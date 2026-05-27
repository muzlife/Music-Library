"""Pin the thirtieth slice of the db.py → app/db/ package split.

  * `app.db.metadata_sync` exposes the periodic metadata-sync job
    surface — `list_metadata_sync_candidates` (scan owned_items
    ripe for refresh) and `upsert_music_detail` (single-row write
    wrapper around `_upsert_music_item_detail_in_conn`).
  * `app.db` re-exports both public functions so existing call
    sites (the metadata-sync admin route, the scheduled background
    job, the test suite) keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import metadata_sync as ms_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_metadata_sync_candidates",
    "upsert_music_detail",
)


def test_metadata_sync_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(ms_module, name)]
    assert not missing, f"app.db.metadata_sync missing: {missing}"


def test_db_package_reexports_metadata_sync_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ms_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.metadata_sync.{name}"
        )


def test_init_py_no_longer_redefines_metadata_sync_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/metadata_sync.py"
        )


def test_upsert_music_item_detail_helper_still_in_init_py() -> None:
    """`_upsert_music_item_detail_in_conn` is shared with
    insert_owned_item / update_owned_item; it MUST remain reachable."""
    assert hasattr(db, "_upsert_music_item_detail_in_conn")


def test_legacy_metadata_sync_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        list_metadata_sync_candidates,
        upsert_music_detail,
    )


def test_list_candidates_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_metadata_sync_candidates(
        source_code=None, only_missing=False, limit=10
    )
    assert isinstance(rows, list)


def test_list_candidates_with_limit_clamps() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_metadata_sync_candidates(
        source_code=None, only_missing=False, limit=5
    )
    assert isinstance(rows, list)
    assert len(rows) <= 5
