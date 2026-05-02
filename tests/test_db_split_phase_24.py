"""Pin the twenty-fourth slice of the db.py → app/db/ package split.

  * `app.db.owned_item_order` exposes the operator drag-and-drop
    order writers on `owned_item.display_rank` —
    `move_owned_item_order`, `realign_owned_item_order_after_slot_move`,
    `move_owned_item_slot_display_rank`.
  * `app.db` re-exports every public symbol so existing call sites
    (`/owned-items/{id}/order` routes, the operator slot detail UI,
    the test suite) keep working unchanged.

The display_rank / order-key helpers stay in __init__.py because
they're shared with insert / update writers that haven't been moved
yet. The new submodule pulls them via the package surface.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import db
from app.db import owned_item_order as oio_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "move_owned_item_order",
    "realign_owned_item_order_after_slot_move",
    "move_owned_item_slot_display_rank",
)


def test_owned_item_order_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(oio_module, name)]
    assert not missing, f"app.db.owned_item_order missing: {missing}"


def test_db_package_reexports_owned_item_order_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(oio_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.owned_item_order.{name}"
        )


def test_init_py_no_longer_redefines_owned_item_order_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/owned_item_order.py"
        )


def test_order_key_helpers_still_in_init_py() -> None:
    """The display_rank / order-key helpers stay in __init__.py
    because they are shared with insert / update writers that
    haven't been moved yet."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (
        "_backfill_order_keys",
        "_compute_between_order_value",
        "_format_order_value",
        "_next_order_key_in_conn",
        "_parse_order_value",
        "_rebalance_in_collection_order",
        "_storage_slot_sort_key",
    ):
        assert f"def {name}(" in init_src, (
            f"{name} must remain in app/db/__init__.py — "
            f"owned_item_order pulls it via the package surface"
        )


def test_legacy_owned_item_order_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        move_owned_item_order,
        move_owned_item_slot_display_rank,
        realign_owned_item_order_after_slot_move,
    )


def test_move_owned_item_order_invalid_args_raise() -> None:
    """Invalid `position` argument must raise ValueError so the route
    can convert it to 400."""
    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.move_owned_item_order(1, 2, "INVALID_POSITION")


def test_realign_owned_item_order_returns_string_for_unknown() -> None:
    """Smoke — calling realign with a non-existent owned_item_id
    should not raise; it should fall through gracefully."""
    db.ensure_startup_db_ready()
    # The function returns a display_rank string; pin that the
    # surface resolves and returns a string-type value (or raises a
    # known exception). We don't pin the exact failure mode because
    # the schema may differ between dev/QA/prod.
    try:
        result = db.realign_owned_item_order_after_slot_move(-99999, -99998)
        assert isinstance(result, str) or result is None
    except (ValueError, RuntimeError, LookupError):
        pass  # Acceptable failure shapes.


def test_move_slot_display_rank_smoke() -> None:
    """Smoke — the higher-level wrapper must at least resolve and
    invoke without ImportError."""
    db.ensure_startup_db_ready()
    # Probe with invalid IDs — we expect a controlled failure shape,
    # NOT an ImportError or NameError (which would mean the package
    # surface is broken).
    try:
        db.move_owned_item_slot_display_rank(
            owned_item_id=-1,
            target_owned_item_id=-2,
            position="BEFORE",
        )
    except (ValueError, RuntimeError, LookupError, TypeError):
        pass  # Acceptable failure shapes.
