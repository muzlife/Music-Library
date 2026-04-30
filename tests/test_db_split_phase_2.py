"""Pin the second slice of the db.py → app/db/ package split.

  * `app.db.cache` exposes the external-response cache CRUD surface
    (get/upsert/touch/purge_expired).
  * `app.db` re-exports those four symbols so existing call sites
    (providers.cached_fetch_json, scheduled purge tasks, the test suite)
    continue to work unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import cache as cache_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cache_submodule_exposes_expected_surface() -> None:
    expected = {
        "get_cached_external_response",
        "upsert_cached_external_response",
        "touch_cached_external_response_expiry",
        "purge_expired_external_responses",
    }
    missing = [name for name in expected if not hasattr(cache_module, name)]
    assert not missing, f"app.db.cache missing: {missing}"


def test_db_package_reexports_cache_callables() -> None:
    for name in (
        "get_cached_external_response",
        "upsert_cached_external_response",
        "touch_cached_external_response_expiry",
        "purge_expired_external_responses",
    ):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(cache_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.cache.{name}"
        )


def test_init_py_no_longer_redefines_cache_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    forbidden = (
        "get_cached_external_response",
        "upsert_cached_external_response",
        "touch_cached_external_response_expiry",
        "purge_expired_external_responses",
    )
    for name in forbidden:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/cache.py"
        )


def test_legacy_cache_import_paths_still_work() -> None:
    """`from app.db import get_cached_external_response` (used by
    providers.cached_fetch_json) must keep resolving."""
    from app.db import (  # noqa: F401
        get_cached_external_response,
        purge_expired_external_responses,
        touch_cached_external_response_expiry,
        upsert_cached_external_response,
    )


def test_cache_round_trip_through_package_surface() -> None:
    """Insert/get/purge via the package-level names."""
    db.ensure_startup_db_ready()
    cache_key = "db-split-phase-2-probe"

    db.upsert_cached_external_response(
        cache_key=cache_key,
        source_code="DISCOGS",
        body_json='{"hello": "phase-2"}',
        status_code=200,
        ttl_seconds=600,
    )
    row = db.get_cached_external_response(cache_key)
    assert row is not None
    assert row["source_code"] == "DISCOGS"

    # Force-expire and verify purge removes it.
    with db.get_write_conn() as conn:
        conn.execute(
            "UPDATE external_response_cache SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE cache_key = ?",
            (cache_key,),
        )
    removed = db.purge_expired_external_responses()
    assert removed >= 1
    assert db.get_cached_external_response(cache_key) is None
