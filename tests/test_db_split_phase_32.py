"""Pin the thirty-second slice of the db.py → app/db/ package split.

  * `app.db.collection_dashboard` exposes `get_collection_dashboard`,
    the giant query that powers the operator's "내 컬렉션" overview
    screen — per-cabinet item counts, top genres, sort-policy
    summaries, and the "최근 이동" sidebar.
  * `app.db` re-exports the public function. collection_dashboard
    MUST be re-exported AFTER ops_home_recent because the dashboard
    embeds the recent-moved feed via the Phase 29 helpers.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import collection_dashboard as cd_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("get_collection_dashboard",)
_INTERNAL_SYMBOLS = (
    "_extract_collection_dashboard_release_year",
    "_build_collection_dashboard_first_item_hints",
)


def test_collection_dashboard_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(cd_module, name)]
    assert not missing, f"app.db.collection_dashboard missing: {missing}"


def test_db_package_reexports_collection_dashboard_callable() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(cd_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.collection_dashboard.{name}"
        )


def test_init_py_no_longer_redefines_collection_dashboard_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/collection_dashboard.py"
        )


def test_reexport_ordering_collection_dashboard_after_ops_home_recent() -> None:
    """collection_dashboard MUST be re-exported AFTER ops_home_recent
    because the dashboard pulls count_ops_home_recent_moved_items
    and list_ops_home_recent_moved_items from the package surface
    at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    cd_pos = init_src.find("from .collection_dashboard import")
    ohr_pos = init_src.find("from .ops_home_recent import")
    assert cd_pos > 0, "collection_dashboard re-export missing"
    assert ohr_pos > 0, "ops_home_recent re-export missing"
    assert ohr_pos < cd_pos, (
        "collection_dashboard re-export must come AFTER ops_home_recent"
    )


def test_legacy_collection_dashboard_path_still_works() -> None:
    from app.db import get_collection_dashboard  # noqa: F401


def test_get_collection_dashboard_returns_dict() -> None:
    """Smoke — the dashboard query must execute against the dev DB
    schema and return a dict envelope with the headline keys the
    operator overview screen renders."""
    db.ensure_startup_db_ready()
    payload = db.get_collection_dashboard()
    assert isinstance(payload, dict)
    for key in (
        "total_items",
        "in_collection_items",
        "by_slot",
        "by_status",
        "recent_moves",
        "recent_move_total",
        "movement_window_days",
    ):
        assert key in payload, f"dashboard envelope missing {key}"
    assert isinstance(payload["recent_moves"], list)
    assert isinstance(payload["recent_move_total"], int)
    assert isinstance(payload["movement_window_days"], int)
    assert isinstance(payload["by_slot"], list)
    assert isinstance(payload["by_status"], list)
