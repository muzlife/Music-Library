"""Owned-item slot / location-event DB surface.

Twenty-third slice extracted from the legacy `app/db.py`. Owns the
slot-management write path on `owned_item.storage_slot_id` plus
the location-event audit trail that records every move.

Public exports
  * update_owned_item_slot — single-column write that rebinds an
    owned_item to a different storage_slot (or unbinds with None).
    Logs a location_event to the audit trail.
  * inherit_owned_item_domain_from_slot_if_missing — when an item
    is dropped into a cabinet whose `cabinet_domain_code` is set,
    inherit that domain onto the item if the item itself has none.
  * restore_owned_item_previous_slot — rolls back to the most
    recent location_event with a non-null `from_storage_slot_id`.
    Operator-facing "undo last move" button.

Module-private helpers
  * _location_slot_snapshot_in_conn — render a (slot_id, slot_code,
    cabinet_name, cabinet_domain_code) snapshot dict. Used by both
    the move log and the listing/dashboard surfaces.
  * _derive_location_movement_kind — classify a move (NEW_SLOT,
    SAME_SLOT, UNLINK, REMOVE) based on (from_id, to_id) pair.
  * _log_owned_item_location_event_in_conn — INSERT into
    `owned_item_location_event`. Called by update_owned_item_slot
    here AND by `insert_owned_item` / `update_owned_item` (still in
    `__init__.py`) — those resolve the helper via the package
    surface at call time.

Cross-package dependencies kept on the package surface
  * `_normalize_domain_code_value`, `_storage_slot_display_name` —
    cross-cutting helpers used 25+ / 10+ times across the package.
  * `get_owned_item_location_snapshot` — public read still in
    __init__.py, used by `restore_owned_item_previous_slot` here.

`app/db/__init__.py` re-exports every public + the helper symbols
so `insert_owned_item` / `update_owned_item` resolve
`_log_owned_item_location_event_in_conn` correctly at call time.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_domain_code_value,
    _storage_slot_display_name,
    get_conn,
    get_owned_item_location_snapshot,
    utc_now_iso,
)


def _location_slot_snapshot_in_conn(conn: sqlite3.Connection, storage_slot_id: int | None) -> dict[str, Any]:
    if storage_slot_id is None:
        return {
            "storage_slot_id": None,
            "slot_code": "UNASSIGNED",
            "display_name": "미배치",
        }

    row = conn.execute(
        """
        SELECT id, slot_code, cabinet_name, column_code, cell_code, allowed_size_group, is_overflow_zone
        FROM storage_slot
        WHERE id = ?
        LIMIT 1
        """,
        (int(storage_slot_id),),
    ).fetchone()
    if row is None:
        slot_id = int(storage_slot_id)
        return {
            "storage_slot_id": slot_id,
            "slot_code": f"DELETED-{slot_id}",
            "display_name": f"삭제 슬롯 #{slot_id}",
        }

    data = dict(row)
    return {
        "storage_slot_id": int(data["id"]),
        "slot_code": str(data["slot_code"] or ""),
        "display_name": _storage_slot_display_name(data),
    }


def _derive_location_movement_kind(
    from_storage_slot_id: int | None,
    to_storage_slot_id: int | None,
    is_create: bool = False,
) -> str | None:
    if from_storage_slot_id == to_storage_slot_id:
        return None
    if from_storage_slot_id is None and to_storage_slot_id is not None:
        return "INITIAL_ASSIGN" if is_create else "ASSIGN"
    if from_storage_slot_id is not None and to_storage_slot_id is None:
        return "UNASSIGN"
    if from_storage_slot_id is not None and to_storage_slot_id is not None:
        return "MOVE"
    return None


def _log_owned_item_location_event_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    from_storage_slot_id: int | None,
    to_storage_slot_id: int | None,
    movement_kind: str | None = None,
    note: str | None = None,
    now: str | None = None,
    is_create: bool = False,
) -> None:
    kind = movement_kind or _derive_location_movement_kind(
        from_storage_slot_id=from_storage_slot_id,
        to_storage_slot_id=to_storage_slot_id,
        is_create=is_create,
    )
    if kind is None:
        return

    from_snapshot = _location_slot_snapshot_in_conn(conn, from_storage_slot_id)
    to_snapshot = _location_slot_snapshot_in_conn(conn, to_storage_slot_id)
    timestamp = now or utc_now_iso()
    note_text = str(note).strip() if note is not None else ""
    conn.execute(
        """
        INSERT INTO owned_item_location_event (
          owned_item_id,
          from_storage_slot_id,
          from_slot_code,
          from_slot_display_name,
          to_storage_slot_id,
          to_slot_code,
          to_slot_display_name,
          movement_kind,
          note,
          created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            owned_item_id,
            from_snapshot["storage_slot_id"],
            from_snapshot["slot_code"],
            from_snapshot["display_name"],
            to_snapshot["storage_slot_id"],
            to_snapshot["slot_code"],
            to_snapshot["display_name"],
            kind,
            note_text or None,
            timestamp,
        ),
    )


