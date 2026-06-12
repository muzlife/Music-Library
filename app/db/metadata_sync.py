"""Metadata-sync candidate query + music_detail upsert surface.

Thirtieth slice extracted from the legacy `app/db.py`. Owns the
two functions that drive the periodic metadata sync job:

  * list_metadata_sync_candidates — scan owned_items for ones that
    look ripe for metadata refresh (missing fields, stale
    last-synced-at, source priority bumps). Powers the operator
    "메타데이터 동기화 대상" admin route + the scheduled
    background sync.
  * upsert_music_detail — write a fresh music_item_detail row for
    one owned_item. Thin wrapper around the
    `_upsert_music_item_detail_in_conn` helper.

Cross-package dependencies kept on the package surface
  * `_upsert_music_item_detail_in_conn` — heavy upsert helper
    shared with insert/update_owned_item. Stays in __init__.py.

`app/db/__init__.py` re-exports both public functions so existing
callers (the metadata-sync admin route, the scheduled background
job, the test suite) keep working unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _upsert_music_item_detail_in_conn,
    get_conn,
    utc_now_iso,
)


def list_metadata_sync_candidates(
    source_code: str | None,
    only_missing: bool,
    limit: int,
    offset: int = 0,
    owned_item_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    query = """
      SELECT
        oi.id,
        oi.category,
        oi.source_code,
        oi.source_external_id,
        oi.linked_album_master_id,
        mid.format_name,
        mid.artist_or_brand,
        mid.release_year,
        mid.released_date,
        mid.barcode,
        mid.label_name,
        mid.catalog_no,
        mid.cover_image_url,
        mid.track_list_json,
        mid.media_type,
        mid.genres_json,
        mid.styles_json,
        mid.disc_count,
        mid.speed_rpm,
        mid.has_obi,
        mid.runout_matrix,
        mid.runout_matrix_json,
        mid.pressing_country,
        mid.source_notes,
        mid.credits_json,
        mid.identifier_items_json,
        mid.image_items_json,
        mid.company_items_json,
        mid.series_json,
        mid.format_items_json,
        mid.track_items_json,
        mid.label_items_json,
        mid.is_promotional_not_for_sale,
        mid.sleeve_condition AS cover_condition,
        mid.media_condition AS disc_condition,
        oi.item_name_override,
        am.title AS master_title,
        COALESCE(oi.item_name_override, am.title) AS display_name
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
      WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
        AND oi.source_code IS NOT NULL
        AND TRIM(COALESCE(oi.source_external_id, '')) <> ''
    """
    params: list[Any] = []
    if owned_item_ids:
        placeholders = ",".join("?" * len(owned_item_ids))
        query += f" AND oi.id IN ({placeholders})"
        params.extend(owned_item_ids)
    if source_code:
        query += " AND oi.source_code = ?"
        params.append(source_code)

    if only_missing:
        query += """
          AND (
            mid.owned_item_id IS NULL
            OR TRIM(COALESCE(mid.label_name, '')) = ''
            OR TRIM(COALESCE(mid.catalog_no, '')) = ''
            OR TRIM(COALESCE(mid.cover_image_url, '')) = ''
            OR TRIM(COALESCE(mid.barcode, '')) = ''
            OR TRIM(COALESCE(mid.media_type, '')) = ''
            OR am.genres_json IS NULL
            OR TRIM(COALESCE(am.genres_json, '')) = ''
            OR TRIM(COALESCE(am.genres_json, '')) = '[]'
            OR am.styles_json IS NULL
            OR TRIM(COALESCE(am.styles_json, '')) = ''
            OR TRIM(COALESCE(am.styles_json, '')) = '[]'
            OR mid.track_list_json IS NULL
            OR TRIM(COALESCE(mid.track_list_json, '')) = ''
            OR TRIM(COALESCE(mid.track_list_json, '')) = '[]'
          )
        """

    query += """
      ORDER BY oi.updated_at ASC, oi.id ASC
      LIMIT ? OFFSET ?
    """
    params.extend([max(1, int(limit)), max(0, int(offset))])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_tracks = item.pop("track_list_json", None)
        if raw_tracks:
            try:
                parsed = json.loads(raw_tracks)
                item["track_list"] = [str(v).strip() for v in parsed if str(v).strip()] if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                item["track_list"] = []
        else:
            item["track_list"] = []

        raw_genres = item.pop("genres_json", None)
        if raw_genres:
            try:
                parsed_genres = json.loads(raw_genres)
                item["genres"] = [str(v).strip() for v in parsed_genres if str(v).strip()] if isinstance(parsed_genres, list) else []
            except json.JSONDecodeError:
                item["genres"] = []
        else:
            item["genres"] = []

        raw_styles = item.pop("styles_json", None)
        if raw_styles:
            try:
                parsed_styles = json.loads(raw_styles)
                item["styles"] = [str(v).strip() for v in parsed_styles if str(v).strip()] if isinstance(parsed_styles, list) else []
            except json.JSONDecodeError:
                item["styles"] = []
        else:
            item["styles"] = []

        runout_values: list[str] = []
        raw_runout_json = item.pop("runout_matrix_json", None)
        if raw_runout_json:
            try:
                parsed_runout = json.loads(raw_runout_json)
                runout_values = [str(v).strip() for v in parsed_runout if str(v).strip()] if isinstance(parsed_runout, list) else []
            except json.JSONDecodeError:
                runout_values = []
        if not runout_values:
            legacy_runout = str(item.get("runout_matrix") or "").strip()
            if legacy_runout:
                runout_values = [p.strip() for p in legacy_runout.split("|") if p.strip()]
        item["runout_matrix"] = runout_values

        def _parse_json_string_list(raw: Any) -> list[str]:
            if not raw:
                return []
            try:
                parsed = json.loads(str(raw))
            except json.JSONDecodeError:
                return []
            if not isinstance(parsed, list):
                return []
            return [str(v).strip() for v in parsed if str(v).strip()]

        def _parse_json_dict_list(raw: Any) -> list[dict[str, Any]]:
            if not raw:
                return []
            try:
                parsed = json.loads(str(raw))
            except json.JSONDecodeError:
                return []
            if not isinstance(parsed, list):
                return []
            return [row for row in parsed if isinstance(row, dict)]

        item["credits"] = _parse_json_string_list(item.pop("credits_json", None))
        item["identifier_items"] = _parse_json_dict_list(item.pop("identifier_items_json", None))
        item["image_items"] = _parse_json_dict_list(item.pop("image_items_json", None))
        item["company_items"] = _parse_json_dict_list(item.pop("company_items_json", None))
        item["series"] = _parse_json_string_list(item.pop("series_json", None))
        item["format_items"] = _parse_json_dict_list(item.pop("format_items_json", None))
        item["track_items"] = _parse_json_dict_list(item.pop("track_items_json", None))
        item["label_items"] = _parse_json_dict_list(item.pop("label_items_json", None))

        item["is_promotional_not_for_sale"] = bool(item.get("is_promotional_not_for_sale"))
        if item.get("has_obi") is not None:
            item["has_obi"] = True if int(item.get("has_obi")) == 1 else None
        out.append(item)
    return out


def upsert_music_detail(owned_item_id: int, music_detail: dict[str, Any], note_append: str | None = None) -> None:
    from app.db.catalog_search import upsert_catalog_search_in_conn
    now = utc_now_iso()
    with get_conn() as conn:
        _upsert_music_item_detail_in_conn(
            conn,
            owned_item_id=owned_item_id,
            music_detail=music_detail,
            now=now,
        )
        if note_append:
            conn.execute(
                """
                UPDATE owned_item
                SET updated_at = ?,
                    memory_note = CASE
                        WHEN IFNULL(TRIM(memory_note), '') = '' THEN ?
                        ELSE memory_note || char(10) || ?
                    END
                WHERE id = ?
                """,
                (now, note_append, note_append, owned_item_id),
            )
        else:
            conn.execute(
                """
                UPDATE owned_item
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, owned_item_id),
            )
        upsert_catalog_search_in_conn(conn, owned_item_id)


__all__ = [
    "list_metadata_sync_candidates",
    "upsert_music_detail",
]
