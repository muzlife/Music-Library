"""Auth-account DB surface.

First slice extracted from `app/db.py` as part of the package split. The
five functions here are exclusively about reading/writing the
`auth_account` table (along with the table-ensure helper). Nothing else
in the codebase calls `_ensure_auth_account_table`, so the slice is
self-contained.

`app/db/__init__.py` re-exports every public symbol below so existing
callers (`db.list_auth_accounts(...)`, `from app.db import upsert_auth_account`)
continue to work unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

# `get_conn` and `utc_now_iso` are re-exported from app.db (currently
# defined in __init__.py during the package split). Once more domains
# move out, these will likely settle in app/db/connection.py — until
# then, importing from the package surface keeps the dependency direction
# pointing inward and avoids hardcoding a future module name.
from app.db import get_conn, utc_now_iso  # noqa: E402


def _ensure_auth_account_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_account (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    # Migration: if old CHECK constraint doesn't include VIEWER, recreate table
    table_info = conn.execute("PRAGMA table_info(auth_account)").fetchall()
    if table_info:
        # Check if VIEWER would be rejected by current CHECK
        try:
            conn.execute("INSERT INTO auth_account (username, password_hash, role, is_active, created_at, updated_at) VALUES ('__migration_probe__', 'x', 'VIEWER', 1, '2020-01-01T00:00:00Z', '2020-01-01T00:00:00Z')")
            conn.execute("DELETE FROM auth_account WHERE username = '__migration_probe__'")
        except Exception:
            # Old CHECK constraint — migrate
            conn.execute("ALTER TABLE auth_account RENAME TO auth_account_old")
            conn.execute(
                """
                CREATE TABLE auth_account (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL UNIQUE,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
                  is_active INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("INSERT INTO auth_account SELECT * FROM auth_account_old")
            conn.execute("DROP TABLE auth_account_old")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_account_role ON auth_account (role, is_active, username)"
    )


def list_auth_accounts() -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        rows = conn.execute(
            """
            SELECT id, username, password_hash, role, is_active, created_at, updated_at
            FROM auth_account
            ORDER BY
              CASE WHEN role = 'ADMIN' THEN 0 ELSE 1 END,
              LOWER(username) ASC,
              id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_auth_account_by_username(username: str) -> dict[str, Any] | None:
    key = str(username or "").strip()
    if not key:
        return None
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        row = conn.execute(
            """
            SELECT *
            FROM auth_account
            WHERE username = ?
            LIMIT 1
            """,
            (key,),
        ).fetchone()
    return dict(row) if row else None


def upsert_auth_account(
    username: str, password_hash: str, role: str, is_active: bool = True
) -> dict[str, Any] | None:
    key = str(username or "").strip()
    hashed = str(password_hash or "").strip()
    role_code = str(role or "").strip().upper()
    if not key or not hashed or role_code not in {"ADMIN", "OPERATOR", "VIEWER"}:
        return None
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        conn.execute(
            """
            INSERT INTO auth_account (username, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
              password_hash = excluded.password_hash,
              role = excluded.role,
              is_active = excluded.is_active,
              updated_at = excluded.updated_at
            """,
            (key, hashed, role_code, 1 if is_active else 0, now, now),
        )
    return get_auth_account_by_username(key)


def delete_auth_account(username: str) -> bool:
    key = str(username or "").strip()
    if not key:
        return False
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        cur = conn.execute("DELETE FROM auth_account WHERE username = ?", (key,))
    return int(cur.rowcount or 0) > 0


__all__ = [
    "_ensure_auth_account_table",
    "list_auth_accounts",
    "get_auth_account_by_username",
    "upsert_auth_account",
    "delete_auth_account",
]
