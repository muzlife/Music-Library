"""Owned-item track-list / location-snapshot read surface.

Twenty-fifth slice extracted from the legacy `app/db.py`. Owns two
read-only queries on `owned_item` that are pulled by other
modules' module-load-time imports.

Public exports
  * get_owned_item_location_snapshot — for an owned_item id, return
    the joined storage_slot row plus a friendly slot display name.
    Used by `customer_track_request.list_customer_track_requests`
    AND `owned_item_slot.restore_owned_item_previous_slot` — both
    import this at module-load time.
  * get_owned_item_track_list — for an owned_item id, return the
    parsed track list from its music_item_detail row.

Cross-package dependencies kept on the package surface
  * `_storage_slot_display_name` — cross-cutting sort/display
    helper, stays in __init__.py. The submodule pulls it via the
    package surface.

Re-export ordering invariant
  owned_item_track MUST be re-exported BEFORE customer_track_request
  AND BEFORE owned_item_slot, because both of those modules import
  `get_owned_item_location_snapshot` from the package surface at
  module-load time. The Phase 25 test pins this.

`app/db/__init__.py` re-exports both public symbols so existing
callers keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _storage_slot_display_name,
    get_conn,
)


def get_owned_item_location_snapshot(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              oi.id,
              oi.storage_slot_id,
              ss.slot_code,
              ss.cabinet_name,
              ss.column_code,
              ss.cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              (
                SELECT e.from_slot_code
                FROM owned_item_location_event e
                WHERE e.owned_item_id = oi.id
                  AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
              ) AS previous_slot_code,
              (
                SELECT e.from_slot_display_name
                FROM owned_item_location_event e
                WHERE e.owned_item_id = oi.id
                  AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
              ) AS previous_slot_display_name
            FROM owned_item oi
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.id = ?
            LIMIT 1
            """,
            (int(owned_item_id),),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    current_display_name = "미배치"
    if data.get("storage_slot_id") is not None:
        current_display_name = _storage_slot_display_name(
            {
                "slot_code": data.get("slot_code"),
                "cabinet_name": data.get("cabinet_name"),
                "column_code": data.get("column_code"),
                "cell_code": data.get("cell_code"),
                "allowed_size_group": data.get("allowed_size_group"),
                "is_overflow_zone": data.get("is_overflow_zone"),
            }
        )
    return {
        "current_slot_code": data.get("slot_code"),
        "current_slot_display_name": current_display_name,
        "previous_slot_code": str(data.get("previous_slot_code") or "").strip() or None,
        "previous_slot_display_name": str(data.get("previous_slot_display_name") or "").strip() or None,
    }


def get_owned_item_track_list(owned_item_id: int) -> list[str]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT track_list_json
            FROM music_item_detail
            WHERE owned_item_id = ?
            """,
            (owned_item_id,),
        ).fetchone()

    if row is None or row["track_list_json"] is None:
        return []

    raw = str(row["track_list_json"])
    if not raw.strip():
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


__all__ = [
    "get_owned_item_location_snapshot",
    "get_owned_item_track_list",
]
