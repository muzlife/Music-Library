"""Music shelf-window + per-source counts DB surface.

Thirty-first slice extracted from the legacy `app/db.py`. Owns two
queries that the operator collection screen pulls when zooming
into a single owned_item:

  * get_music_shelf_window — given one owned_item id and a +/- N
    window size, return the row plus its N neighbours on either
    side, ordered by display_rank inside the storage_slot. Powers
    the operator detail screen's "이 슬롯의 진열 순서" panel.
  * get_owned_counts_by_source — for a given source_code and a
    list of source_external_ids, return how many owned_items are
    bound to each. Used by the metadata-sync admin to dedupe
    incoming candidates against existing rows.

Cross-package dependencies kept on the package surface
  * `_owned_item_select_query`, `_normalize_owned_item_row`,
    `_backfill_order_keys`, `_rebalance_in_collection_order` — all
    cross-cutting helpers; stay in __init__.py.
  * `get_owned_item_list_row` — lives in
    `app/db/owned_item_query.py` (Phase 28). The submodule pulls
    it via the package surface.

Re-export ordering invariant
  music_shelf_window MUST be re-exported AFTER owned_item_query
  (which provides get_owned_item_list_row).

`app/db/__init__.py` re-exports both public functions so existing
callers (operator detail screen, metadata-sync dedupe path, the
test suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _backfill_order_keys,
    _normalize_owned_item_row,
    _owned_item_select_query,
    _rebalance_in_collection_order,
    get_conn,
    get_owned_item_list_row,
)


def get_music_shelf_window(owned_item_id: int, window: int) -> dict[str, Any] | None:
    half_window = max(1, int(window))
    with get_conn() as conn:
        _backfill_order_keys(conn)

        selected = conn.execute(
            """
            SELECT id, order_key
            FROM owned_item
            WHERE id = ?
              AND status = 'IN_COLLECTION'
              AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            """,
            (owned_item_id,),
        ).fetchone()
        if selected is None:
            return None

        center_order_key = str(selected["order_key"] or "").strip()
        if not center_order_key:
            _rebalance_in_collection_order(conn)
            selected = conn.execute(
                """
                SELECT id, order_key
                FROM owned_item
                WHERE id = ?
                  AND status = 'IN_COLLECTION'
                  AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                """,
                (owned_item_id,),
            ).fetchone()
            if selected is None:
                return None
            center_order_key = str(selected["order_key"] or "").strip()
            if not center_order_key:
                return None

        prev_row = conn.execute(
            """
            SELECT oi.id
            FROM owned_item oi
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key < ?
                OR (oi.order_key = ? AND oi.id < ?)
              )
            ORDER BY oi.order_key DESC, oi.id DESC
            LIMIT 1
            """,
            (center_order_key, center_order_key, owned_item_id),
        ).fetchone()

        next_row = conn.execute(
            """
            SELECT oi.id
            FROM owned_item oi
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key > ?
                OR (oi.order_key = ? AND oi.id > ?)
              )
            ORDER BY oi.order_key ASC, oi.id ASC
            LIMIT 1
            """,
            (center_order_key, center_order_key, owned_item_id),
        ).fetchone()

        select_query = _owned_item_select_query()

        before_rows = conn.execute(
            select_query
            + """
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key < ?
                OR (oi.order_key = ? AND oi.id < ?)
              )
            ORDER BY oi.order_key DESC, oi.id DESC
            LIMIT ?
            """,
            (center_order_key, center_order_key, owned_item_id, half_window),
        ).fetchall()

        center_row = conn.execute(
            select_query
            + """
            WHERE oi.id = ?
            LIMIT 1
            """,
            (owned_item_id,),
        ).fetchone()
        if center_row is None:
            return None

        after_rows = conn.execute(
            select_query
            + """
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key > ?
                OR (oi.order_key = ? AND oi.id > ?)
              )
            ORDER BY oi.order_key ASC, oi.id ASC
            LIMIT ?
            """,
            (center_order_key, center_order_key, owned_item_id, half_window),
        ).fetchall()

    before_items = [_normalize_owned_item_row(dict(row)) for row in before_rows]
    before_items.reverse()
    center_item = _normalize_owned_item_row(dict(center_row))
    after_items = [_normalize_owned_item_row(dict(row)) for row in after_rows]

    return {
        "center_owned_item_id": int(owned_item_id),
        "previous_owned_item_id": int(prev_row["id"]) if prev_row else None,
        "next_owned_item_id": int(next_row["id"]) if next_row else None,
        "items": [*before_items, center_item, *after_items],
    }


# `get_owned_item_list_row` lives in app/db/owned_item_query.py and is
# re-exported from this package's __init__ at the bottom of the file.


def get_owned_counts_by_source(source_code: str, source_external_ids: list[str]) -> dict[str, int]:
    cleaned = [str(v).strip() for v in source_external_ids if str(v).strip()]
    if not source_code or not cleaned:
        return {}

    placeholders = ",".join("?" for _ in cleaned)
    query = f"""
      SELECT source_external_id, COUNT(*) AS cnt
      FROM owned_item
      WHERE source_code = ?
        AND source_external_id IN ({placeholders})
        AND status IN ('IN_COLLECTION', 'LOANED', 'ARCHIVED')
      GROUP BY source_external_id
    """
    params: list[Any] = [source_code, *cleaned]

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return {str(r["source_external_id"]): int(r["cnt"]) for r in rows}


__all__ = [
    "get_music_shelf_window",
    "get_owned_counts_by_source",
]
