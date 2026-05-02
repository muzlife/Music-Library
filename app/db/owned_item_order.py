"""Owned-item display-rank / move-order DB surface.

Twenty-fourth slice extracted from the legacy `app/db.py`. Owns the
operator drag-and-drop order writers on the `owned_item.display_rank`
column inside a single storage_slot.

Public exports
  * move_owned_item_order — re-rank `owned_item_id` to land
    `before` / `after` / `at` of `target_owned_item_id`. Returns
    the new display_rank value as a string.
  * realign_owned_item_order_after_slot_move — when an item is
    moved INTO a different slot, pick a sensible display_rank
    inside the new slot's existing order and call move_owned_item_order
    to insert it there.
  * move_owned_item_slot_display_rank — the higher-level wrapper
    used by the slot-detail UI's "이 위치 안에서 위로/아래로 옮기기"
    buttons.

Cross-package dependencies kept on the package surface
  * `_backfill_order_keys`, `_compute_between_order_value`,
    `_format_order_value`, `_next_order_key_in_conn`,
    `_parse_order_value`, `_rebalance_in_collection_order` — the
    display_rank / order-key helpers, used by other writers (insert,
    update) that stay in `__init__.py`.
  * `_storage_slot_sort_key` — cross-cutting sort helper.
  * `get_owned_item`, `get_conn`, `utc_now_iso` — package surface.

`app/db/__init__.py` re-exports every public symbol so existing
callers (`/owned-items/{id}/order` routes, the operator slot detail
UI, the test suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _backfill_order_keys,
    _compute_between_order_value,
    _format_order_value,
    _next_order_key_in_conn,
    _parse_order_value,
    _rebalance_in_collection_order,
    _storage_slot_sort_key,
    get_conn,
    get_owned_item,
    utc_now_iso,
)


def move_owned_item_order(owned_item_id: int, target_owned_item_id: int, position: str) -> str:
    if owned_item_id == target_owned_item_id:
        raise ValueError("owned_item_id and target_owned_item_id must be different")
    if position not in {"BEFORE", "AFTER"}:
        raise ValueError("position must be BEFORE or AFTER")

    with get_conn() as conn:
        src_row = conn.execute(
            "SELECT id, status FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if src_row is None:
            raise LookupError("owned_item not found")

        target_row = conn.execute(
            "SELECT id, status FROM owned_item WHERE id = ?",
            (target_owned_item_id,),
        ).fetchone()
        if target_row is None:
            raise LookupError("target owned_item not found")

        src_status = str(src_row["status"] or "")
        target_status = str(target_row["status"] or "")
        if src_status != "IN_COLLECTION" or target_status != "IN_COLLECTION":
            raise ValueError("order move is available only for IN_COLLECTION items")

        _backfill_order_keys(conn)

        for _ in range(2):
            rows = conn.execute(
                """
                SELECT id, order_key
                FROM owned_item
                WHERE status = 'IN_COLLECTION'
                  AND id <> ?
                ORDER BY order_key ASC, id ASC
                """,
                (owned_item_id,),
            ).fetchall()

            ordered = [
                {"id": int(r["id"]), "value": _parse_order_value(r["order_key"])}
                for r in rows
            ]
            if any(row["value"] is None for row in ordered):
                _rebalance_in_collection_order(conn)
                continue
            idx = next((i for i, row in enumerate(ordered) if row["id"] == target_owned_item_id), None)
            if idx is None:
                raise LookupError("target owned_item not found in IN_COLLECTION order")

            if position == "BEFORE":
                left = ordered[idx - 1]["value"] if idx > 0 else None
                right = ordered[idx]["value"]
            else:
                left = ordered[idx]["value"]
                right = ordered[idx + 1]["value"] if idx + 1 < len(ordered) else None

            if left is not None and right is not None and left >= right:
                _rebalance_in_collection_order(conn)
                continue

            next_value = _compute_between_order_value(left, right)
            if next_value is None:
                _rebalance_in_collection_order(conn)
                continue

            new_order_key = _format_order_value(next_value)
            conn.execute(
                """
                UPDATE owned_item
                SET order_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_order_key, utc_now_iso(), owned_item_id),
            )
            return new_order_key

    raise RuntimeError("order move failed after rebalance")


