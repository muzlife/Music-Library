"""Pin the third slice of the db.py → app/db/ package split.

  * `app.db.purchase_import` exposes the purchase-import queue surface —
    schema, migration, dedupe, CRUD.
  * `app.db` re-exports every public symbol so existing call sites
    (api/purchase_imports.py, /ingest/csv handler, the test suite, the
    legacy `_apply_migrations_legacy` chain) continue to work unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import purchase_import as pi_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "insert_purchase_import_rows",
    "find_purchase_import_duplicate_row",
    "list_purchase_import_rows",
    "has_purchase_import_for_source_ref",
    "count_purchase_import_rows",
    "get_purchase_import_row",
    "update_purchase_import_row",
)
_INTERNAL_SYMBOLS = (
    "_purchase_import_vendor_check_sql",
    "_ensure_purchase_import_queue_table",
    "_purchase_import_queue_allows_file_upload",
    "_purchase_import_queue_allows_extended_vendors",
    "_migrate_purchase_import_queue_allow_file_upload",
    "_purchase_import_cmp_text",
    "_purchase_import_cmp_float",
    "_purchase_import_row_matches_duplicate",
    "_find_purchase_import_duplicate_in_conn",
)


def test_purchase_import_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(pi_module, name)]
    assert not missing, f"app.db.purchase_import missing: {missing}"


def test_db_package_reexports_purchase_import_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(pi_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.purchase_import.{name}"
        )


def test_init_py_no_longer_redefines_purchase_import_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/purchase_import.py"
        )


def test_legacy_purchase_import_paths_still_work() -> None:
    """Surfaces consumed by api/purchase_imports.py, the webhook handler,
    and the migration chain must keep resolving."""
    from app.db import (  # noqa: F401
        _ensure_purchase_import_queue_table,
        _migrate_purchase_import_queue_allow_file_upload,
        count_purchase_import_rows,
        find_purchase_import_duplicate_row,
        get_purchase_import_row,
        has_purchase_import_for_source_ref,
        insert_purchase_import_rows,
        list_purchase_import_rows,
        update_purchase_import_row,
    )


def test_purchase_import_round_trip_through_package_surface() -> None:
    """Insert -> dedupe -> list -> get -> update -> source_ref lookup."""
    db.ensure_startup_db_ready()
    source_ref = "db-split-phase-3-probe"

    created_ids = db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "phase-3-test-item", "quantity": 1}],
        source_ref=source_ref,
    )
    assert len(created_ids) == 1
    queue_id = created_ids[0]

    fetched = db.get_purchase_import_row(queue_id)
    assert fetched is not None
    assert fetched["item_name"] == "phase-3-test-item"

    listed_ids = {row["id"] for row in db.list_purchase_import_rows(limit=200)}
    assert queue_id in listed_ids

    assert db.has_purchase_import_for_source_ref("OTHER", source_ref) is True

    # Dedupe — second insert with same source_ref must NOT create a new row.
    again = db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "phase-3-test-item", "quantity": 1}],
        source_ref=source_ref,
    )
    assert again == []

    # Update queue_status flow.
    updated = db.update_purchase_import_row(queue_id, queue_status="IGNORED")
    assert updated is not None
    assert updated["queue_status"] == "IGNORED"

    # Cleanup so the test row doesn't pollute later tests.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM purchase_import_queue WHERE id = ?", (queue_id,)
        )
