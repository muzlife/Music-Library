"""Pin the eighteenth slice of the db.py → app/db/ package split.

  * `app.db.location_recommendation` exposes the location-recommendation
    engine surface — `recommend_owned_item_location` for the core
    rank, and `recommend_barcode_candidate_locations` for the
    barcode-lookup top-N wrapper.
  * `app.db` re-exports both public functions so existing call sites
    (the new-item form preview, the barcode-lookup endpoint, the
    operator routes, the test suite) keep working unchanged.

The rec engine is large (~673 lines, the biggest single function in
the legacy db.py) and gnarly enough that we deliberately do NOT
reproduce its full behaviour here — the existing integration tests
that drive `/owned-items/...` and `/recommend-barcode-locations`
routes already cover the happy-path. This file is a structural pin
plus a couple of obvious-fail-fast contracts (invalid size_group,
empty result for empty schema) that catch any silent re-export
break.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import location_recommendation as lr_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "recommend_owned_item_location",
    "recommend_barcode_candidate_locations",
)


def test_location_recommendation_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(lr_module, name)]
    assert not missing, f"app.db.location_recommendation missing: {missing}"


def test_db_package_reexports_recommendation_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(lr_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.location_recommendation.{name}"
        )


def test_init_py_no_longer_redefines_recommendation_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/location_recommendation.py"
        )


def test_cross_cutting_helpers_still_in_init_py() -> None:
    """The recommendation submodule depends on a dozen private
    helpers that are also used by other still-in-__init__.py
    writers/readers (sort keys, recommendation-text normalisers,
    storage_slot helpers, etc.). Those helpers MUST stay in
    __init__.py so the submodule can pull them via the package
    surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    # These helpers genuinely stay in __init__.py.
    for name in (
        "_normalize_domain_code_value",
        "_normalize_recommendation_text",
        "_normalize_master_release_sort_text",
        "_normalize_released_date_sort_text",
        "_resolve_owned_item_thickness_mm",
        "_storage_slot_display_name",
        "_storage_slot_sort_key",
        "_title_first_group_artist_key",
        "_compact_search_sql_expr",
        "build_storage_slot_occupancy_summary",
    ):
        assert f"def {name}(" in init_src, (
            f"{name} must remain in app/db/__init__.py — recommendation "
            f"submodule pulls it via the package surface"
        )
    # `_backfill_order_keys` was originally in __init__.py at Phase 18's
    # commit; in Phase 34 it moved to app/db/order_keys.py. What matters
    # for the recommendation submodule is that the helper is reachable
    # via the app.db package surface at module-load time. Pin THAT
    # contract instead of the no-longer-true location.
    assert hasattr(db, "_backfill_order_keys"), (
        "_backfill_order_keys must remain reachable via the app.db package "
        "surface — location_recommendation imports it at module-load time"
    )
    assert "SIZE_GROUP_CODES" in init_src, (
        "SIZE_GROUP_CODES constant must remain in app/db/__init__.py"
    )


def test_legacy_recommendation_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        recommend_barcode_candidate_locations,
        recommend_owned_item_location,
    )


def test_recommendation_returns_invalid_size_group_envelope() -> None:
    """`recommend_owned_item_location` must return its known no-pick
    envelope (NOT raise) when the size_group is unknown."""
    db.ensure_startup_db_ready()
    result = db.recommend_owned_item_location(
        size_group="NEVER_HEARD_OF_THIS_SIZE_GROUP",
        artist_or_brand="anyone",
        release_year=2000,
    )
    assert isinstance(result, dict)
    assert result.get("recommended_storage_slot_id") is None
    assert result.get("anchor_owned_item_id") is None
    assert result.get("reason") == "INVALID_SIZE_GROUP"
    assert result.get("used_fallback_slot") is False
    # candidate_slots key must exist and be a list (possibly empty).
    assert isinstance(result.get("candidate_slots"), list)


def test_barcode_recommendation_returns_empty_for_unknown_size_group() -> None:
    """The barcode wrapper short-circuits to [] when the resolved
    size_group isn't in SIZE_GROUP_CODES, regardless of category
    (because the operator may pass a non-standard category that
    falls through the fallback ladder to a still-invalid value)."""
    db.ensure_startup_db_ready()
    result = db.recommend_barcode_candidate_locations(
        category="NON_EXISTENT_CATEGORY",
        size_group="NEVER_HEARD_OF_THIS_SIZE_GROUP",
        format_name=None,
        artist_or_brand=None,
        title=None,
        release_year=None,
        thickness_mm=None,
        package_hint=None,
    )
    assert result == []


def test_barcode_recommendation_smoke_through_package_surface() -> None:
    """Smoke — call with a real size_group and a category that maps
    to it. The dev DB may have no slots configured, so the result
    can legitimately be []. What matters is the surface still
    resolves and returns a list, not raises."""
    db.ensure_startup_db_ready()
    result = db.recommend_barcode_candidate_locations(
        category="CD",
        size_group="STD",
        format_name="CD",
        artist_or_brand="phase-18 probe artist",
        title="phase-18 probe title",
        release_year=2026,
        thickness_mm=12,
        package_hint=None,
        limit=3,
    )
    assert isinstance(result, list)
    assert len(result) <= 3


def test_recommendation_smoke_with_real_size_group() -> None:
    """Smoke — call recommend_owned_item_location with STD + a probe
    artist/year. The result envelope must always be present even
    when no slots match."""
    db.ensure_startup_db_ready()
    result = db.recommend_owned_item_location(
        size_group="STD",
        artist_or_brand="phase-18 probe artist",
        release_year=2026,
    )
    assert isinstance(result, dict)
    for key in (
        "anchor_owned_item_id",
        "anchor_position",
        "recommended_storage_slot_id",
        "slot_code",
        "candidate_slots",
        "reason",
        "used_fallback_slot",
    ):
        assert key in result, f"recommendation result missing key: {key}"
    assert isinstance(result["candidate_slots"], list)
