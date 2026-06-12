"""데이터베이스 연결 관리 모듈

`get_conn` / `get_write_conn`을 제공하며, `app.db.__init__`에서
재-export하여 기존 호출자(`from app.db import get_conn`)가
변경 없이 동작하도록 유지합니다.
"""

from __future__ import annotations

import sqlite3
import threading
import time as _time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from ..config import get_settings

SQLITE_BUSY_TIMEOUT_MS = 30_000

_slow_query_recording = threading.local()
_read_local = threading.local()          # per-thread: conn, depth, generation
_all_read_conns: list[_TimedConnection] = []
_all_read_conns_lock = threading.Lock()
_conn_generation: int = 0                # bumped on every invalidation


class _TimedConnection(sqlite3.Connection):
    """sqlite3.Connection subclass — times execute() and logs slow queries."""
    _slow_ms: int = 200

    def execute(self, sql: str, parameters=(), /):
        if getattr(_slow_query_recording, "active", False):
            return super().execute(sql, parameters)
        t0 = _time.perf_counter()
        try:
            return super().execute(sql, parameters)
        finally:
            elapsed_ms = int((_time.perf_counter() - t0) * 1000)
            if elapsed_ms >= self._slow_ms:
                self._record_slow(sql, elapsed_ms)

    def _record_slow(self, sql: str, elapsed_ms: int) -> None:
        _slow_query_recording.active = True
        try:
            from app.db.perf_log import insert_perf_log
            insert_perf_log(
                kind="QUERY",
                name=sql.strip()[:300],
                duration_ms=elapsed_ms,
                is_slow=True,
            )
        except Exception:
            pass
        finally:
            _slow_query_recording.active = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _ensure_app_setting_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_setting (
          setting_key TEXT PRIMARY KEY,
          setting_value TEXT,
          updated_at TEXT NOT NULL
        );
        """
    )


def _make_read_conn(settings) -> _TimedConnection:
    conn = sqlite3.connect(
        settings.db_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        factory=_TimedConnection,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL").fetchone()
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA cache_size = -65536")
    with _all_read_conns_lock:
        _all_read_conns.append(conn)
    return conn


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    global _conn_generation
    settings = get_settings()
    _ensure_parent_dir(settings.db_path)
    _TimedConnection._slow_ms = settings.perf_slow_query_ms

    cached_conn = getattr(_read_local, "conn", None)
    cached_gen = getattr(_read_local, "generation", -1)
    cached_path = getattr(_read_local, "db_path", None)
    if (cached_conn is None
            or cached_gen != _conn_generation
            or cached_path != settings.db_path):
        if cached_conn is not None:
            try:
                cached_conn.close()
            except Exception:
                pass
        _read_local.conn = _make_read_conn(settings)
        _read_local.generation = _conn_generation
        _read_local.db_path = settings.db_path
        _read_local.depth = 0

    _read_local.depth += 1
    conn = _read_local.conn
    try:
        yield conn
        if _read_local.depth == 1:
            conn.commit()
    except Exception:
        if _read_local.depth == 1:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        _read_local.depth -= 1


def invalidate_read_conn_cache() -> None:
    """DB 파일 교체(복구) 후 모든 스레드의 캐시된 읽기 커넥션을 무효화."""
    global _conn_generation, _all_read_conns
    with _all_read_conns_lock:
        _conn_generation += 1
        for c in _all_read_conns:
            try:
                c.close()
            except Exception:
                pass
        _all_read_conns = []
    _read_local.conn = None
    _read_local.depth = 0
    _read_local.generation = -1


@contextmanager
def get_write_conn() -> Generator[sqlite3.Connection, None, None]:
    """Connection that begins an IMMEDIATE transaction up-front.

    Use this in place of `get_conn` for any function that performs multiple
    write statements (inserts/updates/deletes) that must be a single atomic
    unit, especially when concurrent writers (auto-backup thread, metadata
    sync worker, user requests) might race for the SQLite WAL write lock.

    With the default DEFERRED isolation, two writers that BEGIN at the same
    time will both succeed initially and only collide on the first write,
    which on busy systems leaves one of them with a partial work-set when
    SQLITE_BUSY fires past the timeout. IMMEDIATE acquires the write lock
    first, so contenders block at BEGIN — predictably and atomically.

    The connection is configured with `isolation_level=None` (autocommit
    mode) and we manage `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` ourselves.
    """
    settings = get_settings()
    _ensure_parent_dir(settings.db_path)
    _TimedConnection._slow_ms = settings.perf_slow_query_ms
    conn = sqlite3.connect(
        settings.db_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        isolation_level=None,
        factory=_TimedConnection,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL").fetchone()
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN IMMEDIATE")
    committed = False
    try:
        yield conn
        conn.execute("COMMIT")
        committed = True
    finally:
        if not committed:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        conn.close()
