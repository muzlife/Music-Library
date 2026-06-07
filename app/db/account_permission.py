"""Permission management DB surface.

Three tables:
  permission         — master list of permission keys (seeded at migration)
  role_permission    — role-level default grants
  account_permission — per-account override grants/denies

app/db/__init__.py re-exports the public symbols so callers use
db.list_permissions(), db.check_permission(), etc.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn, utc_now_iso  # noqa: E402


# All permission keys in sorted order (used for effective-permission sweeps)
ALL_PERMISSION_KEYS = (
    "ops.feed",
    "ops.search",
    "ops.location",
    "ops.requests",
    "ops.playback",
    "ops.move_item",
    "ops.edit_item",
    "ops.cabinet",
    "ops.exception_queue",
    "hr.manage_staff",
)

_DEFAULT_PERMISSIONS = [
    ("ops.feed",            "피드 보기",        "ops", None, 10),
    ("ops.search",          "카탈로그 검색",     "ops", None, 20),
    ("ops.location",        "위치 확인",        "ops", None, 30),
    ("ops.requests",        "요청곡 관리",       "ops", None, 40),
    ("ops.playback",        "음악 재생",        "ops", None, 50),
    ("ops.move_item",       "아이템 이동",       "ops", None, 60),
    ("ops.edit_item",       "아이템 편집",       "ops", None, 70),
    ("ops.cabinet",         "장식장 관리",       "ops", None, 80),
    ("ops.exception_queue", "예외 큐",          "ops", None, 90),
    ("hr.manage_staff",     "스태프 계정 관리",   "hr",  None, 10),
]

_DEFAULT_ROLE_PERMISSIONS = [
    ("OPERATOR",   "ops.feed"),
    ("OPERATOR",   "ops.search"),
    ("OPERATOR",   "ops.location"),
    ("OPERATOR",   "ops.requests"),
    ("OPERATOR",   "ops.playback"),
    ("CAFE_STAFF", "ops.feed"),
    ("CAFE_STAFF", "ops.search"),
    ("CAFE_STAFF", "ops.location"),
    ("CAFE_STAFF", "ops.requests"),
    ("CAFE_STAFF", "ops.playback"),
]


def _ensure_permission_tables(conn: sqlite3.Connection) -> None:

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS permission (
          key         TEXT PRIMARY KEY,
          label       TEXT NOT NULL,
          category    TEXT NOT NULL,
          description TEXT,
          sort_order  INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permission (
          role           TEXT NOT NULL,
          permission_key TEXT NOT NULL REFERENCES permission(key) ON DELETE CASCADE,
          PRIMARY KEY (role, permission_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS account_permission (
          username       TEXT NOT NULL,
          permission_key TEXT NOT NULL REFERENCES permission(key) ON DELETE CASCADE,
          granted        INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY (username, permission_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_role_permission_role "
        "ON role_permission (role)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_account_permission_username "
        "ON account_permission (username)"
    )


def seed_default_permissions(conn: sqlite3.Connection) -> None:
    _ensure_permission_tables(conn)
    conn.executemany(
        """
        INSERT OR IGNORE INTO permission (key, label, category, description, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        _DEFAULT_PERMISSIONS,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO role_permission (role, permission_key)
        VALUES (?, ?)
        """,
        _DEFAULT_ROLE_PERMISSIONS,
    )


def list_permissions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        rows = conn.execute(
            """
            SELECT key, label, category, description, sort_order
            FROM permission
            ORDER BY category, sort_order
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_role_permissions(role: str) -> list[str]:
    key = str(role or "").strip().upper()
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        rows = conn.execute(
            "SELECT permission_key FROM role_permission WHERE role = ?",
            (key,),
        ).fetchall()
    return [str(row["permission_key"]) for row in rows]


def set_role_permissions(role: str, permission_keys: list[str]) -> None:
    key = str(role or "").strip().upper()
    safe_keys = [str(k).strip() for k in permission_keys if str(k).strip()]
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        conn.execute("DELETE FROM role_permission WHERE role = ?", (key,))
        if safe_keys:
            conn.executemany(
                "INSERT OR IGNORE INTO role_permission (role, permission_key) VALUES (?, ?)",
                [(key, k) for k in safe_keys],
            )


def list_account_permissions(username: str) -> list[dict[str, Any]]:
    uname = str(username or "").strip()
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        rows = conn.execute(
            "SELECT permission_key, granted FROM account_permission WHERE username = ?",
            (uname,),
        ).fetchall()
    return [dict(row) for row in rows]


def set_account_permission(username: str, permission_key: str, granted: bool) -> None:
    uname = str(username or "").strip()
    pkey = str(permission_key or "").strip()
    if not uname or not pkey:
        return
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO account_permission (username, permission_key, granted)
            VALUES (?, ?, ?)
            """,
            (uname, pkey, 1 if granted else 0),
        )


def delete_account_permission(username: str, permission_key: str) -> bool:
    uname = str(username or "").strip()
    pkey = str(permission_key or "").strip()
    if not uname or not pkey:
        return False
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        cur = conn.execute(
            "DELETE FROM account_permission WHERE username = ? AND permission_key = ?",
            (uname, pkey),
        )
    return int(cur.rowcount or 0) > 0


def clear_account_permissions(username: str) -> int:
    uname = str(username or "").strip()
    if not uname:
        return 0
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        cur = conn.execute(
            "DELETE FROM account_permission WHERE username = ?",
            (uname,),
        )
    return int(cur.rowcount or 0)


def check_permission(username: str, role: str, permission_key: str) -> bool:
    uname = str(username or "").strip()
    r = str(role or "").strip().upper()
    pkey = str(permission_key or "").strip()
    with get_conn() as conn:
        _ensure_permission_tables(conn)
        override = conn.execute(
            "SELECT granted FROM account_permission WHERE username = ? AND permission_key = ?",
            (uname, pkey),
        ).fetchone()
        if override is not None:
            return bool(override["granted"])
        role_row = conn.execute(
            "SELECT 1 FROM role_permission WHERE role = ? AND permission_key = ?",
            (r, pkey),
        ).fetchone()
    return role_row is not None


def get_effective_permissions(username: str, role: str) -> dict[str, bool]:
    return {
        pkey: check_permission(username, role, pkey)
        for pkey in ALL_PERMISSION_KEYS
    }


__all__ = [
    "_ensure_permission_tables",
    "seed_default_permissions",
    "ALL_PERMISSION_KEYS",
    "list_permissions",
    "list_role_permissions",
    "set_role_permissions",
    "list_account_permissions",
    "set_account_permission",
    "delete_account_permission",
    "clear_account_permissions",
    "check_permission",
    "get_effective_permissions",
]
