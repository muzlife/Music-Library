"""General-purpose audit log for operator-facing change tracking.

Records CREATE/UPDATE/DELETE events on key entities (owned_item,
storage_slot, auth_account) with the acting username, changed field
names, and a JSON snapshot of the after-state.

Table is auto-created on first write.  Reads are served by
app/api/audit_log.py.  Write hooks are called from the existing DB
write functions in __init__.py and the per-entity modules.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import get_conn, utc_now_iso


def _ensure_audit_log_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          entity_type TEXT NOT NULL,
          entity_id INTEGER NOT NULL,
          action TEXT NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'DELETE')),
          changed_by TEXT,
          changed_fields TEXT,
          snapshot_json TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log (entity_type, entity_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at DESC)"
    )


def log_audit_event(
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    changed_by: str | None = None,
    changed_fields: list[str] | None = None,
    snapshot: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Record an audit event.  If *conn* is passed the INSERT runs in
    the existing transaction; otherwise a short-lived connection is
    used (fire-and-forget — a failure here must not roll back the
    caller's business transaction)."""
    params = (
        str(entity_type).strip(),
        int(entity_id),
        str(action).strip().upper(),
        str(changed_by).strip() if changed_by else None,
        json.dumps(changed_fields, ensure_ascii=True) if changed_fields else None,
        json.dumps(snapshot, ensure_ascii=True, default=str) if snapshot else None,
        utc_now_iso(),
    )
    if conn is not None:
        _ensure_audit_log_table(conn)
        conn.execute(
            "INSERT INTO audit_log (entity_type, entity_id, action, changed_by, changed_fields, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            params,
        )
    else:
        try:
            with get_conn() as c:
                _ensure_audit_log_table(c)
                c.execute(
                    "INSERT INTO audit_log (entity_type, entity_id, action, changed_by, changed_fields, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    params,
                )
        except Exception:
            pass  # audit log must never break the caller


def list_audit_log(
    entity_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_audit_log_table(conn)
        if entity_type:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE entity_type = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (entity_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "_ensure_audit_log_table",
    "log_audit_event",
    "list_audit_log",
]
