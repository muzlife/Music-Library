"""Operator-home recent-feed DB surface.

Twenty-ninth slice extracted from the legacy `app/db.py`. Owns the
"운영 홈" recent-activity panels — both the "최근 이동" (items
moved between slots) and "최근 등록" (newly registered items)
feeds, plus the unified `get_ops_home_feed` paginator that powers
the "전체 보기" tab.

Public exports
  * count_ops_home_recent_moved_items / list_ops_home_recent_moved_items
  * count_ops_home_recent_registered_items / list_ops_home_recent_registered_items
  * get_ops_home_recent_sections — returns both feeds + their
    counts in a single dict for the operator home page.
  * get_ops_home_feed — paginator wrapper used by the
    "전체 보기" tab.

Module-private
  * _build_ops_home_recent_item — row-shape builder shared by all
    list endpoints. Joins owned_item + storage_slot + the
    cabinet/owned_item_location_event rows for the move feed.

Cross-package dependencies kept on the package surface
  * `_build_label_id`, `_storage_slot_display_name` — cross-cutting
    helpers, stay in __init__.py.
  * `DASHBOARD_MOVE_WINDOW_DAYS` — module-level constant defined
    early in __init__.py.

`app/db/__init__.py` re-exports every public symbol so existing
callers (the operator home page route, the test suite) keep working
unchanged.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import (  # noqa: E402  — package surface
    DASHBOARD_MOVE_WINDOW_DAYS,
    _build_label_id,
    _storage_slot_display_name,
    get_conn,
)


def _build_ops_home_recent_item(row: dict[str, Any]) -> dict[str, Any]:
    category = str(row.get("category") or "").strip()
    owned_item_id = int(row.get("owned_item_id") or row.get("id") or 0)
    current_slot_code = str(row.get("current_slot_code") or "").strip() or None
    current_cabinet_name = str(row.get("current_cabinet_name") or "").strip() or None
    current_column_code = str(row.get("current_column_code") or "").strip() or None
    current_cell_code = str(row.get("current_cell_code") or "").strip() or None
    current_slot_display_name = "미배치"
    if current_slot_code:
        current_slot_display_name = _storage_slot_display_name(
            {
                "slot_code": current_slot_code,
                "cabinet_name": current_cabinet_name,
                "column_code": current_column_code,
                "cell_code": current_cell_code,
                "allowed_size_group": row.get("allowed_size_group"),
                "is_overflow_zone": row.get("is_overflow_zone"),
            }
        )
    runout_values: list[str] = []
    raw_runout_json = row.get("runout_matrix_json")
    if raw_runout_json:
        try:
            parsed_runout = json.loads(str(raw_runout_json))
        except json.JSONDecodeError:
            parsed_runout = []
        if isinstance(parsed_runout, list):
            runout_values = [str(value).strip() for value in parsed_runout if str(value).strip()]
    if not runout_values:
        legacy_runout = str(row.get("runout_matrix") or "").strip()
        if legacy_runout:
            runout_values = [part.strip() for part in legacy_runout.split("|") if part.strip()]

    format_items: list[dict[str, Any]] = []
    raw_format_items = row.get("format_items_json")
    if raw_format_items:
        try:
            parsed_format_items = json.loads(str(raw_format_items))
        except json.JSONDecodeError:
            parsed_format_items = []
        if isinstance(parsed_format_items, list):
            format_items = [dict(value) for value in parsed_format_items if isinstance(value, dict)]
    return {
        "owned_item_id": owned_item_id,
        "label_id": _build_label_id(category, owned_item_id),
        "category": category,
        "format_name": str(row.get("format_name") or "").strip() or None,
        "format_items": format_items,
        "item_title": str(row.get("item_title") or "").strip() or None,
        "artist_or_brand": str(row.get("artist_or_brand") or "").strip() or None,
        "released_date": str(row.get("released_date") or "").strip() or None,
        "pressing_country": str(row.get("pressing_country") or "").strip() or None,
        "label_name": str(row.get("label_name") or "").strip() or None,
        "catalog_no": str(row.get("catalog_no") or "").strip() or None,
        "barcode": str(row.get("barcode") or "").strip() or None,
        "runout_sample": " | ".join(runout_values[:2]) if runout_values else None,
        "cover_image_url": str(row.get("cover_image_url") or "").strip() or None,
        "current_slot_code": current_slot_code,
        "current_slot_display_name": current_slot_display_name,
        "current_cabinet_name": current_cabinet_name,
        "current_column_code": current_column_code,
        "current_cell_code": current_cell_code,
        "previous_slot_code": str(row.get("previous_slot_code") or "").strip() or None,
        "previous_slot_display_name": str(row.get("previous_slot_display_name") or "").strip() or None,
        "created_at": str(row.get("created_at") or ""),
    }


def count_ops_home_recent_moved_items() -> int:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            WITH ranked_events AS (
              SELECT
                e.owned_item_id,
                ROW_NUMBER() OVER (
                  PARTITION BY e.owned_item_id
                  ORDER BY e.created_at DESC, e.id DESC
                ) AS event_rank
              FROM owned_item_location_event e
              WHERE e.movement_kind = 'MOVE'
                AND TRIM(COALESCE(e.from_slot_code, '')) NOT IN ('', 'UNASSIGNED')
                AND e.created_at >= ?
            )
            SELECT COUNT(*) AS total_count
            FROM ranked_events re
            JOIN owned_item oi ON oi.id = re.owned_item_id
            WHERE re.event_rank = 1
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND oi.storage_slot_id IS NOT NULL
            """,
            (move_threshold,),
        ).fetchone()
    return int(row["total_count"] or 0) if row else 0


