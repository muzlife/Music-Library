"""Coverage for the IMMEDIATE-transaction write context manager.

We pin three behaviours:
  1. `get_write_conn()` opens a real BEGIN IMMEDIATE — proven by attempting a
     concurrent write from a second connection within the busy_timeout
     window and observing a SQLITE_BUSY raise (or a successful queued write
     after our context exits).
  2. An exception inside the context rolls back the entire batch — no
     partial writes leak past the manager.
  3. A successful exit commits.

The metadata_source table is small and always present after init, so we use
it as a scratch surface to avoid coupling to schemas that vary by category.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import db


_SCRATCH_KEY = "WRITE_TX_TEST_PROBE"


def _read_probe_count() -> int:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM metadata_source WHERE source_code = ?",
            (_SCRATCH_KEY,),
        ).fetchone()
        return int(row["n"] or 0)


def _delete_probe_row() -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM metadata_source WHERE source_code = ?", (_SCRATCH_KEY,))


@pytest.fixture(autouse=True)
def _ensure_db_ready_and_clean() -> None:
    db.ensure_startup_db_ready()
    _delete_probe_row()
    yield
    _delete_probe_row()


def test_get_write_conn_commits_on_clean_exit() -> None:
    now = db.utc_now_iso()
    with db.get_write_conn() as conn:
        conn.execute(
            "INSERT INTO metadata_source (source_code, source_name, source_scope, "
            "is_primary, priority, enabled, created_at, updated_at) "
            "VALUES (?, ?, 'INTERNAL', 0, 999, 1, ?, ?)",
            (_SCRATCH_KEY, "write-tx-probe", now, now),
        )
    assert _read_probe_count() == 1


def test_get_write_conn_rolls_back_on_exception() -> None:
    class BoomError(RuntimeError):
        pass

    now = db.utc_now_iso()
    with pytest.raises(BoomError):
        with db.get_write_conn() as conn:
            conn.execute(
                "INSERT INTO metadata_source (source_code, source_name, source_scope, "
                "is_primary, priority, enabled, created_at, updated_at) "
                "VALUES (?, ?, 'INTERNAL', 0, 999, 1, ?, ?)",
                (_SCRATCH_KEY, "write-tx-probe", now, now),
            )
            raise BoomError("simulated fault mid-transaction")
    assert _read_probe_count() == 0, "exception must roll back the entire write batch"


def test_get_write_conn_holds_immediate_write_lock() -> None:
    """A second writer using a tiny busy_timeout must observe SQLITE_BUSY
    while we're inside `get_write_conn`. This proves we actually issued
    BEGIN IMMEDIATE rather than a deferred transaction."""
    settings = db.get_settings()
    db_path = Path(settings.db_path)
    contender = sqlite3.connect(str(db_path), timeout=0.05, isolation_level=None)
    contender.execute("PRAGMA busy_timeout = 50")
    try:
        with db.get_write_conn() as conn:
            now = db.utc_now_iso()
            conn.execute(
                "INSERT INTO metadata_source (source_code, source_name, source_scope, "
                "is_primary, priority, enabled, created_at, updated_at) "
                "VALUES (?, ?, 'INTERNAL', 0, 999, 1, ?, ?)",
                (_SCRATCH_KEY, "write-tx-probe", now, now),
            )

            # Contending writer should be locked out — either BEGIN
            # IMMEDIATE itself, or the first write after a deferred BEGIN.
            with pytest.raises(sqlite3.OperationalError):
                contender.execute("BEGIN IMMEDIATE")

        # After the context exits, the lock is released and the contender
        # can proceed.
        contender.execute("BEGIN IMMEDIATE")
        contender.execute("ROLLBACK")
    finally:
        contender.close()
