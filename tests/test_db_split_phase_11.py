"""Pin the eleventh slice of the db.py → app/db/ package split.

  * `app.db.album_master_merge_history` exposes the
    `list_album_master_merge_history` audit-log read and
    `rollback_latest_album_master_merge` undo write — used by the
    `/admin/album-masters/merge-history` route family.
  * `app.db` re-exports both public functions so existing call sites
    (the album-master admin router, the test suite) keep working
    unchanged.

The merge-history slice is special because the rollback path also
writes to `album_master`, `album_master_member`, `owned_item`, and
`album_master_external_ref` tables. We pin that the submodule
exposes the right surface and that `__init__.py` no longer redefines
the functions, but we deliberately do NOT exercise rollback against
live data here — the existing
`tests/test_album_master_merge_*` integration tests already cover
that path. This file is a pure structural pin.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_merge_history as amh_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_album_master_merge_history",
    "rollback_latest_album_master_merge",
)
_INTERNAL_SYMBOLS = (
    "_album_master_merge_history_record",
    "_latest_open_album_master_merge_history_id",
    "_json_loads_or_default",
)


def test_album_master_merge_history_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(amh_module, name)]
    assert not missing, f"app.db.album_master_merge_history missing: {missing}"


def test_db_package_reexports_album_master_merge_history_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amh_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_merge_history.{name}"
        )


def test_init_py_no_longer_redefines_merge_history_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_merge_history.py"
        )


def test_snapshot_helper_resolves_through_package_surface() -> None:
    """At Phase 11's commit, `_snapshot_album_master_record` lived in
    __init__.py because `merge_album_masters` (still in __init__.py
    at that point) needed it. In Phase 19 both moved together to
    `app/db/album_master_core.py`. What the merge-history rollback
    path actually needs is for the helper to be reachable somewhere —
    the post-Phase-19 contract is "via app.db package surface". Pin
    that instead of the no-longer-true location.

    `_normalize_domain_code_value` IS still a cross-cutting helper
    that stays in __init__.py — pin that.
    """
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert hasattr(db, "_snapshot_album_master_record"), (
        "_snapshot_album_master_record must remain reachable via the "
        "app.db package surface — Phase 19 moved it to album_master_core."
    )
    assert "def _normalize_domain_code_value(" in init_src, (
        "_normalize_domain_code_value must remain in app/db/__init__.py — "
        "it's a cross-cutting helper used 25+ times across the package"
    )


def test_legacy_merge_history_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        list_album_master_merge_history,
        rollback_latest_album_master_merge,
    )


def test_list_merge_history_smoke_through_package_surface() -> None:
    """Package-surface call should succeed even on an empty schema —
    list with no rows must return an empty list, not raise."""
    db.ensure_startup_db_ready()

    history = db.list_album_master_merge_history(limit=5)
    assert isinstance(history, list)


def test_rollback_with_no_history_raises_lookup_error() -> None:
    """If there's no open merge to roll back, the function MUST raise
    LookupError — that's the contract the admin route depends on for
    its 404 conversion."""
    import pytest

    db.ensure_startup_db_ready()

    # Snapshot any existing history rows; if the dev DB happens to
    # have an open merge, this test should be skipped rather than
    # disturb live data.
    existing = db.list_album_master_merge_history(limit=1)
    has_open = any(item.get("rolled_back_at") is None for item in existing)
    if has_open:
        pytest.skip("dev DB has an open merge — skipping no-history smoke")

    with pytest.raises(LookupError):
        db.rollback_latest_album_master_merge(rolled_back_by="phase-11-suite")
