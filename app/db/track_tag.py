"""Track tag DB surface — mood/genre/era tags for tracks.

Tags can reference either a local owned_item or a Spotify track.
The table is auto-created on first use.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn, utc_now_iso


def _ensure_track_tag_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track_tag (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tag_type TEXT NOT NULL,
          tag_value TEXT NOT NULL,
          owned_item_id INTEGER,
          spotify_track_id TEXT,
          created_by TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_tag_type_value ON track_tag (tag_type, tag_value)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_tag_owned ON track_tag (owned_item_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_tag_spotify ON track_tag (spotify_track_id)"
    )


def insert_track_tag(
    *,
    tag_type: str,
    tag_value: str,
    owned_item_id: int | None = None,
    spotify_track_id: str | None = None,
    created_by: str | None = None,
) -> int:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_track_tag_table(conn)
        cur = conn.execute(
            "INSERT INTO track_tag (tag_type, tag_value, owned_item_id, spotify_track_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                tag_type.strip().upper(),
                tag_value.strip(),
                owned_item_id,
                spotify_track_id,
                created_by,
                now,
            ),
        )
        return cur.lastrowid or 0


def list_track_tags(tag_type: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_track_tag_table(conn)
        if tag_type:
            rows = conn.execute(
                "SELECT * FROM track_tag WHERE tag_type = ? ORDER BY tag_value",
                (tag_type.strip().upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM track_tag ORDER BY tag_type, tag_value"
            ).fetchall()
    return [dict(r) for r in rows]


def find_tracks_by_tag(tag_value: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_track_tag_table(conn)
        rows = conn.execute(
            "SELECT * FROM track_tag WHERE tag_value = ? LIMIT ?",
            (tag_value.strip(), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_track_tag(tag_id: int) -> bool:
    with get_conn() as conn:
        _ensure_track_tag_table(conn)
        cur = conn.execute("DELETE FROM track_tag WHERE id = ?", (tag_id,))
        return cur.rowcount > 0


__all__ = [
    "_ensure_track_tag_table",
    "insert_track_tag",
    "list_track_tags",
    "find_tracks_by_tag",
    "delete_track_tag",
]
