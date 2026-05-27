"""Customer track request DB surface.

Fourth slice extracted from the legacy `app/db.py`. Owns the
`customer_track_request` table — the queue that captures a customer's
track-of-the-moment request and the operator's response.

Public exports
  * create_customer_track_request
  * get_customer_track_request
  * list_customer_track_requests
  * count_customer_track_requests
  * update_customer_track_request

`app/db/__init__.py` re-exports every public symbol so existing
callers (the operator UI router, the test suite) keep working.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _build_label_id,
    _storage_slot_display_name,
    get_conn,
    get_owned_item_detail,
    get_owned_item_location_snapshot,
    utc_now_iso,
)


def create_customer_track_request(
    requested_track: str,
    requested_by: str | None = None,
    owned_item_id: int | None = None,
    matched_track_title: str | None = None,
    matched_track_no: int | None = None,
    customer_note: str | None = None,
    weather_temp_c: float | None = None,
    weather_description: str | None = None,
    weather_code: int | None = None,
    season: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    owned_id = int(owned_item_id) if owned_item_id else None
    detail = get_owned_item_detail(owned_id) if owned_id else None
    location = get_owned_item_location_snapshot(owned_id) if owned_id else None

    item_title = None
    artist_or_brand = None
    cover_image_url = None
    category = None
    if detail is not None:
        category = str(detail.get("category") or "").strip() or None
        item_title = str(detail.get("item_name_override") or "").strip() or None
        artist_or_brand = str(detail.get("artist_or_brand") or "").strip() or None
        item_title = item_title or str(detail.get("catalog_no") or "").strip() or None
        cover_image_url = str(detail.get("cover_image_url") or detail.get("goods_primary_image_url") or "").strip() or None

    resolved_season = season
    if not resolved_season:
        try:
            month = int(now.split("-")[1])
            if month in {3, 4, 5}:
                resolved_season = "SPRING"
            elif month in {6, 7, 8}:
                resolved_season = "SUMMER"
            elif month in {9, 10, 11}:
                resolved_season = "AUTUMN"
            else:
                resolved_season = "WINTER"
        except Exception:
            resolved_season = "SPRING"

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO customer_track_request (
              requested_track,
              owned_item_id,
              matched_track_title,
              matched_track_no,
              item_title_snapshot,
              artist_or_brand_snapshot,
              cover_image_url_snapshot,
              category_snapshot,
              current_slot_code_snapshot,
              current_slot_display_snapshot,
              previous_slot_code_snapshot,
              previous_slot_display_snapshot,
              customer_note,
              status,
              requested_by,
              weather_temp_c,
              weather_description,
              weather_code,
              season,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REQUESTED', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(requested_track or "").strip(),
                owned_id,
                str(matched_track_title or "").strip() or None,
                int(matched_track_no) if matched_track_no else None,
                item_title,
                artist_or_brand,
                cover_image_url,
                category,
                location.get("current_slot_code") if location else None,
                location.get("current_slot_display_name") if location else None,
                location.get("previous_slot_code") if location else None,
                location.get("previous_slot_display_name") if location else None,
                str(customer_note or "").strip() or None,
                str(requested_by or "").strip() or None,
                weather_temp_c,
                weather_description,
                weather_code,
                resolved_season,
                now,
                now,
            ),
        )
        request_id = int(cur.lastrowid or 0)
    return get_customer_track_request(request_id) or {}


def get_customer_track_request(request_id: int) -> dict[str, Any] | None:
    rows = list_customer_track_requests(status=None, limit=1, request_id=int(request_id))
    return rows[0] if rows else None


def list_customer_track_requests(
    status: str | None = None,
    limit: int = 100,
    request_id: int | None = None,
) -> list[dict[str, Any]]:
    where_parts = ["1=1"]
    params: list[Any] = []
    if status and str(status).strip():
        where_parts.append("ctr.status = ?")
        params.append(str(status).strip().upper())
    if request_id is not None:
        where_parts.append("ctr.id = ?")
        params.append(int(request_id))
    where_sql = " AND ".join(where_parts)

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
              ctr.*,
              oi.category AS live_category,
              COALESCE(oi.item_name_override, am.title, ctr.item_title_snapshot) AS live_item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, ctr.artist_or_brand_snapshot) AS live_artist_or_brand,
              COALESCE(mid.cover_image_url, ctr.cover_image_url_snapshot) AS live_cover_image_url,
              ss.slot_code AS current_live_slot_code,
              ss.cabinet_name AS current_live_cabinet_name,
              ss.column_code AS current_live_column_code,
              ss.cell_code AS current_live_cell_code,
              ss.allowed_size_group AS current_live_allowed_size_group,
              ss.is_overflow_zone AS current_live_is_overflow_zone
            FROM customer_track_request ctr
            LEFT JOIN owned_item oi ON oi.id = ctr.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE {where_sql}
            ORDER BY ctr.created_at DESC, ctr.id DESC
            LIMIT ?
            """,
            [*params, max(1, int(limit))],
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        live_slot_display = None
        if item.get("current_live_slot_code"):
            live_slot_display = _storage_slot_display_name(
                {
                    "slot_code": item.get("current_live_slot_code"),
                    "cabinet_name": item.get("current_live_cabinet_name"),
                    "column_code": item.get("current_live_column_code"),
                    "cell_code": item.get("current_live_cell_code"),
                    "allowed_size_group": item.get("current_live_allowed_size_group"),
                    "is_overflow_zone": item.get("current_live_is_overflow_zone"),
                }
            )
        item["item_title"] = str(item.get("item_title_snapshot") or item.get("live_item_title") or "").strip() or None
        item["artist_or_brand"] = str(item.get("artist_or_brand_snapshot") or item.get("live_artist_or_brand") or "").strip() or None
        item["cover_image_url"] = str(item.get("cover_image_url_snapshot") or item.get("live_cover_image_url") or "").strip() or None
        category = str(item.get("live_category") or item.get("category_snapshot") or "").strip() or None
        item["category"] = category
        owned_item_id = int(item.get("owned_item_id") or 0)
        item["label_id"] = _build_label_id(category, owned_item_id) if category and owned_item_id > 0 else None
        item["current_live_slot_display_name"] = live_slot_display
        out.append(item)
    return out


