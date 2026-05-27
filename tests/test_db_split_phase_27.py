"""Pin the twenty-seventh slice of the db.py → app/db/ package split.

  * `app.db.owned_item_write` exposes the heart of the operator
    owned-item write path — `insert_owned_item`, `update_owned_item`,
    `bulk_update_owned_items`, `delete_owned_item`, plus the private
    `_sync_owned_item_classifications_in_conn` helper.
  * `app.db` re-exports every public symbol so existing call sites
    (`/owned-items/...` write routes, the operator detail form, the
    bulk-edit modal, the test suite) keep working unchanged.

Re-export ordering invariant
  owned_item_write MUST be re-exported AFTER its cross-module
  dependencies (album_master_core, owned_item_slot,
  owned_item_copy_group, owned_item_track). The natural place is
  the very END of the bottom-of-file re-export block.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import owned_item_write as oiw_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "insert_owned_item",
    "update_owned_item",
    "bulk_update_owned_items",
    "delete_owned_item",
)
_INTERNAL_SYMBOLS = ("_sync_owned_item_classifications_in_conn",)


def test_owned_item_write_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(oiw_module, name)]
    assert not missing, f"app.db.owned_item_write missing: {missing}"


def test_db_package_reexports_owned_item_write_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(oiw_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_write.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_write_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_write.py"
        )


def test_reexport_ordering_owned_item_write_is_last() -> None:
    """owned_item_write MUST be re-exported AFTER all of its
    cross-module dependencies (album_master_core, owned_item_slot,
    owned_item_copy_group, owned_item_track)."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    write_pos = init_src.find("from .owned_item_write import")
    assert write_pos > 0, "owned_item_write re-export missing from __init__.py"
    for dep in (
        "from .album_master_core import",
        "from .owned_item_slot import",
        "from .owned_item_copy_group import",
        "from .owned_item_track import",
    ):
        dep_pos = init_src.find(dep)
        assert dep_pos > 0, f"missing {dep} re-export"
        assert dep_pos < write_pos, (
            f"owned_item_write must come AFTER {dep!r} — that module "
            f"provides a helper that owned_item_write pulls via the "
            f"package surface at module-load time."
        )


def test_owned_item_helpers_reachable_via_package_surface() -> None:
    """Cross-cutting helpers used by the write path. They must be reachable."""
    for name in (
        "_owned_item_select_query",
        "_normalize_owned_item_row",
        "_upsert_music_item_detail_in_conn",
        "_upsert_goods_item_detail_in_conn",
    ):
        assert hasattr(db, name), (
            f"{name} must remain reachable via the app.db package surface"
        )
    # The order-key helpers moved to order_keys.py at Phase 34.
    # What matters for owned_item_write is they're reachable via
    # `from app.db import ...` at module-load time.
    for name in ("_backfill_order_keys", "_next_order_key_in_conn"):
        assert hasattr(db, name), (
            f"{name} must remain reachable via the app.db package "
            f"surface — owned_item_write imports it at module-load time"
        )


def test_legacy_owned_item_write_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        bulk_update_owned_items,
        delete_owned_item,
        insert_owned_item,
        update_owned_item,
    )


def test_delete_owned_item_returns_false_for_missing_id() -> None:
    """Write contract — delete on a missing id returns False, not raises."""
    db.ensure_startup_db_ready()
    assert db.delete_owned_item(-99999) is False


def _full_owned_item_payload(name: str) -> dict[str, object]:
    """Build a fully-populated payload — `update_owned_item` expects
    every column key to be present (it does a complete column
    re-write, not partial)."""
    return {
        "category": "MUSIC",
        "status": "IN_COLLECTION",
        "quantity": 1,
        "item_name_override": name,
        "size_group": "STD",
        "format_name": None,
        "release_year": None,
        "release_type": None,
        "domain_code": None,
        "country_code": None,
        "language_code": None,
        "is_second_hand": False,
        "condition_grade": None,
        "signature_type": "NONE",
        "source_code": None,
        "source_external_id": None,
        "signed_by": None,
        "signed_at": None,
        "acquisition_date": None,
        "purchase_price": None,
        "currency_code": None,
        "purchase_source": None,
        "memory_note": None,
        "display_rank": None,
        "storage_slot_id": None,
        "thickness_mm": None,
        "notes": None,
    }


def test_update_owned_item_returns_false_for_missing_id() -> None:
    """Write contract — update on a missing id returns False (the
    rowcount-based check)."""
    db.ensure_startup_db_ready()
    result = db.update_owned_item(
        owned_item_id=-99999,
        payload=_full_owned_item_payload("phase-27 missing-id probe"),
    )
    assert result is False


def test_insert_update_delete_round_trip() -> None:
    """Full happy-path round trip — insert → read → update → delete."""
    db.ensure_startup_db_ready()
    payload = _full_owned_item_payload("phase-27 round-trip probe")

    owned_item_id = db.insert_owned_item(payload)
    assert isinstance(owned_item_id, int) and owned_item_id > 0

    try:
        # Read back via Phase 26's get_owned_item.
        bare = db.get_owned_item(owned_item_id)
        assert bare is not None
        assert bare["item_name_override"] == "phase-27 round-trip probe"

        # Update.
        update_payload = _full_owned_item_payload("phase-27 round-trip probe v2")
        ok = db.update_owned_item(owned_item_id, update_payload)
        assert ok is True

        bare2 = db.get_owned_item(owned_item_id)
        assert bare2 is not None
        assert bare2["item_name_override"] == "phase-27 round-trip probe v2"

        # Delete.
        deleted = db.delete_owned_item(owned_item_id)
        assert deleted is True
        assert db.get_owned_item(owned_item_id) is None
        owned_item_id = -1  # mark cleaned up
    finally:
        if owned_item_id > 0:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))


def test_bulk_update_returns_empty_list_for_no_rows() -> None:
    """Smoke — bulk_update with an empty id list shouldn't raise; it
    should return an empty list of updated ids."""
    db.ensure_startup_db_ready()
    result = db.bulk_update_owned_items(
        owned_item_ids=[],
        purchase_source="phase-27 noop probe",
    )
    assert result == []
