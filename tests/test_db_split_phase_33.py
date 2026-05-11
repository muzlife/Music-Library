"""Pin the thirty-third slice of the db.py → app/db/ package split.

  * `app.db.operator_search` exposes `search_operator_catalog` —
    the free-text "운영자 통합 검색" engine that returns
    owned_items + storage_slots + album_masters all at once,
    ranked by token-match strength. The largest single search
    query in the codebase (~270 lines).
  * `app.db` re-exports the public function so existing call sites
    (the operator search box, the test suite) keep working
    unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import operator_search as os_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("search_operator_catalog",)


def test_operator_search_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(os_module, name)]
    assert not missing, f"app.db.operator_search missing: {missing}"


def test_db_package_reexports_operator_search_callable() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(os_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.operator_search.{name}"
        )


def test_init_py_no_longer_redefines_operator_search_callable() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/operator_search.py"
        )


def test_search_helpers_still_in_init_py() -> None:
    """Search infrastructure helpers used by the operator-search
    body MUST stay in __init__.py — they're shared with several
    other lookups across the package."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (
        "_search_token_groups",
        "_matches_search_text",
        "_build_compact_token_match_sql",
        "_compact_search_text",
        "_normalize_owned_item_row",
        "_storage_slot_display_name",
        "_parse_label_id_query",
    ):
        assert f"def {name}(" in init_src, (
            f"{name} must remain in app/db/__init__.py — "
            f"operator_search pulls it via the package surface"
        )


def test_legacy_operator_search_path_still_works() -> None:
    from app.db import search_operator_catalog  # noqa: F401


def test_search_returns_empty_list_for_blank_query() -> None:
    """Read-only contract — empty/blank query short-circuits to []."""
    db.ensure_startup_db_ready()
    assert db.search_operator_catalog("") == []
    assert db.search_operator_catalog("   ") == []


def test_search_returns_list_for_unknown_query() -> None:
    """Read-only contract — query that won't match anything must
    return a list (possibly empty), not raise."""
    db.ensure_startup_db_ready()
    payload = db.search_operator_catalog("phase33-zzz-never-used-query-token")
    assert isinstance(payload, list)


def test_search_smoke_with_realistic_query() -> None:
    """Smoke — call with a normal-looking query; the return shape is
    a list (the search hit set)."""
    db.ensure_startup_db_ready()
    payload = db.search_operator_catalog("test")
    assert isinstance(payload, list)