def count_customer_track_requests(status: str | None = None) -> int:
    where_sql = ""
    params: list[Any] = []
    if status and str(status).strip():
        where_sql = " WHERE status = ?"
        params.append(str(status).strip().upper())
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM customer_track_request{where_sql}",
            params,
        ).fetchone()
    return int(row["cnt"] or 0) if row else 0


def update_customer_track_request(
    request_id: int,
    status: str | None = None,
    response_note: str | None = None,
    handled_by: str | None = None,
    playback_deck: str | None = None,
) -> dict[str, Any] | None:
    request_row = get_customer_track_request(int(request_id))
    if request_row is None:
        return None
    next_status = str(status or request_row.get("status") or "REQUESTED").strip().upper()
    next_note = str(response_note or "").strip() or None
    now = utc_now_iso()
    handled_at = request_row.get("handled_at")
    if next_status in {"PLAYING", "RETURNED", "CANCELLED"}:
        handled_at = now

    played_at = request_row.get("played_at")
    returned_at = request_row.get("returned_at")
    next_deck = playback_deck if playback_deck is not None else request_row.get("playback_deck")

    if next_status == "PLAYING" and status == "PLAYING":
        played_at = now
    if next_status == "RETURNED" and status == "RETURNED":
        returned_at = now

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE customer_track_request
            SET status = ?,
                response_note = ?,
                handled_by = ?,
                handled_at = ?,
                playback_deck = ?,
                played_at = ?,
                returned_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_note,
                str(handled_by or "").strip() or request_row.get("handled_by"),
                handled_at,
                next_deck,
                played_at,
                returned_at,
                now,
                int(request_id),
            ),
        )
    return get_customer_track_request(int(request_id))


__all__ = [
    "create_customer_track_request",
    "get_customer_track_request",
    "list_customer_track_requests",
    "count_customer_track_requests",
    "update_customer_track_request",
]
