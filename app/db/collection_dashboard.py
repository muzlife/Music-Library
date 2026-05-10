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
              SUM(CASE WHEN oi.is_second_hand = 1 THEN 1 ELSE 0 END) AS second_hand_items,
              SUM(CASE WHEN oi.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS registered_last_30_days,
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
              ) AS cover_missing_items
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
        "second_hand_items": int((summary["second_hand_items"] if summary else 0) or 0),
        "audio_mapped_items": int((audio_row["cnt"] if audio_row else 0) or 0),
        "registered_last_30_days": int((summary["registered_last_30_days"] if summary else 0) or 0),
        "slotted_in_collection_items": int((summary["slotted_in_collection_items"] if summary else 0) or 0),
        "unslotted_in_collection_items": int((summary["unslotted_in_collection_items"] if summary else 0) or 0),
        "source_unlinked_items": int((summary["source_unlinked_items"] if summary else 0) or 0),
        "master_unlinked_items": int((summary["master_unlinked_items"] if summary else 0) or 0),
        "cover_missing_items": int((summary["cover_missing_items"] if summary else 0) or 0),
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
