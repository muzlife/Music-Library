"""Pin the twenty-fifth slice of the db.py → app/db/ package split.

  * `app.db.owned_item_track` exposes two read-only owned_item
    queries — `get_owned_item_location_snapshot` and
    `get_owned_item_track_list`.
  * `app.db` re-exports both. The
    `get_owned_item_location_snapshot` re-export is critical —
    `customer_track_request.py` (Phase 4) AND `owned_item_slot.py`
    (Phase 23) both `from app.db import get_owned_item_location_snapshot`
    at module-load time.

Re-export ordering invariant
  owned_item_track MUST be re-exported BEFORE customer_track_request
  AND BEFORE owned_item_slot.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import customer_track_request as ctr_module
from app.db import owned_item_slot as ois_module
from app.db import owned_item_track as oit_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_owned_item_location_snapshot",
    "get_owned_item_track_list",
)


def test_owned_item_track_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(oit_module, name)]
    assert not missing, f"app.db.owned_item_track missing: {missing}"


def test_db_package_reexports_owned_item_track_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(oit_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_track.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_track_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_track.py"
        )


def test_reexport_ordering_owned_item_track_before_dependents() -> None:
    """Critical invariant — owned_item_track re-export MUST appear
    BEFORE customer_track_request AND BEFORE owned_item_slot,
    because both modules import `get_owned_item_location_snapshot`
    from app.db at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    track_pos = init_src.find("from .owned_item_track import")
    ctr_pos = init_src.find("from .customer_track_request import")
    ois_pos = init_src.find("from .owned_item_slot import")
    assert track_pos > 0, "owned_item_track re-export missing from __init__.py"
    assert ctr_pos > 0, "customer_track_request re-export missing"
    assert ois_pos > 0, "owned_item_slot re-export missing"
    assert track_pos < ctr_pos, (
        "owned_item_track MUST come BEFORE customer_track_request — "
        "customer_track_request.py imports get_owned_item_location_snapshot "
        "from app.db at module-load time."
    )
    assert track_pos < ois_pos, (
        "owned_item_track MUST come BEFORE owned_item_slot — "
        "owned_item_slot.py imports get_owned_item_location_snapshot "
        "from app.db at module-load time."
    )


def test_dependent_modules_resolve_through_package_surface() -> None:
    """Both customer_track_request and owned_item_slot must end up
    holding the SAME callable as db.get_owned_item_location_snapshot
    at module-load time."""
    assert ctr_module.get_owned_item_location_snapshot is db.get_owned_item_location_snapshot
    assert ois_module.get_owned_item_location_snapshot is db.get_owned_item_location_snapshot


def test_storage_slot_display_name_helper_still_in_init_py() -> None:
    """`_storage_slot_display_name` is a cross-cutting sort/display
    helper. It MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _storage_slot_display_name(" in init_src


def test_legacy_owned_item_track_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        get_owned_item_location_snapshot,
        get_owned_item_track_list,
    )


def test_get_owned_item_location_snapshot_returns_none_for_unknown() -> None:
    """Read-only contract — non-positive or unknown owned_item id
    must return None, not raise."""
    db.ensure_startup_db_ready()
    assert db.get_owned_item_location_snapshot(0) is None
    assert db.get_owned_item_location_snapshot(-1) is None
    assert db.get_owned_item_location_snapshot(-99999) is None


def test_get_owned_item_track_list_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_track_list(-99999) == []
