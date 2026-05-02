"""Pin the twenty-ninth slice of the db.py → app/db/ package split.

  * `app.db.ops_home_recent` exposes the operator-home recent-feed
    surface — `count_ops_home_recent_moved_items`,
    `list_ops_home_recent_moved_items`,
    `count_ops_home_recent_registered_items`,
    `list_ops_home_recent_registered_items`,
    `get_ops_home_recent_sections`, `get_ops_home_feed`, plus the
    private `_build_ops_home_recent_item` row-shape builder.
  * `app.db` re-exports every public symbol so existing call sites
    (the operator home page route, the test suite) keep working
    unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import ops_home_recent as ohr_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "count_ops_home_recent_moved_items",
    "list_ops_home_recent_moved_items",
    "count_ops_home_recent_registered_items",
    "list_ops_home_recent_registered_items",
    "get_ops_home_recent_sections",
    "get_ops_home_feed",
)
_INTERNAL_SYMBOLS = ("_build_ops_home_recent_item",)


def test_ops_home_recent_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(ohr_module, name)]
    assert not missing, f"app.db.ops_home_recent missing: {missing}"


def test_db_package_reexports_ops_home_recent_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ohr_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.ops_home_recent.{name}"
        )


def test_init_py_no_longer_redefines_ops_home_recent_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/ops_home_recent.py"
        )


def test_dashboard_move_window_constant_still_in_init_py() -> None:
    """`DASHBOARD_MOVE_WINDOW_DAYS` is a module-level constant
    defined early in __init__.py. The new submodule pulls it via
    the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "DASHBOARD_MOVE_WINDOW_DAYS = " in init_src


def test_legacy_ops_home_recent_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        count_ops_home_recent_moved_items,
        count_ops_home_recent_registered_items,
        get_ops_home_feed,
        get_ops_home_recent_sections,
        list_ops_home_recent_moved_items,
        list_ops_home_recent_registered_items,
    )


def test_count_recent_moved_returns_int() -> None:
    db.ensure_startup_db_ready()
    total = db.count_ops_home_recent_moved_items()
    assert isinstance(total, int) and total >= 0


def test_count_recent_registered_returns_int() -> None:
    db.ensure_startup_db_ready()
    total = db.count_ops_home_recent_registered_items()
    assert isinstance(total, int) and total >= 0
    # With explicit days arg.
    total_30 = db.count_ops_home_recent_registered_items(days=30)
    assert isinstance(total_30, int) and total_30 >= 0


def test_list_recent_moved_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_ops_home_recent_moved_items(limit=3)
    assert isinstance(rows, list)
    assert len(rows) <= 3


def test_list_recent_registered_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_ops_home_recent_registered_items(limit=5)
    assert isinstance(rows, list)
    assert len(rows) <= 5


def test_get_ops_home_recent_sections_envelope() -> None:
    """The combined-sections endpoint must return a dict containing
    the 4 fields the operator home page renders."""
    db.ensure_startup_db_ready()
    payload = db.get_ops_home_recent_sections(limit=4)
    assert isinstance(payload, dict)
    for key in (
        "recent_moved_items",
        "recent_registered_items",
        "recent_moved_total_count",
        "recent_registered_total_count",
    ):
        assert key in payload, f"recent_sections envelope missing {key}"
    assert isinstance(payload["recent_moved_items"], list)
    assert isinstance(payload["recent_registered_items"], list)
    assert isinstance(payload["recent_moved_total_count"], int)
    assert isinstance(payload["recent_registered_total_count"], int)


def test_get_ops_home_feed_envelope() -> None:
    """The paginator wrapper must return a dict with items + pagination metadata."""
    db.ensure_startup_db_ready()
    payload = db.get_ops_home_feed(kind="registered", page=1, limit=10)
    assert isinstance(payload, dict)
    assert isinstance(payload.get("items"), list)
    # Sanity — limit clamps work for extreme pages.
    payload_far = db.get_ops_home_feed(kind="registered", page=10_000_000, limit=10)
    assert isinstance(payload_far, dict)
    assert payload_far.get("items") == []
