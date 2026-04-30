"""Pin the tenth slice of the db.py → app/db/ package split.

  * `app.db.auto_backup` exposes the auto-backup settings surface —
    the operator panel reads `get_auto_backup_settings`, writes via
    `save_auto_backup_settings`, and the backup scheduler in main.py
    records each run with `record_auto_backup_result`.
  * `app.db` re-exports every public symbol so existing call sites
    (the auto-backup admin route, the backup scheduler, the test
    suite that monkey-patches `db.record_auto_backup_result`) keep
    working unchanged.

`_ensure_app_setting_table` deliberately stays in `app.db.__init__`
because it's also called from init_db / migrations / startup db
ready — moving it would force a circular import. We assert it's
still importable from the package surface.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import auto_backup as ab_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_auto_backup_settings",
    "save_auto_backup_settings",
    "record_auto_backup_result",
)
_CONSTANTS = (
    "AUTO_BACKUP_SETTING_KEYS",
)


def test_auto_backup_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_CONSTANTS)
    missing = [name for name in expected if not hasattr(ab_module, name)]
    assert not missing, f"app.db.auto_backup missing: {missing}"


def test_db_package_reexports_auto_backup_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_CONSTANTS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ab_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.auto_backup.{name}"
        )


def test_init_py_no_longer_redefines_auto_backup_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/auto_backup.py"
        )
    # The constant must also no longer be assigned in __init__ (moved to submodule).
    assert "AUTO_BACKUP_SETTING_KEYS = (" not in init_src, (
        "app/db/__init__.py still defines AUTO_BACKUP_SETTING_KEYS — body "
        "should live only in app/db/auto_backup.py"
    )


def test_app_setting_table_helper_still_in_init_py() -> None:
    """`_ensure_app_setting_table` is shared with init_db / migrations
    and must stay in __init__.py to avoid circular imports. The
    auto_backup submodule re-imports it from the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _ensure_app_setting_table(" in init_src, (
        "_ensure_app_setting_table must remain in app/db/__init__.py — "
        "it is called from init_db / migrations / ensure_startup_db_ready"
    )


def test_legacy_auto_backup_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        AUTO_BACKUP_SETTING_KEYS,
        get_auto_backup_settings,
        record_auto_backup_result,
        save_auto_backup_settings,
    )


def test_auto_backup_round_trip_through_package_surface() -> None:
    """save → get → record → get; verify defaults + keys flip
    correctly via the package surface (not the submodule directly)."""
    db.ensure_startup_db_ready()

    # Snapshot for cleanup at the end.
    original = db.get_auto_backup_settings()

    saved = db.save_auto_backup_settings(
        enabled=True,
        interval_minutes=30,
        backup_dir="/tmp/phase-10-probe-backups",
        backup_scope="FULL",
        include_env_file=True,
    )
    assert saved["enabled"] is True
    assert saved["interval_minutes"] == 30
    assert saved["backup_dir"] == "/tmp/phase-10-probe-backups"
    assert saved["backup_scope"] == "FULL"
    assert saved["include_env_file"] is True

    fetched = db.get_auto_backup_settings()
    assert fetched["enabled"] is True
    assert fetched["interval_minutes"] == 30
    assert fetched["backup_dir"] == "/tmp/phase-10-probe-backups"

    db.record_auto_backup_result(
        last_backup_at="2026-04-30T12:00:00+00:00",
        last_backup_path="/tmp/phase-10-probe-backups/sample.db",
        last_error=None,
    )
    after_record = db.get_auto_backup_settings()
    assert after_record["last_backup_at"] == "2026-04-30T12:00:00+00:00"
    assert after_record["last_backup_path"] == "/tmp/phase-10-probe-backups/sample.db"
    assert after_record["last_error"] is None

    # Clearing the error path independently must not wipe the
    # successful-run fields above.
    db.record_auto_backup_result(
        last_backup_at=None,
        last_backup_path=None,
        last_error="phase-10 simulated failure",
    )
    cleared = db.get_auto_backup_settings()
    assert cleared["last_error"] == "phase-10 simulated failure"

    # Restore to whatever was there before so we don't pollute the dev DB.
    db.save_auto_backup_settings(
        enabled=bool(original["enabled"]),
        interval_minutes=int(original["interval_minutes"] or 0),
        backup_dir=str(original["backup_dir"] or ""),
        backup_scope=str(original["backup_scope"] or "DB"),
        include_env_file=bool(original["include_env_file"]),
    )
    db.record_auto_backup_result(
        last_backup_at=original.get("last_backup_at"),
        last_backup_path=original.get("last_backup_path"),
        last_error=original.get("last_error"),
    )


def test_default_backup_dir_falls_back_when_setting_blank() -> None:
    """Saving with `backup_dir=""` should fall back to the auto-backup
    default (which is `<db_root>/backups`)."""
    db.ensure_startup_db_ready()
    snapshot = db.get_auto_backup_settings()

    saved = db.save_auto_backup_settings(
        enabled=False,
        interval_minutes=0,
        backup_dir="",
    )
    assert saved["backup_dir"], "default backup_dir must not be empty"

    # Restore.
    db.save_auto_backup_settings(
        enabled=bool(snapshot["enabled"]),
        interval_minutes=int(snapshot["interval_minutes"] or 0),
        backup_dir=str(snapshot["backup_dir"] or ""),
        backup_scope=str(snapshot["backup_scope"] or "DB"),
        include_env_file=bool(snapshot["include_env_file"]),
    )
