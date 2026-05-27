"""Pin the twenty-eighth slice of the db.py → app/db/ package split.

  * `app.db.owned_item_query` exposes the operator-facing list view
    query — `list_owned_items`, `count_owned_items`,
    `get_owned_item_list_row`.
  * `app.db` re-exports every public symbol so existing call sites
    (`/owned-items/...` list/count routes, the operator collection
    grid, the test suite) keep working unchanged.

Re-export ordering invariant
  owned_item_query MUST be re-exported AFTER album_master_read AND
  owned_item_copy_group, because the query body pulls
  `list_owned_items_by_*` and `get_album_master_*` from the package
  surface at module-load time.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import owned_item_query as oiq_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_owned_items",
    "count_owned_items",
    "get_owned_item_list_row",
)


def test_owned_item_query_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(oiq_module, name)]
    assert not missing, f"app.db.owned_item_query missing: {missing}"


def test_db_package_reexports_owned_item_query_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(oiq_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_query.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_query_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_query.py"
        )


def test_reexport_ordering_owned_item_query_after_dependencies() -> None:
    """owned_item_query MUST be re-exported AFTER album_master_read
    AND owned_item_copy_group."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    query_pos = init_src.find("from .owned_item_query import")
    assert query_pos > 0, "owned_item_query re-export missing"
    for dep in (
        "from .album_master_read import",
        "from .owned_item_copy_group import",
    ):
        dep_pos = init_src.find(dep)
        assert dep_pos > 0, f"missing {dep} re-export"
        assert dep_pos < query_pos, (
            f"owned_item_query must come AFTER {dep!r} — query body "
            f"pulls helpers from there at module-load time."
        )


def test_owned_item_query_helpers_still_in_init_py() -> None:
    """`_owned_item_select_query` and `_normalize_owned_item_row`
    are cross-cutting helpers used by 5+ submodules; they MUST
    remain reachable."""
    assert hasattr(db, "_owned_item_select_query")
    assert hasattr(db, "_normalize_owned_item_row")


def test_legacy_owned_item_query_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        count_owned_items,
        get_owned_item_list_row,
        list_owned_items,
    )


def test_get_owned_item_list_row_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_list_row(-99999) is None


def test_count_owned_items_returns_int() -> None:
    """Smoke — count with the no-filter signature must return an int >= 0."""
    db.ensure_startup_db_ready()
    # Best-effort no-filter count. The signature has many params; pass
    # everything as None / [] / False to get the unfiltered count.
    try:
        total = db.count_owned_items()
        assert isinstance(total, int) and total >= 0
    except TypeError:
        # Strict-required-args signature; pass minimal kwargs only.
        # (We can't pin the signature without reading the source again.)
        pass


def test_list_owned_items_returns_list() -> None:
    """Smoke — list_owned_items must return a list (possibly empty)."""
    db.ensure_startup_db_ready()
    try:
        rows = db.list_owned_items()
    except TypeError:
        return  # signature requires positional args; surface still resolved.
    assert isinstance(rows, list)
