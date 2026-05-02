"""Pin the twenty-sixth slice of the db.py → app/db/ package split.

  * `app.db.owned_item_read` exposes two single-row read queries —
    `get_owned_item` (bare row SELECT) and `get_owned_item_detail`
    (joined SELECT + normalisation pass).
  * `app.db` re-exports both. Critical: customer_track_request
    (Phase 4) imports `get_owned_item_detail` at module-load time
    and owned_item_order (Phase 24) imports `get_owned_item` at
    module-load time, so owned_item_read MUST be re-exported BEFORE
    both of them.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import customer_track_request as ctr_module
from app.db import owned_item_order as oio_module
from app.db import owned_item_read as oir_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_owned_item",
    "get_owned_item_detail",
)


def test_owned_item_read_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(oir_module, name)]
    assert not missing, f"app.db.owned_item_read missing: {missing}"


def test_db_package_reexports_owned_item_read_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(oir_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_read.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_read_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_read.py"
        )


def test_reexport_ordering_owned_item_read_before_dependents() -> None:
    """Critical invariant — owned_item_read re-export MUST appear
    BEFORE customer_track_request AND BEFORE owned_item_order."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    read_pos = init_src.find("from .owned_item_read import")
    ctr_pos = init_src.find("from .customer_track_request import")
    oio_pos = init_src.find("from .owned_item_order import")
    assert read_pos > 0, "owned_item_read re-export missing from __init__.py"
    assert ctr_pos > 0, "customer_track_request re-export missing"
    assert oio_pos > 0, "owned_item_order re-export missing"
    assert read_pos < ctr_pos, (
        "owned_item_read MUST come BEFORE customer_track_request — "
        "customer_track_request.py imports get_owned_item_detail "
        "from app.db at module-load time."
    )
    assert read_pos < oio_pos, (
        "owned_item_read MUST come BEFORE owned_item_order — "
        "owned_item_order.py imports get_owned_item from app.db "
        "at module-load time."
    )


def test_dependent_modules_resolve_through_package_surface() -> None:
    """customer_track_request and owned_item_order must hold the
    same callable as the package surface at module-load time."""
    assert ctr_module.get_owned_item_detail is db.get_owned_item_detail
    assert oio_module.get_owned_item is db.get_owned_item


def test_owned_item_helpers_still_in_init_py() -> None:
    """`_owned_item_select_query` and `_normalize_owned_item_row`
    are cross-cutting helpers used by every owned_item read; they
    stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _owned_item_select_query(" in init_src
    assert "def _normalize_owned_item_row(" in init_src


def test_legacy_owned_item_read_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        get_owned_item,
        get_owned_item_detail,
    )


def test_get_owned_item_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item(-99999) is None


def test_get_owned_item_detail_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_detail(-99999) is None


def test_get_owned_item_round_trip() -> None:
    """Insert a temp owned_item, read both via get_owned_item and
    get_owned_item_detail, verify both return the same id. Cleanup."""
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
                        'phase-26 read probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        bare = db.get_owned_item(owned_item_id)
        detail = db.get_owned_item_detail(owned_item_id)

        assert bare is not None
        assert detail is not None
        assert int(bare["id"]) == owned_item_id
        assert int(detail["id"]) == owned_item_id
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
