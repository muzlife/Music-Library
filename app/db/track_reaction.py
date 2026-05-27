"""Track reaction DB surface — customer emoji reactions to played tracks."""
from __future__ import annotations
import sqlite3
from typing import Any
from app.db import get_conn, utc_now_iso


def _ensure_track_reaction_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_reaction (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          track_request_id INTEGER NOT NULL,
          table_number TEXT NOT NULL,
          reaction_type TEXT NOT NULL,
          free_text TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (track_request_id) REFERENCES customer_track_request(id) ON DELETE CASCADE
        )
    """)


def insert_track_reaction(track_request_id: int, table_number: str, reaction_type: str, free_text: str | None = None) -> int:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_track_reaction_table(conn)
        cur = conn.execute(
            "INSERT INTO track_reaction (track_request_id, table_number, reaction_type, free_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (track_request_id, table_number.strip(), reaction_type.strip().upper(), free_text, now),
        )
        return cur.lastrowid or 0


def list_reactions_by_request(track_request_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_track_reaction_table(conn)
        rows = conn.execute("SELECT * FROM track_reaction WHERE track_request_id = ? ORDER BY created_at", (track_request_id,)).fetchall()
    return [dict(r) for r in rows]


__all__ = ["_ensure_track_reaction_table", "insert_track_reaction", "list_reactions_by_request"]
