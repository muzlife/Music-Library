"""Pin the thirty-fourth slice of the db.py → app/db/ package split.

  * `app.db.order_keys` exposes the fractional-index machinery for
    the operator drag-and-drop sort UI — `_format_order_value`,
    `_parse_order_value`, `_next_order_key_in_conn`,
    `_backfill_order_keys`, `_compute_between_order_value`,
    `_rebalance_in_collection_order`, and the public
    `resequence_in_collection_order` operator-button writer.
  * `app.db` re-exports every symbol so existing call sites
    (location_recommendation, owned_item_order, music_shelf_window,
    owned_item_write, the legacy migration path, the test suite)
    keep working unchanged.

Re-export ordering invariant
  order_keys MUST be re-exported BEFORE any consumer slice. It
  depends on `list_owned_items_for_storage_slot` from storage_slot,
  so it loads right after storage_slot in __init__.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import order_keys as ok_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("resequence_in_collection_order",)
_INTERNAL_SYMBOLS = (
    "_format_order_value",
    "_parse_order_value",
    "_next_order_key_in_conn",
    "_backfill_order_keys",
    "_compute_between_order_value",
    "_rebalance_in_collection_order",
)


def test_order_keys_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(ok_module, name)]
    assert not missing, f"app.db.order_keys missing: {missing}"


def test_db_package_reexports_order_keys_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ok_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.order_keys.{name}"
        )


def test_init_py_no_longer_redefines_order_keys_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/order_keys.py"
        )


def test_order_key_constants_still_in_init_py() -> None:
    """`ORDER_KEY_WIDTH` and `ORDER_KEY_STEP` are module-level
    constants in __init__.py; the new submodule pulls them via the
    package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "ORDER_KEY_WIDTH = " in init_src
    assert "ORDER_KEY_STEP = " in init_src


def test_reexport_ordering_order_keys_before_consumers() -> None:
    """order_keys MUST be re-exported BEFORE its consumer slices
    (location_recommendation, owned_item_order, music_shelf_window,
    owned_item_write)."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    ok_pos = init_src.find("from .order_keys import")
    assert ok_pos > 0, "order_keys re-export missing"
    for consumer in (
        "from .location_recommendation import",
        "from .owned_item_order import",
        "from .music_shelf_window import",
        "from .owned_item_write import",
    ):
        c_pos = init_src.find(consumer)
        assert c_pos > 0, f"missing {consumer} re-export"
        assert ok_pos < c_pos, (
            f"order_keys re-export must come BEFORE {consumer!r} — "
            f"that module pulls order-key helpers via the package surface."
        )


def test_legacy_order_keys_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        _backfill_order_keys,
        _compute_between_order_value,
        _format_order_value,
        _next_order_key_in_conn,
        _parse_order_value,
        _rebalance_in_collection_order,
        resequence_in_collection_order,
    )


def test_format_and_parse_order_value_round_trip() -> None:
    """Format/parse pin — encoding and decoding positive integer
    order values must round-trip cleanly. (Note: format clamps any
    value <= 0 to ORDER_KEY_STEP, so we only test positive inputs.)"""
    for raw in (1, 1024, 12345, 999_999_999):
        encoded = db._format_order_value(raw)
        assert isinstance(encoded, str)
        assert db._parse_order_value(encoded) == raw


def test_parse_order_value_returns_none_for_invalid_input() -> None:
    assert db._parse_order_value(None) is None
    assert db._parse_order_value("") is None
    assert db._parse_order_value("not-a-number") is None


def test_compute_between_order_value_midpoint() -> None:
    """`_compute_between_order_value` returns the midpoint of two
    neighbouring order keys (used by drag-between gestures)."""
    assert db._compute_between_order_value(0, 2048) == 1024
    assert db._compute_between_order_value(1024, 2048) == 1536
    # When left is None, we extend to the left.
    left_only = db._compute_between_order_value(None, 1024)
    assert isinstance(left_only, int)
    # When right is None, we extend to the right.
    right_only = db._compute_between_order_value(1024, None)
    assert isinstance(right_only, int)


def test_resequence_returns_count_envelope() -> None:
    """Smoke — resequence_in_collection_order returns a dict with
    the three counter fields the operator-facing button uses for
    the toast message."""
    db.ensure_startup_db_ready()
    payload = db.resequence_in_collection_order()
    assert isinstance(payload, dict)
    for key in ("assigned_slot_count", "reordered_count", "unassigned_tail_count"):
        assert key in payload, f"resequence envelope missing {key}"
        assert isinstance(payload[key], int)
