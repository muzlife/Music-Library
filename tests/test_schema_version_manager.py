"""Coverage for the PRAGMA user_version-based migration manager.

Pins the new contract:
  * SCHEMA_VERSION is a real integer and at least 1.
  * `_run_pending_migrations` is idempotent — second call is a no-op once
    the DB is at SCHEMA_VERSION.
  * Bringing a pre-versioning DB up to current converges to user_version
    = SCHEMA_VERSION on first boot.
  * `ensure_startup_db_ready` short-circuits the legacy idempotent pass
    on subsequent boots (user_version already >= SCHEMA_VERSION).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import db


def _user_version_for(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


def test_schema_version_is_at_least_one() -> None:
    assert isinstance(db.SCHEMA_VERSION, int)
    assert db.SCHEMA_VERSION >= 1


def test_init_db_sets_user_version_to_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_db = tmp_path / "fresh.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(target_db))
    from app import config as config_module
    config_module.get_settings.cache_clear()
    try:
        db.init_db()
        assert target_db.exists()
        assert _user_version_for(target_db) == db.SCHEMA_VERSION
    finally:
        config_module.get_settings.cache_clear()


def test_run_pending_migrations_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_db = tmp_path / "idempotent.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(target_db))
    from app import config as config_module
    config_module.get_settings.cache_clear()
    try:
        db.init_db()
        # First call after init_db should already report 0 pending migrations.
        with db.get_conn() as conn:
            applied = db._run_pending_migrations(conn)
        assert applied == 0
        # And again, just to be sure.
        with db.get_conn() as conn:
            applied = db._run_pending_migrations(conn)
        assert applied == 0
    finally:
        config_module.get_settings.cache_clear()


def test_pre_versioning_install_converges_on_first_boot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a DB created before user_version was tracked.

    We initialise normally then manually reset user_version=0 to mimic a
    pre-2026-04 install. The next `ensure_startup_db_ready` should run
    the legacy migration pass once and bump back to SCHEMA_VERSION.
    """
    target_db = tmp_path / "legacy.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(target_db))
    from app import config as config_module
    config_module.get_settings.cache_clear()
    try:
        db.init_db()
        # Force the DB back to "pre-versioning" state.
        rewind = sqlite3.connect(str(target_db))
        try:
            rewind.execute("PRAGMA user_version = 0")
            rewind.commit()
        finally:
            rewind.close()
        assert _user_version_for(target_db) == 0

        db.ensure_startup_db_ready()

        assert _user_version_for(target_db) == db.SCHEMA_VERSION
    finally:
        config_module.get_settings.cache_clear()


def test_ensure_startup_skips_legacy_pass_when_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When user_version already matches SCHEMA_VERSION, ensure_startup_db_ready
    must NOT invoke the legacy idempotent pass. We monkeypatch the legacy
    helper to a sentinel that increments a counter and assert it stays 0."""
    target_db = tmp_path / "fastpath.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(target_db))
    from app import config as config_module
    config_module.get_settings.cache_clear()
    try:
        db.init_db()  # → user_version = SCHEMA_VERSION
        assert _user_version_for(target_db) == db.SCHEMA_VERSION

        calls = {"legacy": 0}

        def _spy(conn):  # type: ignore[no-untyped-def]
            calls["legacy"] += 1

        monkeypatch.setattr(db, "_apply_migrations_legacy", _spy)
        # Even ensure_recent_feed_indexes / app_setting_table are skipped on
        # the fast path; pin those too.
        monkeypatch.setattr(db, "_ensure_recent_feed_indexes", _spy)

        db.ensure_startup_db_ready()
        assert calls["legacy"] == 0, "fast path must skip legacy migration helpers"
    finally:
        config_module.get_settings.cache_clear()


def test_migration_registry_is_contiguous() -> None:
    """Every registered migration version must be a positive int and the
    set must be contiguous from 1..max. This catches `add v3 without v2`
    bugs that would silently leave SCHEMA_VERSION holes."""
    versions = sorted(db._MIGRATIONS_BY_VERSION)
    assert versions, "at least one migration must be registered"
    assert versions[0] == 1
    for prev, curr in zip(versions, versions[1:]):
        assert curr == prev + 1, f"non-contiguous migration registry: {versions}"
    assert max(versions) == db.SCHEMA_VERSION, (
        "SCHEMA_VERSION must equal the highest registered migration version"
    )
