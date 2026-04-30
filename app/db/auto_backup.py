"""Auto-backup settings DB surface.

Tenth slice extracted from the legacy `app/db.py`. Owns the
`auto_backup_*` keys stored in the generic `app_setting` key/value
table — used by the operator's "자동 백업" panel and the auto-backup
scheduler in main.py.

Public exports
  * get_auto_backup_settings
  * save_auto_backup_settings
  * record_auto_backup_result

Module-private helpers
  * AUTO_BACKUP_SETTING_KEYS — the set of `app_setting.setting_key`
    rows that compose a single backup-config snapshot.
  * _default_auto_backup_dir — fall-back directory under the DB root
    used when the operator hasn't picked a custom backup path.
  * _upsert_app_setting — primitive INSERT...ON CONFLICT against
    the generic `app_setting` table.
  * _auto_backup_settings_from_conn — single-connection read of all
    eight keys, normalised into the operator-panel response shape.

Cross-package dependencies
  * `_ensure_app_setting_table` and `_ensure_parent_dir` deliberately
    stay in `app.db.__init__` because they're shared with
    `get_conn` / `init_db` / migrations and would otherwise force a
    circular import. We pull `_ensure_app_setting_table` from the
    package surface here.

`app/db/__init__.py` re-exports every public symbol so existing
callers (the auto-backup admin route, the backup scheduler in
main.py, the test suite that monkey-patches `db.record_auto_backup_result`)
keep working unchanged.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings  # noqa: E402
from app.db import _ensure_app_setting_table, get_conn  # noqa: E402  — package surface


AUTO_BACKUP_SETTING_KEYS = (
    "auto_backup_enabled",
    "auto_backup_interval_minutes",
    "auto_backup_dir",
    "auto_backup_scope",
    "auto_backup_include_env_file",
    "auto_backup_last_at",
    "auto_backup_last_path",
    "auto_backup_last_error",
)


def _default_auto_backup_dir() -> str:
    settings = get_settings()
    return str(Path(settings.db_path).resolve().parent / "backups")


def _upsert_app_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO app_setting (setting_key, setting_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET
          setting_value = excluded.setting_value,
          updated_at = excluded.updated_at
        """,
        (str(key), None if value is None else str(value), now),
    )


def _auto_backup_settings_from_conn(conn: sqlite3.Connection) -> dict[str, Any]:
    _ensure_app_setting_table(conn)
    placeholders = ", ".join("?" for _ in AUTO_BACKUP_SETTING_KEYS)
    rows = conn.execute(
        f"""
        SELECT setting_key, setting_value
        FROM app_setting
        WHERE setting_key IN ({placeholders})
        """,
        AUTO_BACKUP_SETTING_KEYS,
    ).fetchall()
    values = {str(row["setting_key"]): row["setting_value"] for row in rows}
    enabled_raw = str(values.get("auto_backup_enabled") or "").strip().lower()
    interval_raw = str(values.get("auto_backup_interval_minutes") or "").strip()
    try:
        interval_minutes = max(0, int(interval_raw or "0"))
    except (TypeError, ValueError):
        interval_minutes = 0
    backup_dir = str(values.get("auto_backup_dir") or "").strip() or _default_auto_backup_dir()
    backup_scope = str(values.get("auto_backup_scope") or "").strip().upper()
    if backup_scope not in {"DB", "FULL"}:
        backup_scope = "DB"
    include_env_raw = str(values.get("auto_backup_include_env_file") or "").strip().lower()
    return {
        "enabled": enabled_raw in {"1", "true", "yes", "on", "y"},
        "interval_minutes": interval_minutes,
        "backup_dir": backup_dir,
        "backup_scope": backup_scope,
        "include_env_file": include_env_raw in {"1", "true", "yes", "on", "y"},
        "last_backup_at": str(values.get("auto_backup_last_at") or "").strip() or None,
        "last_backup_path": str(values.get("auto_backup_last_path") or "").strip() or None,
        "last_error": str(values.get("auto_backup_last_error") or "").strip() or None,
    }


def get_auto_backup_settings() -> dict[str, Any]:
    with get_conn() as conn:
        return _auto_backup_settings_from_conn(conn)


def save_auto_backup_settings(
    *,
    enabled: bool,
    interval_minutes: int,
    backup_dir: str,
    backup_scope: str = "DB",
    include_env_file: bool = False,
) -> dict[str, Any]:
    with get_conn() as conn:
        _ensure_app_setting_table(conn)
        _upsert_app_setting(conn, "auto_backup_enabled", "1" if enabled else "0")
        _upsert_app_setting(conn, "auto_backup_interval_minutes", str(max(0, int(interval_minutes))))
        _upsert_app_setting(conn, "auto_backup_dir", str(backup_dir or "").strip() or _default_auto_backup_dir())
        _upsert_app_setting(conn, "auto_backup_scope", "FULL" if str(backup_scope or "").strip().upper() == "FULL" else "DB")
        _upsert_app_setting(conn, "auto_backup_include_env_file", "1" if include_env_file else "0")
        return _auto_backup_settings_from_conn(conn)


def record_auto_backup_result(*, last_backup_at: str | None, last_backup_path: str | None, last_error: str | None) -> None:
    with get_conn() as conn:
        _ensure_app_setting_table(conn)
        _upsert_app_setting(conn, "auto_backup_last_at", last_backup_at)
        _upsert_app_setting(conn, "auto_backup_last_path", last_backup_path)
        _upsert_app_setting(conn, "auto_backup_last_error", last_error)


__all__ = [
    "AUTO_BACKUP_SETTING_KEYS",
    "get_auto_backup_settings",
    "save_auto_backup_settings",
    "record_auto_backup_result",
]
