"""Collection-dashboard DB surface.

Thirty-second slice extracted from the legacy `app/db.py`. Owns
the giant `get_collection_dashboard` query that powers the
operator's "내 컬렉션" overview screen — per-cabinet item counts,
top genres, sort-policy summaries, and the "최근 이동" / "최근
등록" sidebars.

Public exports
  * get_collection_dashboard — the whole dashboard payload as one
    dict (also embeds the recent-moved feed via
    `count_ops_home_recent_moved_items` /
    `list_ops_home_recent_moved_items`).

Module-private helpers (only used inside the slice)
  * _extract_collection_dashboard_release_year — pulls the most
    operator-meaningful release_year from a heterogeneous row dict.
  * _build_collection_dashboard_first_item_hints — for each
    storage_slot, pick the "first" item's hint fields (title,
    artist, release_year) used by the dashboard tooltip.

Cross-package dependencies kept on the package surface
  * Many cross-cutting helpers stay in __init__.py: `_build_label_id`,
    `_normalize_*`, `_owned_item_storage_sort_key`,
    `_preferred_korean_artist_by_master_ids`,
    `_storage_slot_*`, `build_storage_slot_occupancy_summary`.
  * `count_ops_home_recent_moved_items`,
    `list_ops_home_recent_moved_items` come from
    `app/db/ops_home_recent.py` (Phase 29).
  * `DASHBOARD_MOVE_WINDOW_DAYS` — module-level constant in
    __init__.py.

Re-export ordering invariant
  collection_dashboard MUST be re-exported AFTER ops_home_recent —
  it pulls the recent-moved feed query from there.

`app/db/__init__.py` re-exports the public function so existing
callers (the operator collection dashboard route, the test suite)
keep working unchanged.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import (  # noqa: E402  — package surface
    DASHBOARD_MOVE_WINDOW_DAYS,
    _build_label_id,
    _normalize_cabinet_sort_policy_value,
    _normalize_domain_code_value,
    _owned_item_storage_sort_key,
    _preferred_korean_artist_by_master_ids,
    _storage_slot_display_name,
    _storage_slot_sort_key,
    build_storage_slot_occupancy_summary,
    count_ops_home_recent_moved_items,
    get_conn,
    list_ops_home_recent_moved_items,
)


def _extract_collection_dashboard_release_year(row: dict[str, Any]) -> int | None:
    for candidate in (
        row.get("master_release_year"),
        row.get("release_year"),
    ):
        try:
            value = int(candidate) if candidate is not None and str(candidate).strip() else None
        except (TypeError, ValueError):
            value = None
        if value is not None and value > 0:
            return value
    for text in (
        row.get("master_release_date"),
        row.get("released_date"),
    ):
        raw = str(text or "").strip()
        match = re.match(r"^(\d{4})", raw)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            value = None
        if value is not None and value > 0:
            return value
    return None


def _build_collection_dashboard_first_item_hints(
    slot_item_map: dict[int, list[dict[str, Any]]],
    slot_policy_map: dict[int, str] | None = None,
) -> dict[int, dict[str, Any]]:
    master_ids = [
        int(row.get("linked_album_master_id") or 0)
        for rows in slot_item_map.values()
        for row in rows
        if int(row.get("linked_album_master_id") or 0) > 0
    ]
    korean_artist_by_master_id = _preferred_korean_artist_by_master_ids(master_ids)
    hints: dict[int, dict[str, Any]] = {}
    for slot_id, rows in slot_item_map.items():
        if not rows:
            continue
        slot_sort_policy = (slot_policy_map or {}).get(slot_id, "ARTIST_RELEASE_TITLE")
        ordered_rows = sorted(
            rows,
            key=lambda row: _owned_item_storage_sort_key(row, korean_artist_by_master_id, slot_sort_policy),
        )
        first_row = ordered_rows[0] if ordered_rows else None
        if not first_row:
            continue
        artist = (
            str(first_row.get("artist_or_brand") or "").strip()
            or str(first_row.get("linked_artist_name") or "").strip()
            or str(first_row.get("master_artist_or_brand") or "").strip()
            or None
        )
        title = (
            str(first_row.get("item_name_override") or "").strip()
            or str(first_row.get("master_title") or "").strip()
            or None
        )
        hints[int(slot_id)] = {
            "first_item_artist_or_brand": artist,
            "first_item_title": title,
            "first_item_release_year": _extract_collection_dashboard_release_year(first_row),
        }
    return hints


def get_collection_dashboard() -> dict[str, Any]:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        summary = conn.execute(
            """
            SELECT
              COUNT(*) AS total_items,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' THEN 1 ELSE 0 END) AS in_collection_items,
              SUM(CASE WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS music_items,
              SUM(CASE WHEN oi.category NOT IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS goods_items,
              SUM(CASE WHEN oi.signature_type IS NOT NULL AND oi.signature_type <> 'NONE' THEN 1 ELSE 0 END) AS signed_items,
              SUM(CASE WHEN oi.signature_type = 'IN_PERSON' THEN 1 ELSE 0 END) AS direct_signed_items,
              SUM(CASE WHEN oi.signature_type = 'PURCHASE_INCLUDED' THEN 1 ELSE 0 END) AS purchase_signed_items,
              SUM(CASE WHEN oi.is_second_hand = 1 THEN 1 ELSE 0 END) AS second_hand_items,
              SUM(CASE WHEN oi.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS registered_last_30_days,
              SUM(CASE WHEN oi.created_at >= datetime('now', '-7 days') THEN 1 ELSE 0 END) AS registered_last_7_days,
              SUM(CASE WHEN oi.created_at >= datetime('now', '-1 days') THEN 1 ELSE 0 END) AS registered_today,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' AND oi.storage_slot_id IS NOT NULL THEN 1 ELSE 0 END) AS slotted_in_collection_items,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' AND oi.storage_slot_id IS NULL THEN 1 ELSE 0 END) AS unslotted_in_collection_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (
                     oi.source_code IS NULL
                     OR TRIM(oi.source_code) = ''
                     OR UPPER(TRIM(oi.source_code)) = 'MANUAL'
                     OR oi.source_external_id IS NULL
                     OR TRIM(oi.source_external_id) = ''
                   )
                  THEN 1
                  ELSE 0
                END
              ) AS source_unlinked_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND oi.linked_album_master_id IS NULL
                  THEN 1
                  ELSE 0
                END
              ) AS master_unlinked_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')
                  THEN 1
                  ELSE 0
                END
              ) AS cover_missing_items,
              SUM(CASE WHEN oi.status = 'LOANED' THEN 1 ELSE 0 END) AS loaned_items,
              SUM(CASE WHEN oi.status = 'SOLD' THEN 1 ELSE 0 END) AS sold_items,
              SUM(CASE WHEN oi.status = 'LOST' THEN 1 ELSE 0 END) AS lost_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (mid.genres_json IS NULL OR TRIM(mid.genres_json) = '' OR mid.genres_json = '[]')
                  THEN 1
                  ELSE 0
                END
              ) AS genre_missing_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (mid.format_name IS NULL OR TRIM(mid.format_name) = '')
                  THEN 1
                  ELSE 0
                END
              ) AS media_missing_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (mid.catalog_no IS NULL OR TRIM(mid.catalog_no) = '')
                  THEN 1
                  ELSE 0
                END
              ) AS catalog_missing_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND mid.format_items_json LIKE '%Limited%'
                  THEN 1
                  ELSE 0
                END
              ) AS limited_items,
              SUM(
                CASE
                  WHEN (mid.format_items_json IS NULL OR mid.format_items_json NOT LIKE '%Promo%')
                   AND COALESCE(oi.is_second_hand, 0) = 0
                  THEN 1 ELSE 0
                END
              ) AS new_items,
              SUM(
                CASE
                  WHEN mid.format_items_json LIKE '%Promo%'
                  THEN 1 ELSE 0
                END
              ) AS promo_items,
              SUM(
                CASE
                  WHEN (mid.format_items_json IS NULL OR mid.format_items_json NOT LIKE '%Promo%')
                   AND COALESCE(oi.is_second_hand, 0) != 0
                  THEN 1 ELSE 0
                END
              ) AS other_condition_items
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            """
        ).fetchone()

        standalone_goods_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM goods_item
            """
        ).fetchone()

        # Additional stats
        box_row = conn.execute("SELECT COUNT(*) FROM owned_item WHERE UPPER(COALESCE(release_type,'')) = 'BOX_SET'").fetchone()
        box_set_items = box_row[0] if box_row else 0
        master_row = conn.execute("SELECT COUNT(*) FROM album_master").fetchone()
        total_master_count = master_row[0] if master_row else 0
        spotify_row = conn.execute("SELECT COUNT(DISTINCT album_master_id) FROM album_master_external_ref WHERE UPPER(source_code) = 'SPOTIFY'").fetchone()
        spotify_master_count = spotify_row[0] if spotify_row else 0

        audio_row = conn.execute(
            """
            SELECT COUNT(DISTINCT l.owned_item_id) AS cnt
            FROM owned_item_digital_link l
            JOIN digital_asset da ON da.id = l.digital_asset_id
            WHERE da.asset_type = 'AUDIO'
            """
        ).fetchone()

        by_category_rows = conn.execute(
            """
            SELECT category, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY category
            ORDER BY cnt DESC, category ASC
            """
        ).fetchall()

        by_status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY status
            ORDER BY cnt DESC, status ASC
            """
        ).fetchall()

        by_domain_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_domain_category_rows = conn.execute(
            """
            SELECT 
              COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS domain,
              category,
              COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED'), category
            ORDER BY domain ASC, cnt DESC
            """
        ).fetchall()

        by_release_type_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(release_type, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(release_type, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_size_group_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(size_group, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY COALESCE(NULLIF(size_group, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_source_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(source_code, ''), 'MANUAL') AS value, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY COALESCE(NULLIF(source_code, ''), 'MANUAL')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_source_domain_rows = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(source_code, ''), 'MANUAL') AS source,
              COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS domain,
              COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(source_code, ''), 'MANUAL'), COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED')
            ORDER BY source ASC, cnt DESC
            """
        ).fetchall()

        by_source_category_rows = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(source_code, ''), 'MANUAL') AS source,
              category,
              COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(source_code, ''), 'MANUAL'), category
            ORDER BY source ASC, cnt DESC
            """
        ).fetchall()

        slot_rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, cabinet_domain_code, cabinet_group_name, cabinet_group_order, column_code, cell_code, allowed_size_group, is_overflow_zone, cabinet_sort_policy
            FROM storage_slot
            """
        ).fetchall()

        slot_count_rows = conn.execute(
            """
            SELECT storage_slot_id, COUNT(*) AS cnt
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NOT NULL
            GROUP BY storage_slot_id
            """
        ).fetchall()

        slot_item_rows = conn.execute(
            """
            SELECT
              oi.storage_slot_id,
              oi.id,
              oi.linked_album_master_id,
              oi.linked_artist_name,
              oi.domain_code,
              oi.order_key,
              oi.display_rank,
              oi.size_group,
              oi.thickness_mm,
              oi.notes,
              oi.item_name_override,
              mid.format_name,
              mid.artist_or_brand,
              mid.release_year,
              mid.released_date,
              mid.disc_count,
              mid.format_items_json,
              am.title AS master_title,
              am.artist_or_brand AS master_artist_or_brand,
              am.sort_artist_name AS master_sort_artist_name,
              am.domain_code AS master_domain_code,
              am.release_year AS master_release_year,
              TRIM(COALESCE(json_extract(am.raw_json, '$.release_date'), json_extract(am.raw_json, '$.master_release_date'), '')) AS master_release_date
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.storage_slot_id IS NOT NULL
            """
        ).fetchall()

        slot_in_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(to_slot_code, ''), 'UNASSIGNED') AS slot_code, COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= ?
            GROUP BY COALESCE(NULLIF(to_slot_code, ''), 'UNASSIGNED')
            """,
            (move_threshold,),
        ).fetchall()

        slot_out_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(from_slot_code, ''), 'UNASSIGNED') AS slot_code, COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= ?
            GROUP BY COALESCE(NULLIF(from_slot_code, ''), 'UNASSIGNED')
            """,
            (move_threshold,),
        ).fetchall()

        unassigned_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NULL
            """
        ).fetchone()

        by_pressing_country_rows = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(TRIM(mid.pressing_country), ''), 'UNKNOWN') AS value,
              COUNT(*) AS cnt
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND mid.pressing_country IS NOT NULL
              AND TRIM(mid.pressing_country) <> ''
            GROUP BY value
            ORDER BY cnt DESC, value ASC
            LIMIT 10
            """
        ).fetchall()
        # Cross-dimensional queries
        # ═══════════════════════════════════════════════════════════

        by_domain_decade = conn.execute(
            """
            SELECT COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   (mid.release_year / 10) * 10 AS decade,
                   COUNT(*) AS cnt
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND mid.release_year IS NOT NULL AND mid.release_year > 0
            GROUP BY domain, decade
            ORDER BY domain, decade
            """
        ).fetchall()

        by_genre_domain = conn.execute(
            """
            SELECT COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   j.value AS genre,
                   COUNT(*) AS cnt
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id,
                 json_each(mid.genres_json) j
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND mid.genres_json IS NOT NULL AND mid.genres_json <> '[]'
            GROUP BY domain, genre
            ORDER BY cnt DESC
            """
        ).fetchall()

        by_format_domain = conn.execute(
            """
            SELECT oi.category AS format,
                   COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   COUNT(*) AS cnt
            FROM owned_item oi
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY oi.category, domain
            ORDER BY cnt DESC
            """
        ).fetchall()

        by_pressing_domain = conn.execute(
            """
            SELECT mid.pressing_country,
                   COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   COUNT(*) AS cnt
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND mid.pressing_country IS NOT NULL AND TRIM(mid.pressing_country) <> ''
            GROUP BY mid.pressing_country, domain
            ORDER BY cnt DESC
            """
        ).fetchall()

        by_artist_decade = conn.execute(
            """
            SELECT artist, MIN(decade) AS min_decade, MAX(decade) AS max_decade, SUM(cnt) AS total
            FROM (
              SELECT COALESCE(mid.artist_or_brand, am.artist_or_brand) AS artist,
                     (mid.release_year / 10) * 10 AS decade,
                     COUNT(*) AS cnt
              FROM owned_item oi
              LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
              LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
              WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                AND mid.release_year IS NOT NULL AND mid.release_year > 0
                AND COALESCE(mid.artist_or_brand, am.artist_or_brand) IS NOT NULL
              GROUP BY artist, decade
            )
            GROUP BY artist
            HAVING total >= 3
               AND LOWER(artist) NOT LIKE '%various%'
               AND LOWER(artist) NOT LIKE '%여러%'
               AND LOWER(artist) NOT LIKE '%옴니버스%'
               AND LOWER(artist) NOT LIKE '%omnibus%'
               AND LOWER(artist) NOT LIKE '%compilation%'
            ORDER BY total DESC
            LIMIT 15
            """
        ).fetchall()

        by_label_country = conn.execute(
            """
            SELECT mid.label_name, mid.pressing_country, COUNT(*) AS cnt
            FROM music_item_detail mid
            JOIN owned_item oi ON oi.id = mid.owned_item_id
            WHERE mid.label_name IS NOT NULL AND TRIM(mid.label_name) <> ''
              AND mid.pressing_country IS NOT NULL AND TRIM(mid.pressing_country) <> ''
            GROUP BY mid.label_name, mid.pressing_country
            ORDER BY cnt DESC
            LIMIT 20
            """
        ).fetchall()

        by_source_completeness = conn.execute(
            """
            SELECT COALESCE(NULLIF(oi.source_code, ''), 'MANUAL') AS source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN oi.linked_album_master_id IS NOT NULL THEN 1 ELSE 0 END) AS master_linked,
                   SUM(CASE WHEN mid.cover_image_url IS NOT NULL AND TRIM(mid.cover_image_url) <> '' THEN 1 ELSE 0 END) AS cover_present,
                   SUM(CASE WHEN mid.genres_json IS NOT NULL AND mid.genres_json <> '[]' THEN 1 ELSE 0 END) AS genre_present,
                   SUM(CASE WHEN mid.catalog_no IS NOT NULL AND TRIM(mid.catalog_no) <> '' THEN 1 ELSE 0 END) AS catalog_present,
                   SUM(CASE WHEN mid.format_name IS NOT NULL AND TRIM(mid.format_name) <> '' THEN 1 ELSE 0 END) AS format_present
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY source
            ORDER BY total DESC
            """
        ).fetchall()

        by_sign_domain = conn.execute(
            """
            SELECT COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   oi.signature_type,
                   COUNT(*) AS cnt
            FROM owned_item oi
            WHERE oi.signature_type IS NOT NULL AND oi.signature_type <> 'NONE'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY domain, oi.signature_type
            ORDER BY cnt DESC
            """
        ).fetchall()

        # ═══════════════════════════════════════════════════════════
        # Ops panel → merged as insight cards
        # ═══════════════════════════════════════════════════════════

        # Card: Move heatmap — slot × move count
        by_slot_moves = conn.execute(
            """
            SELECT COALESCE(NULLIF(to_slot_code, ''), 'UNASSIGNED') AS slot_code,
                   movement_kind,
                   COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY slot_code, movement_kind
            ORDER BY cnt DESC
            """
        ).fetchall()

        # Card: Recent registration profile — domain × decade (last 30 days)
        by_recent_reg_domain_decade = conn.execute(
            """
            SELECT COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain,
                   (mid.release_year / 10) * 10 AS decade,
                   COUNT(*) AS cnt
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.created_at >= datetime('now', '-30 days')
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND mid.release_year IS NOT NULL AND mid.release_year > 0
            GROUP BY domain, decade
            ORDER BY cnt DESC
            """
        ).fetchall()

        by_recent_reg_domain = conn.execute(
            """
            SELECT COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS domain, COUNT(*) AS cnt
            FROM owned_item
            WHERE created_at >= datetime('now', '-30 days')
              AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY domain
            ORDER BY cnt DESC
            """
        ).fetchall()

        # Card: Purchase flow — source × currency × domain
        by_purchase_flow = conn.execute(
            """
            SELECT COALESCE(NULLIF(purchase_source, ''), 'UNKNOWN') AS source,
                   COALESCE(NULLIF(currency_code, ''), 'UNKNOWN') AS currency,
                   COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS domain,
                   COUNT(*) AS items,
                   ROUND(SUM(purchase_price), 0) AS total_spend
            FROM owned_item
            WHERE purchase_price IS NOT NULL
              AND purchase_source IS NOT NULL AND TRIM(purchase_source) <> ''
            GROUP BY source, currency, domain
            ORDER BY items DESC
            """
        ).fetchall()

        # ── New dashboard cards ──

        # Card: Financial Overview
        by_currency_spend = conn.execute(
            """
            SELECT currency_code, COUNT(*) AS items, ROUND(SUM(purchase_price), 0) AS total_spend
            FROM owned_item
            WHERE purchase_price IS NOT NULL AND currency_code IS NOT NULL
            GROUP BY currency_code
            ORDER BY total_spend DESC
            """
        ).fetchall()
        by_domain_spend = conn.execute(
            """
            SELECT COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS domain,
                   COUNT(*) AS items,
                   ROUND(AVG(purchase_price), 0) AS avg_price,
                   ROUND(SUM(purchase_price), 0) AS total_spend
            FROM owned_item
            WHERE purchase_price IS NOT NULL
              AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED')
            ORDER BY total_spend DESC
            """
        ).fetchall()
        by_month_spend = conn.execute(
            """
            SELECT strftime('%Y-%m', acquisition_date) AS month,
                   COUNT(*) AS items,
                   ROUND(SUM(purchase_price), 0) AS total_spend
            FROM owned_item
            WHERE acquisition_date IS NOT NULL AND purchase_price IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
            """
        ).fetchall()

        # Card: Artist / Label / Genre
        by_artist = conn.execute(
            """
            SELECT COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist,
                   COUNT(*) AS cnt
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY artist
            ORDER BY cnt DESC
            LIMIT 15
            """
        ).fetchall()
        by_label = conn.execute(
            """
            SELECT label_name, COUNT(*) AS cnt
            FROM music_item_detail
            WHERE label_name IS NOT NULL AND TRIM(label_name) <> ''
            GROUP BY label_name
            ORDER BY cnt DESC
            LIMIT 15
            """
        ).fetchall()
        by_genre = conn.execute(
            """
            SELECT value AS genre, COUNT(*) AS cnt
            FROM music_item_detail, json_each(genres_json)
            WHERE genres_json IS NOT NULL AND genres_json <> '[]'
            GROUP BY value
            ORDER BY cnt DESC
            LIMIT 15
            """
        ).fetchall()

        # Card: Timeline
        by_release_decade = conn.execute(
            """
            SELECT (release_year / 10) * 10 AS decade, COUNT(*) AS cnt
            FROM music_item_detail
            WHERE release_year IS NOT NULL AND release_year > 0
            GROUP BY decade
            ORDER BY decade
            """
        ).fetchall()
        by_registration_month = conn.execute(
            """
            SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY month
            ORDER BY month
            """
        ).fetchall()

        # Card: Collector Value
        multi_disc_items = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM music_item_detail
            WHERE disc_count >= 3
            """
        ).fetchone()
        obi_items = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM music_item_detail
            WHERE has_obi = 1
            """
        ).fetchone()
        by_media_condition = conn.execute(
            """
            SELECT media_condition, COUNT(*) AS cnt
            FROM music_item_detail
            WHERE media_condition IS NOT NULL AND TRIM(media_condition) <> ''
            GROUP BY media_condition
            ORDER BY cnt DESC
            """
        ).fetchall()
        # Import queue
        import_queue_size = conn.execute("SELECT COUNT(*) AS cnt FROM purchase_import_queue").fetchone()
        # Sync coverage rates
        sync_sources = conn.execute("SELECT source_code, COUNT(*) AS cnt FROM album_master GROUP BY source_code").fetchall()

    slot_count_map = {int(row["storage_slot_id"]): int(row["cnt"] or 0) for row in slot_count_rows if row["storage_slot_id"] is not None}
    slot_policy_map: dict[int, str] = {
        int(row["id"]): _normalize_cabinet_sort_policy_value(row["cabinet_sort_policy"])
        for row in slot_rows
        if row["id"] is not None
    }
    slot_item_map: dict[int, list[dict[str, Any]]] = {}
    for row in slot_item_rows:
        storage_slot_id = int(row["storage_slot_id"] or 0)
        if storage_slot_id <= 0:
            continue
        slot_item_map.setdefault(storage_slot_id, []).append(dict(row))
    slot_first_item_hint_map = _build_collection_dashboard_first_item_hints(slot_item_map, slot_policy_map)
    slot_in_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_in_rows}
    slot_out_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_out_rows}
    structured_slots = [dict(row) for row in slot_rows]
    recent_move_total = count_ops_home_recent_moved_items()
    recent_move_items = list_ops_home_recent_moved_items(limit=12)
    for item in structured_slots:
        item["display_name"] = _storage_slot_display_name(item)
        item["count"] = int(slot_count_map.get(int(item["id"]), 0))
        item["recent_in_count"] = int(slot_in_map.get(str(item["slot_code"] or ""), 0))
        item["recent_out_count"] = int(slot_out_map.get(str(item["slot_code"] or ""), 0))
        item.update(build_storage_slot_occupancy_summary(item, slot_item_map.get(int(item["id"]), [])))
        item.update(slot_first_item_hint_map.get(int(item["id"]), {}))
    structured_slots.sort(key=_storage_slot_sort_key)

    legacy_goods_items = int((summary["goods_items"] if summary else 0) or 0)
    standalone_goods_items = int((standalone_goods_row["cnt"] if standalone_goods_row else 0) or 0)



    return {
    
        "total_items": int((summary["total_items"] if summary else 0) or 0),
        "in_collection_items": int((summary["in_collection_items"] if summary else 0) or 0),
        "music_items": int((summary["music_items"] if summary else 0) or 0),
        "goods_items": legacy_goods_items + standalone_goods_items,
        "signed_items": int((summary["signed_items"] if summary else 0) or 0),
        "direct_signed_items": int((summary["direct_signed_items"] if summary else 0) or 0),
        "purchase_signed_items": int((summary["purchase_signed_items"] if summary else 0) or 0),
        "second_hand_items": int((summary["second_hand_items"] if summary else 0) or 0),
        "box_set_items": box_set_items,
        "total_master_count": total_master_count,
        "spotify_master_count": spotify_master_count,
        "audio_mapped_items": int((audio_row["cnt"] if audio_row else 0) or 0),
        "registered_last_30_days": int((summary["registered_last_30_days"] if summary else 0) or 0),
        "registered_last_7_days": int((summary["registered_last_7_days"] if summary else 0) or 0),
        "registered_today": int((summary["registered_today"] if summary else 0) or 0),
        "slotted_in_collection_items": int((summary["slotted_in_collection_items"] if summary else 0) or 0),
        "unslotted_in_collection_items": int((summary["unslotted_in_collection_items"] if summary else 0) or 0),
        "source_unlinked_items": int((summary["source_unlinked_items"] if summary else 0) or 0),
        "master_unlinked_items": int((summary["master_unlinked_items"] if summary else 0) or 0),
        "cover_missing_items": int((summary["cover_missing_items"] if summary else 0) or 0),
        "multi_disc_items": int((multi_disc_items["cnt"] if multi_disc_items else 0) or 0),
        "obi_items": int((obi_items["cnt"] if obi_items else 0) or 0),
        "import_queue_size": int((import_queue_size["cnt"] if import_queue_size else 0) or 0),
        "by_artist": [
            {"artist": str(row["artist"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_artist
        ],
        "by_label": [
            {"label": str(row["label_name"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_label
        ],
        "by_genre": [
            {"genre": str(row["genre"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_genre
        ],
        "by_release_decade": [
            {"decade": int(row["decade"] or 0), "count": int(row["cnt"] or 0)}
            for row in by_release_decade
        ],
        "by_registration_month": [
            {"month": str(row["month"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_registration_month
        ],
        "by_currency_spend": [
            {"currency_code": str(row["currency_code"] or ""), "items": int(row["items"] or 0), "total_spend": int(row["total_spend"] or 0)}
            for row in by_currency_spend
        ],
        "by_domain_spend": [
            {"domain": str(row["domain"] or ""), "items": int(row["items"] or 0), "avg_price": int(row["avg_price"] or 0), "total_spend": int(row["total_spend"] or 0)}
            for row in by_domain_spend
        ],
        "by_month_spend": [
            {"month": str(row["month"] or ""), "items": int(row["items"] or 0), "total_spend": int(row["total_spend"] or 0)}
            for row in by_month_spend
        ],
        "by_media_condition": [
            {"condition": str(row["media_condition"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_media_condition
        ],
        "sync_sources": [
            {"source_code": str(row["source_code"] or ""), "count": int(row["cnt"] or 0)}
            for row in sync_sources
        ],
        "loaned_items": int((summary["loaned_items"] if summary else 0) or 0),
        "sold_items": int((summary["sold_items"] if summary else 0) or 0),
        "lost_items": int((summary["lost_items"] if summary else 0) or 0),
        "genre_missing_items": int((summary["genre_missing_items"] if summary else 0) or 0),
        "media_missing_items": int((summary["media_missing_items"] if summary else 0) or 0),
        "catalog_missing_items": int((summary["catalog_missing_items"] if summary else 0) or 0),
        "limited_items": int((summary["limited_items"] if summary else 0) or 0),
        "new_items": int((summary["new_items"] if summary else 0) or 0),
        "promo_items": int((summary["promo_items"] if summary else 0) or 0),
        "other_condition_items": int((summary["other_condition_items"] if summary else 0) or 0),
        "by_pressing_country": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_pressing_country_rows
        ],
        # Cross-dimensional
        "by_domain_decade": [
            {"domain": str(row["domain"] or ""), "decade": int(row["decade"] or 0), "count": int(row["cnt"] or 0)}
            for row in by_domain_decade
        ],
        "by_genre_domain": [
            {"domain": str(row["domain"] or ""), "genre": str(row["genre"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_genre_domain
        ],
        "by_format_domain": [
            {"format": str(row["format"] or ""), "domain": str(row["domain"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_format_domain
        ],
        "by_pressing_domain": [
            {"pressing_country": str(row["pressing_country"] or ""), "domain": str(row["domain"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_pressing_domain
        ],
        "by_artist_decade": [
            {"artist": str(row["artist"] or ""), "min_decade": int(row["min_decade"] or 0), "max_decade": int(row["max_decade"] or 0), "total": int(row["total"] or 0)}
            for row in by_artist_decade
        ],
        "by_label_country": [
            {"label": str(row["label_name"] or ""), "pressing_country": str(row["pressing_country"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_label_country
        ],
        "by_source_completeness": [
            {"source": str(row["source"] or ""), "total": int(row["total"] or 0), "master_linked": int(row["master_linked"] or 0), "cover_present": int(row["cover_present"] or 0), "genre_present": int(row["genre_present"] or 0), "catalog_present": int(row["catalog_present"] or 0), "format_present": int(row["format_present"] or 0)}
            for row in by_source_completeness
        ],
        "by_sign_domain": [
            {"domain": str(row["domain"] or ""), "signature_type": str(row["signature_type"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_sign_domain
        ],
        "by_slot_moves": [
            {"slot_code": str(row["slot_code"] or ""), "movement_kind": str(row["movement_kind"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_slot_moves
        ],
        "by_recent_reg_domain_decade": [
            {"domain": str(row["domain"] or ""), "decade": int(row["decade"] or 0), "count": int(row["cnt"] or 0)}
            for row in by_recent_reg_domain_decade
        ],
        "by_recent_reg_domain": [
            {"value": str(row["domain"] or ""), "count": int(row["cnt"] or 0)}
            for row in by_recent_reg_domain
        ],
        "by_purchase_flow": [
            {"source": str(row["source"] or ""), "currency": str(row["currency"] or ""), "domain": str(row["domain"] or ""), "items": int(row["items"] or 0), "total_spend": int(row["total_spend"] or 0)}
            for row in by_purchase_flow
        ],

        "by_category": [
            {"category": str(row["category"]), "count": int(row["cnt"] or 0)}
            for row in by_category_rows
        ],
        "by_status": [
            {"status": str(row["status"]), "count": int(row["cnt"] or 0)}
            for row in by_status_rows
        ],
        "by_domain": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_domain_rows
        ],
        "by_domain_category": [
            {"domain": str(row["domain"]), "category": str(row["category"]), "count": int(row["cnt"] or 0)}
            for row in by_domain_category_rows
        ],
        "by_release_type": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_release_type_rows
        ],
        "by_size_group": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_size_group_rows
        ],
        "by_source": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_source_rows
        ],
        "by_source_domain": [
            {"source": str(row["source"]), "domain": str(row["domain"]), "count": int(row["cnt"] or 0)}
            for row in by_source_domain_rows
        ],
        "by_source_category": [
            {"source": str(row["source"]), "category": str(row["category"]), "count": int(row["cnt"] or 0)}
            for row in by_source_category_rows
        ],
        "movement_window_days": DASHBOARD_MOVE_WINDOW_DAYS,
        "recent_move_total": int(recent_move_total),
        "recent_moves": [
            {
                "id": int(row["owned_item_id"]),
                "owned_item_id": int(row["owned_item_id"]),
                "label_id": str(row.get("label_id") or _build_label_id(str(row["category"] or ""), int(row["owned_item_id"]))),
                "category": str(row["category"] or ""),
                "item_title": str(row["item_title"]) if row["item_title"] is not None else None,
                "artist_or_brand": str(row["artist_or_brand"]) if row["artist_or_brand"] is not None else None,
                "cover_image_url": str(row["cover_image_url"]) if row["cover_image_url"] is not None else None,
                "movement_kind": "MOVE",
                "from_slot_code": str(row["previous_slot_code"]) if row.get("previous_slot_code") is not None else None,
                "from_display_name": str(row["previous_slot_display_name"]) if row.get("previous_slot_display_name") is not None else None,
                "to_slot_code": str(row["current_slot_code"]) if row.get("current_slot_code") is not None else None,
                "to_display_name": str(row["current_slot_display_name"]) if row.get("current_slot_display_name") is not None else None,
                "note": None,
                "created_at": str(row["created_at"] or ""),
            }
            for row in recent_move_items
        ],
        "by_slot": [
            {
                "slot_code": str(row["slot_code"]),
                "cabinet_name": str(row["cabinet_name"]) if row.get("cabinet_name") is not None else None,
                "cabinet_domain_code": _normalize_domain_code_value(row.get("cabinet_domain_code")),
                "cabinet_group_name": str(row["cabinet_group_name"]) if row.get("cabinet_group_name") is not None else None,
                "cabinet_group_order": int(row["cabinet_group_order"]) if row.get("cabinet_group_order") not in (None, "") else None,
                "column_code": str(row["column_code"]) if row.get("column_code") is not None else None,
                "cell_code": str(row["cell_code"]) if row.get("cell_code") is not None else None,
                "display_name": str(row["display_name"]) if row.get("display_name") is not None else None,
                "allowed_size_group": str(row["allowed_size_group"]) if row.get("allowed_size_group") is not None else None,
                "is_overflow_zone": bool(row["is_overflow_zone"]),
                "count": int(row["count"] or 0),
                "recent_in_count": int(row.get("recent_in_count") or 0),
                "recent_out_count": int(row.get("recent_out_count") or 0),
                "capacity_mm": int(row.get("capacity_mm") or 0),
                "used_thickness_mm": int(row.get("used_thickness_mm") or 0),
                "free_thickness_mm": int(row.get("free_thickness_mm") or 0),
                "occupancy_ratio": float(row.get("occupancy_ratio") or 0.0),
                "occupancy_percent": int(row.get("occupancy_percent") or 0),
                "first_item_artist_or_brand": str(row["first_item_artist_or_brand"]) if row.get("first_item_artist_or_brand") is not None else None,
                "first_item_title": str(row["first_item_title"]) if row.get("first_item_title") is not None else None,
                "first_item_release_year": int(row["first_item_release_year"]) if row.get("first_item_release_year") not in (None, "") else None,
            }
            for row in structured_slots
        ]
        + [
            {
                "slot_code": "UNASSIGNED",
                "cabinet_name": "미배치",
                "cabinet_domain_code": None,
                "cabinet_group_name": None,
                "cabinet_group_order": None,
                "column_code": None,
                "cell_code": None,
                "display_name": "미배치",
                "allowed_size_group": None,
                "is_overflow_zone": False,
                "count": int((unassigned_row["cnt"] if unassigned_row else 0) or 0),
                "recent_in_count": int(slot_in_map.get("UNASSIGNED", 0)),
                "recent_out_count": int(slot_out_map.get("UNASSIGNED", 0)),
                "capacity_mm": 0,
                "used_thickness_mm": 0,
                "free_thickness_mm": 0,
                "occupancy_ratio": 0.0,
                "occupancy_percent": 0,
            }
        ],
    }


__all__ = [
    "get_collection_dashboard",
]
