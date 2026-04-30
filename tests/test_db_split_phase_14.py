"""Pin the fourteenth slice of the db.py → app/db/ package split.

  * `app.db.album_master_duplicates` exposes `list_duplicate_album_masters`
    (the duplicate-candidate query that backs the album-master merge
    UI's "유사 마스터" panel) plus the `_album_master_source_priority`
    helper.
  * `app.db` re-exports both so existing call sites (the album-master
    admin route, the test suite) keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_duplicates as amd_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("list_duplicate_album_masters",)
_INTERNAL_SYMBOLS = ("_album_master_source_priority",)


def test_album_master_duplicates_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(amd_module, name)]
    assert not missing, f"app.db.album_master_duplicates missing: {missing}"


def test_db_package_reexports_album_master_duplicates_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amd_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_duplicates.{name}"
        )


def test_init_py_no_longer_redefines_duplicates_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_duplicates.py"
        )


def test_legacy_duplicates_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        _album_master_source_priority,
        list_duplicate_album_masters,
    )


def test_source_priority_ordering_through_package_surface() -> None:
    """Pin the priority order: DISCOGS < MANIADB < MUSICBRAINZ < others."""
    assert db._album_master_source_priority("DISCOGS") == 0
    assert db._album_master_source_priority("MANIADB") == 1
    assert db._album_master_source_priority("MUSICBRAINZ") == 2
    assert db._album_master_source_priority("UNKNOWN_SOURCE") == 3
    # Case- and whitespace-insensitive.
    assert db._album_master_source_priority("  discogs  ") == 0
    assert db._album_master_source_priority("") == 3
    assert db._album_master_source_priority(None) == 3  # type: ignore[arg-type]


def test_list_duplicates_returns_empty_for_invalid_master() -> None:
    """Read-only contract — listing duplicates for a master id that
    doesn't exist (or is non-positive) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_duplicate_album_masters(album_master_id=0) == []
    assert db.list_duplicate_album_masters(album_master_id=-1) == []
    assert db.list_duplicate_album_masters(album_master_id=-99999) == []


def test_list_duplicates_smoke_through_package_surface() -> None:
    """Smoke — pick the smallest existing master, the call must not
    raise (it may return [] if the dev DB has no duplicates, that's
    fine; what matters is the surface still resolves correctly)."""
    db.ensure_startup_db_ready()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()
    if row is None:
        # No master rows — nothing to smoke against. The "invalid id"
        # test above already exercises the empty-result path.
        return
    result = db.list_duplicate_album_masters(int(row["id"]))
    assert isinstance(result, list)


def test_list_duplicates_limit_clamped_to_safe_range() -> None:
    """The limit must be clamped to [1, 100] regardless of caller input.
    We can't directly inspect the LIMIT in the issued SQL from outside,
    but we can probe the empty path with extreme values to confirm
    no exception is raised (the clamp handles it gracefully)."""
    db.ensure_startup_db_ready()
    # Upper bound — way above 100 must still work.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=10_000) == []
    # Zero should clamp up to 1, not blow up.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=0) == []
    # Negative limit should also be clamped.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=-5) == []
