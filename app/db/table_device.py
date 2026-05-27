"""Table device registry — maps tablet UUIDs to table numbers."""
from __future__ import annotations
import sqlite3
from typing import Any
from app.db import get_conn, utc_now_iso


def _ensure_table_device_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_device (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          table_number TEXT NOT NULL UNIQUE,
          device_label TEXT,
          device_id TEXT UNIQUE,
          is_active INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
    """)


def register_table_device(table_number: str, device_id: str, device_label: str = "") -> dict[str, Any] | None:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_table_device_table(conn)
        conn.execute(
            "INSERT INTO table_device (table_number, device_id, device_label, is_active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?) ON CONFLICT(table_number) DO UPDATE SET device_id=excluded.device_id, device_label=excluded.device_label, updated_at=excluded.updated_at",
            (table_number.strip(), device_id.strip(), device_label.strip(), now, now),
        )
    return get_table_by_device(device_id)


def get_table_by_device(device_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        _ensure_table_device_table(conn)
        row = conn.execute("SELECT * FROM table_device WHERE device_id = ? AND is_active = 1 LIMIT 1", (device_id.strip(),)).fetchone()
    return dict(row) if row else None


def list_table_devices() -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_table_device_table(conn)
        rows = conn.execute("SELECT * FROM table_device ORDER BY table_number").fetchall()
    return [dict(r) for r in rows]


def deactivate_table_device(device_id: str) -> bool:
    with get_conn() as conn:
        _ensure_table_device_table(conn)
        cur = conn.execute("UPDATE table_device SET is_active = 0, updated_at = ? WHERE device_id = ?", (utc_now_iso(), device_id.strip()))
        return cur.rowcount > 0


__all__ = ["_ensure_table_device_table", "register_table_device", "get_table_by_device", "list_table_devices", "deactivate_table_device"]
