"""perf_log 테이블: API/배치/DB 성능 기록."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_conn, utc_now_iso

__all__ = [
    "insert_perf_log",
    "list_perf_log_aggregated",
    "list_perf_log_detail",
]


def _ensure_perf_log_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS perf_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          kind         TEXT NOT NULL,
          name         TEXT NOT NULL,
          duration_ms  INTEGER NOT NULL,
          is_slow      INTEGER NOT NULL DEFAULT 0,
          context_json TEXT,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_perf_log_kind_created
          ON perf_log (kind, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_perf_log_slow
          ON perf_log (is_slow, created_at DESC);
        """
    )


def insert_perf_log(
    *,
    kind: str,
    name: str,
    duration_ms: int,
    is_slow: bool,
    context: dict[str, Any] | None = None,
) -> None:
    now = utc_now_iso()
    ctx_json = json.dumps(context, ensure_ascii=False) if context else None
    with get_conn() as conn:
        _ensure_perf_log_table(conn)
        conn.execute(
            """
            INSERT INTO perf_log (kind, name, duration_ms, is_slow, context_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kind, name, duration_ms, 1 if is_slow else 0, ctx_json, now),
        )


def list_perf_log_aggregated(
    *,
    kind: str | None = None,
    is_slow_only: bool = False,
    days: int = 7,
) -> list[dict[str, Any]]:
    conditions = [f"created_at >= datetime('now', '-{days} days')"]
    params: list[Any] = []
    if kind:
        conditions.append("kind = ?")
        params.append(kind)

    where_clause = "WHERE " + " AND ".join(conditions)
    having_clause = "AND SUM(is_slow) > 0" if is_slow_only else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            WITH grouped AS (
                SELECT
                    kind,
                    name,
                    duration_ms,
                    is_slow,
                    COUNT(*) OVER (PARTITION BY kind, name) AS total_count,
                    ROW_NUMBER() OVER (PARTITION BY kind, name ORDER BY duration_ms) AS rn
                FROM perf_log
                {where_clause}
            )
            SELECT
                kind,
                name,
                COUNT(*) AS count,
                CAST(AVG(duration_ms) AS INTEGER) AS avg_ms,
                MAX(duration_ms) AS max_ms,
                SUM(is_slow) AS slow_count,
                MAX(CASE
                    WHEN rn = MAX(1, CAST(total_count * 0.95 AS INTEGER))
                    THEN duration_ms
                END) AS p95_ms
            FROM grouped
            GROUP BY kind, name
            HAVING 1=1 {having_clause}
            ORDER BY max_ms DESC
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def list_perf_log_detail(
    *,
    name: str,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conditions = ["name = ?"]
    params: list[Any] = [name]
    if kind:
        conditions.append("kind = ?")
        params.append(kind)
    where = "WHERE " + " AND ".join(conditions)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, kind, name, duration_ms, is_slow, context_json, created_at
            FROM perf_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]