def list_ops_home_recent_moved_items(limit: int = 6, offset: int = 0) -> list[dict[str, Any]]:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH ranked_events AS (
              SELECT
                e.id AS event_id,
                e.owned_item_id,
                e.from_slot_code AS previous_slot_code,
                e.from_slot_display_name AS previous_slot_display_name,
                e.created_at,
                ROW_NUMBER() OVER (
                  PARTITION BY e.owned_item_id
                  ORDER BY e.created_at DESC, e.id DESC
                ) AS event_rank
              FROM owned_item_location_event e
              WHERE e.movement_kind = 'MOVE'
                AND TRIM(COALESCE(e.from_slot_code, '')) NOT IN ('', 'UNASSIGNED')
                AND e.created_at >= ?
            ),
            recent_events AS (
              SELECT *
              FROM ranked_events
              WHERE event_rank = 1
              ORDER BY created_at DESC, event_id DESC
              LIMIT ?
              OFFSET ?
            )
            SELECT
              re.event_id,
              oi.id AS owned_item_id,
              oi.category,
              mid.format_name,
              COALESCE(oi.item_name_override, am.title) AS item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist_or_brand,
              mid.released_date,
              mid.pressing_country,
              mid.label_name,
              mid.catalog_no,
              mid.barcode,
              mid.runout_matrix_json,
              mid.format_items_json,
              COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
              ss.slot_code AS current_slot_code,
              ss.cabinet_name AS current_cabinet_name,
              ss.column_code AS current_column_code,
              ss.cell_code AS current_cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              re.previous_slot_code,
              re.previous_slot_display_name,
              re.created_at
            FROM recent_events re
            JOIN owned_item oi ON oi.id = re.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND oi.storage_slot_id IS NOT NULL
            ORDER BY re.created_at DESC, re.event_id DESC
            """,
            (move_threshold, int(limit), max(0, int(offset))),
        ).fetchall()
    return [_build_ops_home_recent_item(dict(row)) for row in rows]


def count_ops_home_recent_registered_items(days: int | None = None) -> int:
    where_sql = "WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"
    params: list[Any] = []
    if days is not None and int(days) > 0:
        threshold = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        where_sql += " AND oi.created_at >= ?"
        params.append(threshold)
    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total_count
            FROM owned_item oi
            {where_sql}
            """,
            tuple(params),
        ).fetchone()
    return int(row["total_count"] or 0) if row else 0


def list_ops_home_recent_registered_items(limit: int = 6, offset: int = 0) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH recent_owned AS (
              SELECT
                oi.id,
                oi.category,
                oi.item_name_override,
                oi.linked_album_master_id,
                oi.linked_artist_name,
                oi.storage_slot_id,
                oi.created_at
              FROM owned_item oi
              WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              ORDER BY oi.created_at DESC, oi.id DESC
              LIMIT ?
              OFFSET ?
            )
            SELECT
              oi.id AS owned_item_id,
              oi.category,
              mid.format_name,
              COALESCE(oi.item_name_override, am.title) AS item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist_or_brand,
              mid.released_date,
              mid.pressing_country,
              mid.label_name,
              mid.catalog_no,
              mid.barcode,
              mid.runout_matrix_json,
              mid.format_items_json,
              COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
              ss.slot_code AS current_slot_code,
              ss.cabinet_name AS current_cabinet_name,
              ss.column_code AS current_column_code,
              ss.cell_code AS current_cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              oi.created_at
            FROM recent_owned oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            ORDER BY oi.created_at DESC, oi.id DESC
            """,
            (int(limit), max(0, int(offset))),
        ).fetchall()
    return [_build_ops_home_recent_item(dict(row)) for row in rows]


def get_ops_home_recent_sections(limit: int = 6) -> dict[str, Any]:
    return {
        "recent_moved_items": list_ops_home_recent_moved_items(limit=limit),
        "recent_registered_items": list_ops_home_recent_registered_items(limit=limit),
        "recent_moved_total_count": count_ops_home_recent_moved_items(),
        "recent_registered_total_count": count_ops_home_recent_registered_items(days=30),
    }


def get_ops_home_feed(kind: str = "registered", page: int = 1, limit: int = 30) -> dict[str, Any]:
    normalized_kind = "moved" if str(kind or "").strip().lower() == "moved" else "registered"
    safe_page = max(1, int(page))
    safe_limit = max(1, int(limit))
    offset = (safe_page - 1) * safe_limit
    if normalized_kind == "moved":
        total_count = count_ops_home_recent_moved_items()
        items = list_ops_home_recent_moved_items(limit=safe_limit, offset=offset)
    else:
        total_count = count_ops_home_recent_registered_items()
        items = list_ops_home_recent_registered_items(limit=safe_limit, offset=offset)
    return {
        "kind": normalized_kind,
        "page": safe_page,
        "limit": safe_limit,
        "total_count": total_count,
        "items": items,
    }


# Customer track request CRUD lives in app.db.customer_track_request and
# is re-exported at the bottom of this module.


# Auth-account CRUD (`list_auth_accounts`, `get_auth_account_by_username`,
# `upsert_auth_account`, `delete_auth_account`) lives in app.db.auth_account
# now and is re-exported at the bottom of this module.


__all__ = [
    "_build_ops_home_recent_item",
    "count_ops_home_recent_moved_items",
    "list_ops_home_recent_moved_items",
    "count_ops_home_recent_registered_items",
    "list_ops_home_recent_registered_items",
    "get_ops_home_recent_sections",
    "get_ops_home_feed",
]
