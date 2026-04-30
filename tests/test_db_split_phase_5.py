"""Pin the fifth slice of the db.py → app/db/ package split.

  * `app.db.storage_slot` exposes the storage-slot CRUD + cabinet
    register/delete + the migration helpers it owns
    (_storage_slot_allows_goods, _migrate_storage_slot_allow_goods,
    _cleanup_overflow_slots, _derive_storage_slot_parts).
  * `app.db` re-exports every public + module-private symbol so existing
    call sites (the dashboard router, /storage-slots/* routes, the
    init_db / ensure_startup_db_ready chain) continue to work unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import storage_slot as ss_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_storage_slot",
    "get_storage_slot_by_code",
    "list_storage_slots",
    "list_owned_items_for_storage_slot",
    "upsert_storage_slot",
    "register_storage_cabinet_slots",
    "delete_storage_cabinet",
)
_INTERNAL_SYMBOLS = (
    "_storage_slot_allows_goods",
    "_migrate_storage_slot_allow_goods",
    "_cleanup_overflow_slots",
    "_derive_storage_slot_parts",
)


def test_storage_slot_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(ss_module, name)]
    assert not missing, f"app.db.storage_slot missing: {missing}"


def test_db_package_reexports_storage_slot_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ss_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.storage_slot.{name}"
        )


def test_init_py_no_longer_redefines_storage_slot_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/storage_slot.py"
        )


def test_legacy_storage_slot_paths_still_work() -> None:
    """Surfaces consumed by the dashboard router, the storage-slot routes,
    and the init/migration chain must keep resolving."""
    from app.db import (  # noqa: F401
        _cleanup_overflow_slots,
        _derive_storage_slot_parts,
        _migrate_storage_slot_allow_goods,
        _storage_slot_allows_goods,
        delete_storage_cabinet,
        get_storage_slot,
        get_storage_slot_by_code,
        list_owned_items_for_storage_slot,
        list_storage_slots,
        register_storage_cabinet_slots,
        upsert_storage_slot,
    )


def test_storage_slot_cross_cutting_helpers_remain_in_init() -> None:
    """`_storage_slot_display_name`, `_natural_sort_key`,
    `_contains_any_token`, `_storage_slot_sort_key`,
    `_compose_storage_slot_code` are intentionally NOT in the
    storage_slot submodule — they're shared with other slices that
    haven't been extracted yet."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for cross_helper in (
        "_storage_slot_display_name",
        "_natural_sort_key",
        "_contains_any_token",
        "_storage_slot_sort_key",
        "_compose_storage_slot_code",
    ):
        pattern = re.compile(rf"^def {re.escape(cross_helper)}\(", re.MULTILINE)
        assert pattern.search(init_src), (
            f"{cross_helper} unexpectedly removed from app/db/__init__.py — "
            f"it must remain there until its dependents are also extracted"
        )


def test_storage_slot_register_and_list_round_trip_through_package_surface() -> None:
    """register a tiny cabinet → list → get → list_items → delete cleanup.
    Uses a unique cabinet name so it doesn't collide with existing data."""
    db.ensure_startup_db_ready()
    cabinet = "phase-5-probe-cabinet"

    # Register a 1x1 cabinet.
    summary = db.register_storage_cabinet_slots(
        cabinet_name=cabinet,
        floor_count=1,
        cell_count=1,
        allowed_size_group="STD",
    )
    assert summary["cabinet_name"] == cabinet

    # List should include it.
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name") == cabinet]
    assert len(slots) == 1
    slot_id = int(slots[0]["id"])
    slot_code = str(slots[0]["slot_code"])

    # get_storage_slot + get_storage_slot_by_code resolve.
    fetched_by_id = db.get_storage_slot(slot_id)
    fetched_by_code = db.get_storage_slot_by_code(slot_code)
    assert fetched_by_id is not None
    assert fetched_by_code is not None
    assert int(fetched_by_id["id"]) == slot_id
    assert int(fetched_by_code["id"]) == slot_id

    # Empty cabinet should report no items.
    items = db.list_owned_items_for_storage_slot(slot_id)
    assert isinstance(items, list)
    assert items == []

    # Cleanup via delete_storage_cabinet (the canonical path).
    result = db.delete_storage_cabinet(cabinet)
    assert int(result.get("removed_slot_count") or 0) == 1
    assert (
        len([item for item in db.list_storage_slots() if item.get("cabinet_name") == cabinet])
        == 0
    )