def update_owned_item_slot(owned_item_id: int, storage_slot_id: int | None, movement_note: str | None = None) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT storage_slot_id, display_rank FROM owned_item WHERE id = ? LIMIT 1",
            (owned_item_id,),
        ).fetchone()
        previous_storage_slot_id = row["storage_slot_id"] if row is not None else None
        previous_display_rank = row["display_rank"] if row is not None else None
        now = utc_now_iso()
        next_display_rank = previous_display_rank if previous_storage_slot_id == storage_slot_id else None
        conn.execute(
            """
            UPDATE owned_item
            SET storage_slot_id = ?, display_rank = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_slot_id, next_display_rank, now, owned_item_id),
        )
        if row is not None and previous_storage_slot_id != storage_slot_id:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=int(previous_storage_slot_id) if previous_storage_slot_id is not None else None,
                to_storage_slot_id=int(storage_slot_id) if storage_slot_id is not None else None,
                note=movement_note,
                now=now,
            )


def inherit_owned_item_domain_from_slot_if_missing(owned_item_id: int, storage_slot_id: int | None) -> str | None:
    if storage_slot_id is None:
        return None
    with get_conn() as conn:
        owned_row = conn.execute(
            "SELECT domain_code FROM owned_item WHERE id = ? LIMIT 1",
            (int(owned_item_id),),
        ).fetchone()
        if owned_row is None:
            return None
        current_domain_code = _normalize_domain_code_value(owned_row["domain_code"])
        if current_domain_code not in (None, "UNKNOWN"):
            return current_domain_code
        slot_row = conn.execute(
            "SELECT cabinet_domain_code FROM storage_slot WHERE id = ? LIMIT 1",
            (int(storage_slot_id),),
        ).fetchone()
        inherited_domain_code = _normalize_domain_code_value(slot_row["cabinet_domain_code"]) if slot_row is not None else None
        if inherited_domain_code in (None, "UNKNOWN"):
            return current_domain_code
        conn.execute(
            "UPDATE owned_item SET domain_code = ?, updated_at = ? WHERE id = ?",
            (inherited_domain_code, utc_now_iso(), int(owned_item_id)),
        )
        return inherited_domain_code


def restore_owned_item_previous_slot(owned_item_id: int) -> dict[str, Any] | None:
    row = get_owned_item_location_snapshot(int(owned_item_id))
    if row is None:
        return None
    previous_slot_code = str(row.get("previous_slot_code") or "").strip()
    if not previous_slot_code:
        return {"owned_item_id": int(owned_item_id), "storage_slot_id": None, "restored": False, "reason": "이전 위치 이력이 없습니다."}
    next_slot_id: int | None = None
    if previous_slot_code != "UNASSIGNED":
        slot = get_storage_slot_by_code(previous_slot_code)
        if slot is None:
            return {"owned_item_id": int(owned_item_id), "restored": False, "reason": "이전 위치 칸을 찾지 못했습니다."}
        next_slot_id = int(slot["id"])
    update_owned_item_slot(int(owned_item_id), next_slot_id, movement_note="직전 위치 복구")
    return {"owned_item_id": int(owned_item_id), "storage_slot_id": next_slot_id, "restored": True}


__all__ = [
    "_location_slot_snapshot_in_conn",
    "_derive_location_movement_kind",
    "_log_owned_item_location_event_in_conn",
    "update_owned_item_slot",
    "inherit_owned_item_domain_from_slot_if_missing",
    "restore_owned_item_previous_slot",
]
