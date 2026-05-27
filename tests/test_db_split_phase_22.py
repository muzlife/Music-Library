"""Pin the twenty-second slice of the db.py → app/db/ package split.

  * `app.db.owned_item_copy_group` exposes the trio of small queries
    on `owned_item` for copy-group / source-external-id lookups —
    `set_owned_item_copy_group`, `list_owned_items_by_copy_group`,
    `list_owned_items_by_source_external_ids`.
  * `app.db` re-exports every public symbol so existing call sites
    (operator detail screen, metadata-sync providers, the test
    suite) keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import owned_item_copy_group as ocg_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "set_owned_item_copy_group",
    "list_owned_items_by_copy_group",
    "list_owned_items_by_source_external_ids",
)


def test_owned_item_copy_group_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(ocg_module, name)]
    assert not missing, f"app.db.owned_item_copy_group missing: {missing}"


def test_db_package_reexports_copy_group_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ocg_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_copy_group.{name}"
        )


def test_init_py_no_longer_redefines_copy_group_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_copy_group.py"
        )


def test_owned_item_helpers_still_in_init_py() -> None:
    """`_normalize_owned_item_row` and `_owned_item_select_query` are
    cross-cutting helpers used by every owned_item read. They MUST
    remain reachable."""
    assert hasattr(db, "_normalize_owned_item_row")
    assert hasattr(db, "_owned_item_select_query")


def test_legacy_copy_group_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        list_owned_items_by_copy_group,
        list_owned_items_by_source_external_ids,
        set_owned_item_copy_group,
    )


def test_set_copy_group_returns_false_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    # set_owned_item_copy_group: rowcount-based contract
    # Calling on a missing id returns False.
    result = db.set_owned_item_copy_group(-99999, "phase-22-probe-key")
    assert result is False


def test_list_by_copy_group_returns_empty_for_unknown_key() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_copy_group("phase-22-never-used-key")
    assert rows == []


def test_list_by_source_external_ids_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_source_external_ids(
        "DISCOGS",
        ["phase-22-fake-master-id-1", "phase-22-fake-master-id-2"],
    )
    assert rows == []


def test_list_by_source_external_ids_handles_empty_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_source_external_ids("DISCOGS", [])
    assert rows == []


def test_set_copy_group_round_trip() -> None:
    """Round trip — create temp owned_item, set copy_group_key,
    verify via list_owned_items_by_copy_group, clear via None,
    verify cleared. Cleanup at the end."""
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
                        'phase-22 copy-group probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        copy_key = "phase-22-round-trip-key"
        ok = db.set_owned_item_copy_group(owned_item_id, copy_key)
        assert ok is True

        listed = db.list_owned_items_by_copy_group(copy_key)
        assert any(int(r.get("id") or 0) == owned_item_id for r in listed)

        # Clear via None.
        ok2 = db.set_owned_item_copy_group(owned_item_id, None)
        assert ok2 is True
        assert db.list_owned_items_by_copy_group(copy_key) == [] or all(
            int(r.get("id") or 0) != owned_item_id for r in db.list_owned_items_by_copy_group(copy_key)
        )
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
