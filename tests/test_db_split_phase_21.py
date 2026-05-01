"""Pin the twenty-first slice of the db.py → app/db/ package split.

  * `app.db.owned_item_track_links` exposes the owned_item track-
    link / audio-directory-link read+delete surface —
    `list_owned_item_track_links`,
    `list_owned_item_audio_directory_links`,
    `delete_owned_item_track_links`,
    `delete_owned_item_audio_directory_links`.
  * `app.db` re-exports every public symbol so existing call sites
    (`/owned-items/{id}/links` routes, the test suite, the
    delete-cascade path in the operator owned-item form) keep
    working unchanged.

The dual write paths (insert track / dir links) live elsewhere —
most go through `digital_link.insert_digital_link` (Phase 17) and
the metadata-sync watch-directory paths in `app/main.py`. Only the
list/delete surface is migrated here.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import owned_item_track_links as otl_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_owned_item_track_links",
    "list_owned_item_audio_directory_links",
    "delete_owned_item_track_links",
    "delete_owned_item_audio_directory_links",
)


def test_owned_item_track_links_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(otl_module, name)]
    assert not missing, f"app.db.owned_item_track_links missing: {missing}"


def test_db_package_reexports_track_links_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(otl_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_track_links.{name}"
        )


def test_init_py_no_longer_redefines_track_links_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_track_links.py"
        )


def test_legacy_track_links_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        delete_owned_item_audio_directory_links,
        delete_owned_item_track_links,
        list_owned_item_audio_directory_links,
        list_owned_item_track_links,
    )


def test_list_track_links_returns_empty_for_unknown_owned_item() -> None:
    """Read-only contract — listing track_links for an owned_item id
    that has none (or doesn't exist) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_owned_item_track_links(-99999) == []


def test_list_audio_directory_links_returns_empty_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.list_owned_item_audio_directory_links(-99999) == []


def test_delete_track_links_returns_zero_for_unknown_owned_item() -> None:
    """Write contract — deleting track_links for an owned_item that
    has none returns 0, NOT raises."""
    db.ensure_startup_db_ready()
    assert db.delete_owned_item_track_links(-99999) == 0


def test_delete_audio_directory_links_returns_zero_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.delete_owned_item_audio_directory_links(-99999) == 0