def realign_owned_item_order_after_slot_move(owned_item_id: int, target_slot_id: int) -> str:
    target_slot_id = int(target_slot_id)
    moved_row = get_owned_item(owned_item_id)
    if moved_row is None:
        raise LookupError("owned_item not found")
    if str(moved_row.get("status") or "").strip().upper() != "IN_COLLECTION":
        raise ValueError("slot move order realign is available only for IN_COLLECTION items")
    if int(moved_row.get("storage_slot_id") or 0) != target_slot_id:
        raise ValueError("owned_item is not assigned to the target slot")

    target_rows = list_owned_items_for_storage_slot(target_slot_id, limit=1000, offset=0)
    ordered_ids = [int(row["id"]) for row in target_rows if int(row.get("id") or 0) > 0]
    if owned_item_id not in ordered_ids:
        raise LookupError("owned_item not found in target slot order")

    anchor_owned_item_id: int | None = None
    anchor_position: str | None = None
    target_index = ordered_ids.index(owned_item_id)
    if target_index > 0:
        anchor_owned_item_id = ordered_ids[target_index - 1]
        anchor_position = "AFTER"
    elif target_index + 1 < len(ordered_ids):
        anchor_owned_item_id = ordered_ids[target_index + 1]
        anchor_position = "BEFORE"

    if anchor_owned_item_id is None:
        with get_conn() as conn:
            _backfill_order_keys(conn)
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
            slot_order = [int(row["id"]) for row in slot_dicts if row["id"] is not None]
            slot_index = next((idx for idx, slot_id in enumerate(slot_order) if slot_id == target_slot_id), None)

            if slot_index is not None:
                for previous_slot_id in reversed(slot_order[:slot_index]):
                    previous_rows = list_owned_items_for_storage_slot(previous_slot_id, limit=1000, offset=0)
                    previous_ids = [int(row["id"]) for row in previous_rows if int(row.get("id") or 0) > 0]
                    if previous_ids:
                        anchor_owned_item_id = previous_ids[-1]
                        anchor_position = "AFTER"
                        break

            if anchor_owned_item_id is None and slot_index is not None:
                for next_slot_id in slot_order[slot_index + 1 :]:
                    next_rows = list_owned_items_for_storage_slot(next_slot_id, limit=1000, offset=0)
                    next_ids = [int(row["id"]) for row in next_rows if int(row.get("id") or 0) > 0]
                    if next_ids:
                        anchor_owned_item_id = next_ids[0]
                        anchor_position = "BEFORE"
                        break

            if anchor_owned_item_id is None:
                unassigned_row = conn.execute(
                    """
                    SELECT order_key
                    FROM owned_item
                    WHERE status = 'IN_COLLECTION'
                      AND storage_slot_id IS NULL
                      AND id <> ?
                    ORDER BY
                      CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
                      order_key ASC,
                      id ASC
                    LIMIT 1
                    """,
                    (owned_item_id,),
                ).fetchone()
                right_value = _parse_order_value(unassigned_row["order_key"]) if unassigned_row else None
                next_value = _compute_between_order_value(None, right_value)
                if next_value is None and right_value is not None:
                    _rebalance_in_collection_order(conn)
                    refreshed_row = conn.execute(
                        """
                        SELECT order_key
                        FROM owned_item
                        WHERE status = 'IN_COLLECTION'
                          AND storage_slot_id IS NULL
                          AND id <> ?
                        ORDER BY
                          CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
                          order_key ASC,
                          id ASC
                        LIMIT 1
                        """,
                        (owned_item_id,),
                    ).fetchone()
                    refreshed_value = _parse_order_value(refreshed_row["order_key"]) if refreshed_row else None
                    next_value = _compute_between_order_value(None, refreshed_value)
                new_order_key = (
                    _format_order_value(next_value)
                    if next_value is not None
                    else _next_order_key_in_conn(conn)
                )
                conn.execute(
                    """
                    UPDATE owned_item
                    SET order_key = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_order_key, utc_now_iso(), owned_item_id),
                )
                return new_order_key

    if anchor_owned_item_id is None or anchor_position is None:
        raise RuntimeError("slot move order realign failed without anchor")
    return move_owned_item_order(
        owned_item_id=owned_item_id,
        target_owned_item_id=anchor_owned_item_id,
        position=anchor_position,
    )


def move_owned_item_slot_display_rank(
    storage_slot_id: int,
    owned_item_id: int,
    target_owned_item_id: int,
    position: str,
) -> int:
    if owned_item_id == target_owned_item_id:
        raise ValueError("owned_item_id and target_owned_item_id must be different")
    if position not in {"BEFORE", "AFTER"}:
        raise ValueError("position must be BEFORE or AFTER")

    with get_conn() as conn:
        source_row = conn.execute(
            "SELECT id, status, storage_slot_id FROM owned_item WHERE id = ? LIMIT 1",
            (owned_item_id,),
        ).fetchone()
        if source_row is None:
            raise LookupError("owned_item not found")
        target_row = conn.execute(
            "SELECT id, status, storage_slot_id FROM owned_item WHERE id = ? LIMIT 1",
            (target_owned_item_id,),
        ).fetchone()
        if target_row is None:
            raise LookupError("target owned_item not found")

    source_slot_id = int(source_row["storage_slot_id"] or 0) if source_row["storage_slot_id"] is not None else 0
    target_slot_id = int(target_row["storage_slot_id"] or 0) if target_row["storage_slot_id"] is not None else 0
    if source_slot_id <= 0 or target_slot_id <= 0:
        raise ValueError("slot order move is available only for assigned items")
    if source_slot_id != int(storage_slot_id) or target_slot_id != int(storage_slot_id):
        raise ValueError("slot order move is available only within the current slot")
    if str(source_row["status"] or "") != "IN_COLLECTION" or str(target_row["status"] or "") != "IN_COLLECTION":
        raise ValueError("slot order move is available only for IN_COLLECTION items")

    current_rows = list_owned_items_for_storage_slot(int(storage_slot_id), limit=1000, offset=0)
    ordered_ids = [int(row["id"]) for row in current_rows if int(row.get("id") or 0) > 0]
    if owned_item_id not in ordered_ids:
        raise LookupError("owned_item not found in current slot")
    if target_owned_item_id not in ordered_ids:
        raise LookupError("target owned_item not found in current slot")

    ordered_ids = [item_id for item_id in ordered_ids if item_id != owned_item_id]
    target_index = ordered_ids.index(target_owned_item_id)
    insert_index = target_index if position == "BEFORE" else target_index + 1
    ordered_ids.insert(insert_index, owned_item_id)

    now = utc_now_iso()
    display_rank = 0
    with get_conn() as conn:
        for index, item_id in enumerate(ordered_ids, start=1):
            rank_value = index * 10
            conn.execute(
                """
                UPDATE owned_item
                SET display_rank = ?, updated_at = ?
                WHERE id = ?
                """,
                (rank_value, now, item_id),
            )
            if item_id == owned_item_id:
                display_rank = rank_value

    if display_rank <= 0:
        raise RuntimeError("slot order move failed")
    return display_rank


__all__ = [
    "move_owned_item_order",
    "realign_owned_item_order_after_slot_move",
    "move_owned_item_slot_display_rank",
]
