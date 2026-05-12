"""Owned-item display-rank order-key helpers + resequencer.

Thirty-fourth slice extracted from the legacy `app/db.py`. Owns the
fractional-index machinery used by the operator drag-and-drop sort
UI to insert items between existing rows without renumbering the
whole list:

  * _format_order_value / _parse_order_value — fixed-width string
    representation of the integer order key.
  * _next_order_key_in_conn — pick the next key for an item being
    appended to the end of the collection.
  * _backfill_order_keys — one-shot bulk migration helper that
    fills NULL order_key columns for legacy rows.
  * _compute_between_order_value — compute the integer order value
    halfway between two neighbours' keys (the "drag between two
    rows" gesture).
  * _rebalance_in_collection_order — rewrite all order_key values
    to ORDER_KEY_STEP * rank so subsequent inserts have headroom.

Public exports
  * resequence_in_collection_order — operator "정렬 초기화" button.
    Wraps _rebalance_in_collection_order in a transaction and
    returns counts.

Re-export ordering invariant
  order_keys MUST be re-exported BEFORE any consumer slice
  (location_recommendation, owned_item_order, music_shelf_window,
  owned_item_write) — those modules import the helpers from the
  package surface at module-load time.

Cross-package dependencies kept on the package surface
  * `ORDER_KEY_WIDTH`, `ORDER_KEY_STEP` constants in __init__.py.
  * `list_owned_items_for_storage_slot` from storage_slot (Phase 5).
  * `get_conn`, `utc_now_iso`.

`app/db/__init__.py` re-exports every public + the helper symbols
so existing callers (the legacy migration path, the operator
resequence route, and the cross-module consumers above) keep
working unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    ORDER_KEY_STEP,
    ORDER_KEY_WIDTH,
    _storage_slot_sort_key,
    get_conn,
    list_owned_items_for_storage_slot,
    utc_now_iso,
)


def _format_order_value(value: int) -> str:
    safe = value if value > 0 else ORDER_KEY_STEP
    return f"{safe:0{ORDER_KEY_WIDTH}d}"


def _parse_order_value(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _next_order_key_in_conn(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT order_key
        FROM owned_item
        WHERE order_key IS NOT NULL
          AND TRIM(order_key) <> ''
        ORDER BY order_key DESC
        LIMIT 1
        """
    ).fetchone()
    value = _parse_order_value(row["order_key"]) if row else None
    base = value if value is not None else 0
    return _format_order_value(base + ORDER_KEY_STEP)


def _backfill_order_keys(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id
        FROM owned_item
        WHERE status = 'IN_COLLECTION'
          AND (order_key IS NULL OR TRIM(order_key) = '')
        ORDER BY
          CASE WHEN display_rank IS NULL THEN 1 ELSE 0 END,
          display_rank ASC,
          created_at ASC,
          id ASC
        """
    ).fetchall()
    if not rows:
        return

    next_key = _next_order_key_in_conn(conn)
    next_value = _parse_order_value(next_key)
    if next_value is None:
        next_value = ORDER_KEY_STEP

    now = utc_now_iso()
    for row in rows:
        conn.execute(
            """
            UPDATE owned_item
            SET order_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (_format_order_value(next_value), now, int(row["id"])),
        )
        next_value += ORDER_KEY_STEP


def _compute_between_order_value(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return ORDER_KEY_STEP
    if left is None:
        if right is None:
            return ORDER_KEY_STEP
        candidate = right // 2
        if candidate <= 0 or candidate >= right:
            return None
        return candidate
    if right is None:
        return left + ORDER_KEY_STEP
    gap = right - left
    if gap <= 1:
        return None
    return left + (gap // 2)


def _rebalance_in_collection_order(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id
        FROM owned_item
        WHERE status = 'IN_COLLECTION'
        ORDER BY
          CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
          order_key ASC,
          CASE WHEN display_rank IS NULL THEN 1 ELSE 0 END,
          display_rank ASC,
          created_at ASC,
          id ASC
        """
    ).fetchall()
    now = utc_now_iso()
    value = 0
    for row in rows:
        value += ORDER_KEY_STEP
        conn.execute(
            """
            UPDATE owned_item
            SET order_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (_format_order_value(value), now, int(row["id"])),
        )


def resequence_in_collection_order() -> dict[str, int]:
    with get_conn() as conn:
        slot_rows = conn.execute(
            """
            SELECT DISTINCT ss.*
            FROM storage_slot ss
            JOIN owned_item oi ON oi.storage_slot_id = ss.id
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.storage_slot_id IS NOT NULL
            """
        ).fetchall()
        slot_dicts = [dict(row) for row in slot_rows]
        slot_dicts.sort(key=_storage_slot_sort_key)

        ordered_ids: list[int] = []
        for slot in slot_dicts:
            rows = list_owned_items_for_storage_slot(int(slot["id"]))
            ordered_ids.extend(int(row["id"]) for row in rows if int(row.get("id") or 0) > 0)

        unassigned_rows = conn.execute(
            """
            SELECT id
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NULL
            ORDER BY
              CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
              order_key ASC,
              id ASC
            """
        ).fetchall()
        ordered_ids.extend(int(row["id"]) for row in unassigned_rows if int(row["id"] or 0) > 0)

        now = utc_now_iso()
        value = 0
        for owned_item_id in ordered_ids:
            value += ORDER_KEY_STEP
            conn.execute(
                """
                UPDATE owned_item
                SET order_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (_format_order_value(value), now, owned_item_id),
            )

    return {
        "reordered_count": len(ordered_ids),
        "assigned_slot_count": len(slot_dicts),
        "unassigned_tail_count": len(unassigned_rows),
    }


__all__ = [
    "_format_order_value",
    "_parse_order_value",
    "_next_order_key_in_conn",
    "_backfill_order_keys",
    "_compute_between_order_value",
    "_rebalance_in_collection_order",
    "resequence_in_collection_order",
]
