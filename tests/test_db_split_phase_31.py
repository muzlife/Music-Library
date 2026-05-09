"""Pin the thirty-first slice of the db.py → app/db/ package split.

  * `app.db.music_shelf_window` exposes
    `get_music_shelf_window` (operator detail screen's "이 슬롯의
    진열 순서" panel) and `get_owned_counts_by_source` (metadata-
    sync admin's per-source dedupe counter).
  * `app.db` re-exports both. music_shelf_window MUST be re-exported
    AFTER owned_item_query because it pulls
    `get_owned_item_list_row` from the package surface.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import music_shelf_window as msw_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_music_shelf_window",
    "get_owned_counts_by_source",
)


def test_music_shelf_window_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(msw_module, name)]
    assert not missing, f"app.db.music_shelf_window missing: {missing}"


def test_db_package_reexports_music_shelf_window_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(msw_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.music_shelf_window.{name}"
        )


def test_init_py_no_longer_redefines_music_shelf_window_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/music_shelf_window.py"
        )


def test_reexport_ordering_music_shelf_window_after_owned_item_query() -> None:
    """music_shelf_window MUST be re-exported AFTER owned_item_query
    because get_music_shelf_window pulls get_owned_item_list_row
    from the package surface at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    msw_pos = init_src.find("from .music_shelf_window import")
    oiq_pos = init_src.find("from .owned_item_query import")
    assert msw_pos > 0, "music_shelf_window re-export missing"
    assert oiq_pos > 0, "owned_item_query re-export missing"
    assert oiq_pos < msw_pos, (
        "music_shelf_window re-export must come AFTER owned_item_query"
    )


def test_legacy_music_shelf_window_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        get_music_shelf_window,
        get_owned_counts_by_source,
    )


def test_get_owned_counts_by_source_handles_empty_input() -> None:
    """Empty source_external_ids list returns an empty dict, not raises."""
    db.ensure_startup_db_ready()
    counts = db.get_owned_counts_by_source("DISCOGS", [])
    assert counts == {}


def test_get_owned_counts_by_source_returns_dict_int_values() -> None:
    db.ensure_startup_db_ready()
    counts = db.get_owned_counts_by_source(
        "DISCOGS",
        ["phase-31-fake-1", "phase-31-fake-2"],
    )
    assert isinstance(counts, dict)
    for value in counts.values():
        assert isinstance(value, int) and value >= 0


def test_get_music_shelf_window_returns_none_for_missing_id() -> None:
    """Read-only contract — non-existent owned_item_id returns None."""
    db.ensure_startup_db_ready()
    assert db.get_music_shelf_window(-99999, window=2) is None
