"""error_log 테이블: 서버 예외 기록 및 관리자 확인 추적."""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.connection import get_conn, get_write_conn, utc_now_iso

__all__ = [
    "insert_error_log",
    "list_error_log",
    "get_unread_error_count",
    "acknowledge_error_log",
]


def _ensure_error_log_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS error_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          level        TEXT NOT NULL DEFAULT 'ERROR',
          source       TEXT,
          message      TEXT NOT NULL,
          traceback    TEXT,
          request_path TEXT,
          request_body TEXT,
          is_read      INTEGER NOT NULL DEFAULT 0,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_error_log_created
          ON error_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_error_log_is_read
          ON error_log (is_read, created_at DESC);
        """
    )


def insert_error_log(
    *,
    level: str = "ERROR",
    source: str | None,
    message: str,
    traceback: str | None,
    request_path: str | None,
    request_body: str | None,
) -> int:
    now = utc_now_iso()
    # Ensure table exists (uses executescript, so must be outside get_conn context)
    with get_conn() as conn:
        _ensure_error_log_table(conn)
    # Now insert
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO error_log
              (level, source, message, traceback, request_path, request_body, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (level, source, message, traceback, request_path, request_body, now),
        )
        return cursor.lastrowid or 0


def list_error_log(
    *,
    is_read: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if is_read is not None:
        where = "WHERE is_read = ?"
        params.append(1 if is_read else 0)
    # Ensure table exists (uses executescript, so must be outside get_conn context)
    with get_conn() as conn:
        _ensure_error_log_table(conn)
    # Now query
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, level, source, message, traceback,
                   request_path, request_body, is_read, created_at
            FROM error_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_unread_error_count() -> int:
    # Ensure table exists (uses executescript, so must be outside get_conn context)
    with get_conn() as conn:
        _ensure_error_log_table(conn)
    # Now query
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM error_log WHERE is_read = 0"
        ).fetchone()
    return int(row[0]) if row else 0


def acknowledge_error_log(*, ids: list[int] | None = None) -> int:
    """ids=None이면 전체 확인 처리. 반환값: 처리된 행 수."""
    # Ensure table exists (uses executescript, so must be outside get_write_conn context)
    with get_conn() as conn:
        _ensure_error_log_table(conn)
    # Now update with write connection
    with get_write_conn() as conn:
        if ids is None:
            cursor = conn.execute("UPDATE error_log SET is_read = 1 WHERE is_read = 0")
        else:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"UPDATE error_log SET is_read = 1 WHERE id IN ({placeholders})",
                ids,
            )
    return cursor.rowcount
