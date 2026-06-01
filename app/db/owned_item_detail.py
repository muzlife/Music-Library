"""수집품 상세 upsert 도메인 (owned_item_detail).

db/__init__.py 에서 분리된 슬라이스. owned_item에 연결된
music_item_detail / goods_item_detail 행의 INSERT OR REPLACE 로직을 소유한다.

공개 surface (app.db re-export)
  _upsert_music_item_detail_in_conn  — 음반 상세 정보 upsert
  _upsert_goods_item_detail_in_conn  — 굿즈 상세 정보 upsert

변경격리: owned_item 쿼리/정규화는 owned_item_select.py 에서 담당.
테스트 단위: test_owned_item_detail.py 에서 독립 검증.

Cross-package dependencies
  utc_now_iso — app.db surface
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import utc_now_iso  # noqa: E402

def _upsert_music_item_detail_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    music_detail: dict[str, Any],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    disc_condition = music_detail.get("disc_condition") or music_detail.get("media_condition")
    cover_condition = music_detail.get("cover_condition") or music_detail.get("sleeve_condition")
    has_obi_raw = music_detail.get("has_obi")
    has_obi_db: int | None = None
    if isinstance(has_obi_raw, bool):
        has_obi_db = 1 if has_obi_raw else None
    elif has_obi_raw in {0, 1}:
        has_obi_db = 1 if int(has_obi_raw) == 1 else None
    elif isinstance(has_obi_raw, str):
        lowered = has_obi_raw.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            has_obi_db = 1
    runout_matrix_values_raw = music_detail.get("runout_matrix")
    if isinstance(runout_matrix_values_raw, list):
        runout_matrix_values = [str(v).strip() for v in runout_matrix_values_raw if str(v).strip()]
    elif runout_matrix_values_raw is None:
        runout_matrix_values = []
    else:
        text = str(runout_matrix_values_raw).strip()
        runout_matrix_values = [p.strip() for p in text.split("|") if p.strip()] if text else []
    runout_matrix_legacy = " | ".join(runout_matrix_values) if runout_matrix_values else None
    conn.execute(
        """
        INSERT INTO music_item_detail (
          owned_item_id, format_name, is_promotional_not_for_sale,
          artist_or_brand, release_year, released_date, barcode,
          label_name, catalog_no, cover_image_url, track_list_json,
          media_type, genres_json, styles_json,
          media_condition, sleeve_condition, disc_count, speed_rpm,
          has_obi, runout_matrix, runout_matrix_json, pressing_country,
          disc_type,
          package_contents, is_limited_edition, edition_number,
          source_notes, credits_json, identifier_items_json, image_items_json,
          company_items_json, series_json, format_items_json, track_items_json,
          label_items_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owned_item_id) DO UPDATE SET
          format_name = excluded.format_name,
          is_promotional_not_for_sale = MAX(excluded.is_promotional_not_for_sale, is_promotional_not_for_sale),
          artist_or_brand = excluded.artist_or_brand,
          release_year = excluded.release_year,
          released_date = excluded.released_date,
          barcode = excluded.barcode,
          label_name = excluded.label_name,
          catalog_no = excluded.catalog_no,
          cover_image_url = excluded.cover_image_url,
          track_list_json = excluded.track_list_json,
          media_type = excluded.media_type,
          genres_json = excluded.genres_json,
          styles_json = excluded.styles_json,
          media_condition = excluded.media_condition,
          sleeve_condition = excluded.sleeve_condition,
          disc_count = excluded.disc_count,
          speed_rpm = excluded.speed_rpm,
          has_obi = excluded.has_obi,
          runout_matrix = excluded.runout_matrix,
          runout_matrix_json = excluded.runout_matrix_json,
          pressing_country = excluded.pressing_country,
          disc_type = COALESCE(excluded.disc_type, disc_type),
          package_contents = excluded.package_contents,
          is_limited_edition = CASE WHEN excluded.is_limited_edition IS NOT NULL THEN MAX(COALESCE(excluded.is_limited_edition,0), COALESCE(is_limited_edition,0)) ELSE is_limited_edition END,
          edition_number = excluded.edition_number,
          source_notes = excluded.source_notes,
          credits_json = excluded.credits_json,
          identifier_items_json = excluded.identifier_items_json,
          image_items_json = excluded.image_items_json,
          company_items_json = excluded.company_items_json,
          series_json = excluded.series_json,
          format_items_json = excluded.format_items_json,
          track_items_json = excluded.track_items_json,
          label_items_json = excluded.label_items_json,
          updated_at = excluded.updated_at
        """,
        (
            owned_item_id,
            music_detail.get("format_name"),
            1 if music_detail.get("is_promotional_not_for_sale") else 0,
            music_detail.get("artist_or_brand"),
            music_detail.get("release_year"),
            music_detail.get("released_date"),
            music_detail.get("barcode"),
            music_detail.get("label_name"),
            music_detail.get("catalog_no"),
            music_detail.get("cover_image_url"),
            json.dumps(music_detail.get("track_list", []), ensure_ascii=True),
            music_detail.get("media_type"),
            json.dumps(music_detail.get("genres", []), ensure_ascii=True),
            json.dumps(music_detail.get("styles", []), ensure_ascii=True),
            disc_condition,
            cover_condition,
            music_detail.get("disc_count"),
            music_detail.get("speed_rpm"),
            has_obi_db,
            runout_matrix_legacy,
            json.dumps(runout_matrix_values, ensure_ascii=True),
            music_detail.get("pressing_country"),
            music_detail.get("disc_type"),
            music_detail.get("package_contents") or None,
            (1 if music_detail.get("is_limited_edition") else 0) if music_detail.get("is_limited_edition") is not None else None,
            music_detail.get("edition_number") or None,
            music_detail.get("source_notes"),
            json.dumps(music_detail.get("credits", []), ensure_ascii=True),
            json.dumps(music_detail.get("identifier_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("image_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("company_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("series", []), ensure_ascii=True),
            json.dumps(music_detail.get("format_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("track_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("label_items", []), ensure_ascii=True),
            timestamp,
            timestamp,
        ),
    )


def _upsert_goods_item_detail_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    goods_detail: dict[str, Any],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    image_urls_raw = goods_detail.get("image_urls")
    if isinstance(image_urls_raw, list):
        image_urls = [str(v).strip() for v in image_urls_raw if str(v).strip()]
    elif image_urls_raw is None:
        image_urls = []
    else:
        text = str(image_urls_raw).strip()
        image_urls = [part.strip() for part in text.splitlines() if part.strip()] if text else []

    primary_image_url = str(goods_detail.get("primary_image_url") or "").strip() or None
    if primary_image_url is None and image_urls:
        primary_image_url = image_urls[0]

    poster_storage_spec = str(goods_detail.get("poster_storage_spec") or "").strip() or None
    tshirt_size = str(goods_detail.get("tshirt_size") or "").strip() or None
    cup_material = str(goods_detail.get("cup_material") or "").strip() or None
    hat_size = str(goods_detail.get("hat_size") or "").strip() or None

    conn.execute(
        """
        INSERT INTO goods_item_detail (
          owned_item_id,
          image_urls_json,
          primary_image_url,
          poster_storage_spec,
          tshirt_size,
          cup_material,
          hat_size,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owned_item_id) DO UPDATE SET
          image_urls_json = excluded.image_urls_json,
          primary_image_url = excluded.primary_image_url,
          poster_storage_spec = excluded.poster_storage_spec,
          tshirt_size = excluded.tshirt_size,
          cup_material = excluded.cup_material,
          hat_size = excluded.hat_size,
          updated_at = excluded.updated_at
        """,
        (
            owned_item_id,
            json.dumps(image_urls, ensure_ascii=True),
            primary_image_url,
            poster_storage_spec,
            tshirt_size,
            cup_material,
            hat_size,
            timestamp,
            timestamp,
        ),
    )
