"""Coverage for the persisted external-response cache.

Pins:
  * Schema migration v2 creates `external_response_cache` and `idx_*`.
  * `cached_fetch_json` returns cached body on a hit and skips the fetcher.
  * Stale cache + fetcher failure → caller still gets the stale body
    (so a Discogs 503 doesn't tip the metadata sync worker into nulls).
  * Expired entries do trigger a refetch.
  * `purge_expired_external_responses` deletes only stale rows.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import httpx
import pytest

from app import db
from app.services import providers as providers_module


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _index_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (name,)
    ).fetchone()
    return row is not None


def test_v2_migration_creates_cache_table_and_indexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "fresh.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(target))
    from app import config as config_module

    config_module.get_settings.cache_clear()
    try:
        db.init_db()
        with db.get_conn() as conn:
            assert _table_exists(conn, "external_response_cache")
            assert _index_exists(conn, "idx_external_response_cache_expires")
            assert _index_exists(conn, "idx_external_response_cache_source")
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert user_version >= 2
    finally:
        config_module.get_settings.cache_clear()


def test_cache_round_trip_via_db_helpers() -> None:
    db.ensure_startup_db_ready()
    db.upsert_cached_external_response(
        cache_key="UNIT-TEST-KEY",
        source_code="DISCOGS",
        body_json=json.dumps({"hello": "world"}),
        status_code=200,
        ttl_seconds=60,
    )
    row = db.get_cached_external_response("UNIT-TEST-KEY")
    assert row is not None
    assert row["source_code"] == "DISCOGS"
    assert json.loads(row["body_json"]) == {"hello": "world"}
    assert row["status_code"] == 200
    # Cleanup so other tests don't see this row.
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM external_response_cache WHERE cache_key = 'UNIT-TEST-KEY'")


def test_cached_fetch_json_skips_fetcher_on_fresh_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    db.ensure_startup_db_ready()
    cache_key = providers_module.build_external_cache_key("DISCOGS", "release", "fetcher-skip-1")
    db.upsert_cached_external_response(
        cache_key=cache_key,
        source_code="DISCOGS",
        body_json=json.dumps({"id": 1, "title": "cached release"}),
        status_code=200,
        ttl_seconds=600,
    )

    calls = {"n": 0}

    def _fetcher() -> httpx.Response:  # pragma: no cover - must not run
        calls["n"] += 1
        return httpx.Response(200, json={"unexpected": True})

    body = providers_module.cached_fetch_json(
        source_code="DISCOGS",
        kind="release",
        identifier="fetcher-skip-1",
        fetcher=_fetcher,
    )
    assert body == {"id": 1, "title": "cached release"}
    assert calls["n"] == 0
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM external_response_cache WHERE cache_key = ?", (cache_key,))


def test_cached_fetch_json_falls_back_to_stale_on_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale cache must save us when the upstream provider 5xx's."""
    db.ensure_startup_db_ready()
    cache_key = providers_module.build_external_cache_key("DISCOGS", "release", "stale-fallback-1")

    # Seed a row, then force-expire it.
    db.upsert_cached_external_response(
        cache_key=cache_key,
        source_code="DISCOGS",
        body_json=json.dumps({"id": 2, "title": "stale release"}),
        status_code=200,
        ttl_seconds=60,
    )
    with db.get_write_conn() as conn:
        conn.execute(
            "UPDATE external_response_cache SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE cache_key = ?",
            (cache_key,),
        )

    def _fetcher() -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream unavailable"})

    body = providers_module.cached_fetch_json(
        source_code="DISCOGS",
        kind="release",
        identifier="stale-fallback-1",
        fetcher=_fetcher,
    )
    assert body == {"id": 2, "title": "stale release"}
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM external_response_cache WHERE cache_key = ?", (cache_key,))


def test_cached_fetch_json_refetches_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    db.ensure_startup_db_ready()
    cache_key = providers_module.build_external_cache_key("DISCOGS", "release", "expiry-1")

    db.upsert_cached_external_response(
        cache_key=cache_key,
        source_code="DISCOGS",
        body_json=json.dumps({"id": 3, "title": "old"}),
        status_code=200,
        ttl_seconds=60,
    )
    with db.get_write_conn() as conn:
        conn.execute(
            "UPDATE external_response_cache SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE cache_key = ?",
            (cache_key,),
        )

    def _fetcher() -> httpx.Response:
        return httpx.Response(200, json={"id": 3, "title": "fresh"})

    body = providers_module.cached_fetch_json(
        source_code="DISCOGS",
        kind="release",
        identifier="expiry-1",
        fetcher=_fetcher,
    )
    assert body == {"id": 3, "title": "fresh"}

    # Confirm the row was updated, not just returned.
    fresh_row = db.get_cached_external_response(cache_key)
    assert fresh_row is not None
    assert json.loads(fresh_row["body_json"])["title"] == "fresh"
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM external_response_cache WHERE cache_key = ?", (cache_key,))


def test_purge_expired_external_responses_only_drops_stale() -> None:
    db.ensure_startup_db_ready()
    fresh_key = providers_module.build_external_cache_key("DISCOGS", "release", "purge-fresh-1")
    stale_key = providers_module.build_external_cache_key("DISCOGS", "release", "purge-stale-1")

    db.upsert_cached_external_response(
        cache_key=fresh_key,
        source_code="DISCOGS",
        body_json=json.dumps({"keep": True}),
        status_code=200,
        ttl_seconds=600,
    )
    db.upsert_cached_external_response(
        cache_key=stale_key,
        source_code="DISCOGS",
        body_json=json.dumps({"drop": True}),
        status_code=200,
        ttl_seconds=60,
    )
    with db.get_write_conn() as conn:
        conn.execute(
            "UPDATE external_response_cache SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE cache_key = ?",
            (stale_key,),
        )

    removed = db.purge_expired_external_responses()
    assert removed >= 1
    assert db.get_cached_external_response(fresh_key) is not None
    assert db.get_cached_external_response(stale_key) is None
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM external_response_cache WHERE cache_key IN (?, ?)",
            (fresh_key, stale_key),
        )


def test_build_external_cache_key_is_deterministic_and_namespaced() -> None:
    a = providers_module.build_external_cache_key("DISCOGS", "release", "12345")
    b = providers_module.build_external_cache_key("DISCOGS", "release", "12345")
    assert a == b
    assert a.startswith("DISCOGS:release:")
    other = providers_module.build_external_cache_key("DISCOGS", "master", "12345")
    assert a != other


def test_cache_disabled_env_bypasses_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """When EXTERNAL_RESPONSE_CACHE_DISABLED=1, calls go straight to the
    fetcher and nothing lands in the table."""
    monkeypatch.setattr(providers_module, "EXTERNAL_RESPONSE_CACHE_DISABLED", True)
    cache_key = providers_module.build_external_cache_key("DISCOGS", "release", "disabled-1")
    assert db.get_cached_external_response(cache_key) is None

    def _fetcher() -> httpx.Response:
        return httpx.Response(200, json={"bypass": True})

    body = providers_module.cached_fetch_json(
        source_code="DISCOGS",
        kind="release",
        identifier="disabled-1",
        fetcher=_fetcher,
    )
    assert body == {"bypass": True}
    assert db.get_cached_external_response(cache_key) is None
