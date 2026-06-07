"""General-purpose audit log for operator-facing change tracking.

snapshot_json format (when before/after provided):
  {"field": {"b": before_value, "a": after_value}, ...}

Legacy format (when only snapshot provided):
  {field: value, ...}  — after-state only (older records)
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import get_conn, utc_now_iso

_ALLOWED_ACTIONS = {
    "CREATE", "UPDATE", "DELETE",
    "MERGE", "MEMBER_LINK", "MEMBER_UNLINK",
    "SPOTIFY_MATCH", "SPOTIFY_CLEAR",
    "BULK_UPDATE", "IMAGE_UPLOAD", "IMAGE_DELETE",
}


def _ensure_audit_log_table(conn: sqlite3.Connection) -> None:
    # No CHECK constraint — action set is open for extension
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          entity_type TEXT NOT NULL,
          entity_id INTEGER NOT NULL,
          action TEXT NOT NULL,
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


def _build_diff(before: dict[str, Any], after: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
    """Return {field: {b: before_val, a: after_val}} for fields that changed."""
    keys = fields if fields else sorted(set(before.keys()) | set(after.keys()))
    return {
        k: {"b": before.get(k), "a": after.get(k)}
        for k in keys
        if str(before.get(k) or "") != str(after.get(k) or "")
    }


def log_audit_event(
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    changed_by: str | None = None,
    changed_fields: list[str] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Record an audit event.

    Preferred call style: pass *before* and *after* dicts.
    The function computes the diff and stores {field: {b:, a:}} in snapshot_json.
    changed_fields is auto-derived from the diff when not given.

    Legacy: pass *snapshot* (after-state only) + *changed_fields*.
    """
    action_u = str(action).strip().upper()

    if before is not None and after is not None:
        diff = _build_diff(before, after, changed_fields)
        if not diff:
            return  # nothing actually changed
        if not changed_fields:
            changed_fields = sorted(diff.keys())
        snapshot_to_store: dict[str, Any] | None = diff
    else:
        snapshot_to_store = snapshot

    params = (
        str(entity_type).strip(),
        int(entity_id),
        action_u,
        str(changed_by).strip() if changed_by else None,
        json.dumps(changed_fields, ensure_ascii=True) if changed_fields else None,
        json.dumps(snapshot_to_store, ensure_ascii=True, default=str) if snapshot_to_store else None,
        utc_now_iso(),
    )

    def _insert(c: sqlite3.Connection) -> None:
        _ensure_audit_log_table(c)
        c.execute(
            "INSERT INTO audit_log (entity_type, entity_id, action, changed_by, changed_fields, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            params,
        )

    if conn is not None:
        _insert(conn)
    else:
        try:
            with get_conn() as c:
                _insert(c)
        except Exception:
            pass  # audit log must never break the caller


def list_audit_log(
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    changed_by: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    with get_conn() as conn:
        _ensure_audit_log_table(conn)
        base = "FROM audit_log WHERE 1=1"
        params: list[Any] = []
        if entity_type is not None:
            base += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id is not None:
            base += " AND entity_id = ?"
            params.append(entity_id)
        if action is not None:
            base += " AND action = ?"
            params.append(action.strip().upper())
        if changed_by is not None:
            base += " AND changed_by LIKE ?"
            params.append(f"%{changed_by}%")
        if date_from is not None:
            base += " AND created_at >= ?"
            params.append(date_from)
        if date_to is not None:
            base += " AND created_at <= ?"
            params.append(date_to)
        total_count = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * {base} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"items": [dict(r) for r in rows], "total_count": int(total_count)}


__all__ = [
    "_ensure_audit_log_table",
    "_build_diff",
    "log_audit_event",
    "list_audit_log",
]
