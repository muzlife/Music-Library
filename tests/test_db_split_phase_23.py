"""Pin the twenty-third slice of the db.py → app/db/ package split.

  * `app.db.owned_item_slot` exposes the slot-management write path
    + location-event audit trail — `update_owned_item_slot`,
    `inherit_owned_item_domain_from_slot_if_missing`,
    `restore_owned_item_previous_slot`, and the three private
    helpers (`_location_slot_snapshot_in_conn`,
    `_derive_location_movement_kind`,
    `_log_owned_item_location_event_in_conn`).
  * `app.db` re-exports every public + the helper symbols. The
    `_log_owned_item_location_event_in_conn` re-export is critical
    — `insert_owned_item` and `update_owned_item` (still in
    __init__.py) call it by bare name and resolve via the package
    surface at call time. AND `storage_slot.py` imports it at
    module-load time, which is why owned_item_slot MUST be
    re-exported BEFORE storage_slot in __init__.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import owned_item_slot as ois_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "update_owned_item_slot",
    "inherit_owned_item_domain_from_slot_if_missing",
    "restore_owned_item_previous_slot",
)
_INTERNAL_SYMBOLS = (
    "_location_slot_snapshot_in_conn",
    "_derive_location_movement_kind",
    "_log_owned_item_location_event_in_conn",
)


def test_owned_item_slot_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(ois_module, name)]
    assert not missing, f"app.db.owned_item_slot missing: {missing}"


def test_db_package_reexports_owned_item_slot_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ois_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_slot.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_slot_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_slot.py"
        )


def test_reexport_ordering_owned_item_slot_before_storage_slot() -> None:
    """Critical invariant — owned_item_slot re-export MUST appear
    BEFORE storage_slot re-export in __init__.py. Otherwise
    storage_slot.py fails to import at package-load time because it
    pulls `_log_owned_item_location_event_in_conn` from the package
    surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    slot_pos = init_src.find("from .owned_item_slot import")
    storage_pos = init_src.find("from .storage_slot import")
    assert slot_pos > 0, "owned_item_slot re-export missing from __init__.py"
    assert storage_pos > 0, "storage_slot re-export missing from __init__.py"
    assert slot_pos < storage_pos, (
        "owned_item_slot re-export MUST come BEFORE storage_slot — "
        "storage_slot.py imports _log_owned_item_location_event_in_conn "
        "from app.db at module-load time."
    )


def test_storage_slot_resolves_log_helper_through_package_surface() -> None:
    """The storage_slot module's import of
    `_log_owned_item_location_event_in_conn` from app.db MUST land
    on the same callable that owned_item_slot defines."""
    from app.db import storage_slot as ss_module
    assert ss_module._log_owned_item_location_event_in_conn is db._log_owned_item_location_event_in_conn
    assert ss_module._log_owned_item_location_event_in_conn is ois_module._log_owned_item_location_event_in_conn


def test_legacy_owned_item_slot_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        inherit_owned_item_domain_from_slot_if_missing,
        restore_owned_item_previous_slot,
        update_owned_item_slot,
    )


def test_inherit_domain_returns_none_for_invalid_inputs() -> None:
    """Read contract — non-positive owned_item_id or None storage_slot_id
    should not raise."""
    db.ensure_startup_db_ready()
    assert db.inherit_owned_item_domain_from_slot_if_missing(0, None) is None
    assert db.inherit_owned_item_domain_from_slot_if_missing(-1, None) is None
    assert db.inherit_owned_item_domain_from_slot_if_missing(-99999, None) is None


def test_restore_previous_slot_returns_none_for_unknown() -> None:
    """Write contract — restoring a slot for an owned_item with no
    location history must return None, not raise."""
    db.ensure_startup_db_ready()
    result = db.restore_owned_item_previous_slot(-99999)
    assert result is None


def test_update_slot_no_op_when_already_unassigned() -> None:
    """When the from-slot equals the to-slot (both None for a fresh
    owned_item), update_owned_item_slot is a no-op — the column
    stays at None and no location_event row is logged. This pins the
    `kind is None` short-circuit inside _log_owned_item_location_event_in_conn."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1,
                        'phase-23 slot probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        db.update_owned_item_slot(owned_item_id, None, movement_note="phase-23 probe")

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT storage_slot_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
            assert row is not None
            assert row["storage_slot_id"] is None
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item_location_event WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))


def test_derive_movement_kind_classifies_pairs() -> None:
    """Pin the classification contract:
      from == to                              → None (no-op, no log)
      None → some_id                          → "ASSIGN" / "INITIAL_ASSIGN"
      some_id → None                          → "UNASSIGN"
      some_id → other_id                      → "MOVE"
    """
    # Same-slot no-op.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=5
    ) is None
    # None → set: ASSIGN (or INITIAL_ASSIGN with is_create=True).
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=7
    ) == "ASSIGN"
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=7, is_create=True
    ) == "INITIAL_ASSIGN"
    # set → None: UNASSIGN.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=None
    ) == "UNASSIGN"
    # set → different set: MOVE.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=7
    ) == "MOVE"
    # Both None — no-op.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=None
    ) is None
