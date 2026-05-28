"""Cafe playlist DB — staff-curated playlists mixing Spotify + local tracks."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db.connection import get_conn, utc_now_iso
from app.db.table_device import get_table_by_device, register_table_device, list_table_devices
from app.db.track_reaction import insert_track_reaction, list_reactions_by_request
from app.db.customer_track_request import get_customer_track_request


def _ensure_playlist_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cafe_playlist (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          created_by TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cafe_playlist_item (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          playlist_id INTEGER NOT NULL,
          spotify_track_id TEXT,
          spotify_track_uri TEXT,
          local_file_path TEXT,
          title TEXT NOT NULL,
          artist TEXT NOT NULL,
          album_art_url TEXT,
          sort_order INTEGER NOT NULL DEFAULT 0,
          added_by TEXT,
          added_at TEXT NOT NULL,
          FOREIGN KEY (playlist_id) REFERENCES cafe_playlist(id) ON DELETE CASCADE
        )
    """)


# ── playlists ──────────────────────────────────────────────────

def create_playlist(name: str, created_by: str | None = None) -> dict[str, Any] | None:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        cur = conn.execute(
            "INSERT INTO cafe_playlist (name, created_by, created_at, updated_at) VALUES (?,?,?,?)",
            (name.strip(), created_by, now, now),
        )
        return get_playlist(cur.lastrowid)


def get_playlist(playlist_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        row = conn.execute("SELECT * FROM cafe_playlist WHERE id=?", (playlist_id,)).fetchone()
    return dict(row) if row else None


def list_playlists() -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        rows = conn.execute("SELECT * FROM cafe_playlist ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_playlist(playlist_id: int) -> bool:
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        conn.execute("DELETE FROM cafe_playlist_item WHERE playlist_id=?", (playlist_id,))
        cur = conn.execute("DELETE FROM cafe_playlist WHERE id=?", (playlist_id,))
        return cur.rowcount > 0


# ── playlist items ─────────────────────────────────────────────

def add_playlist_item(
    playlist_id: int,
    title: str,
    artist: str,
    spotify_track_id: str | None = None,
    spotify_track_uri: str | None = None,
    local_file_path: str | None = None,
    album_art_url: str | None = None,
    added_by: str | None = None,
) -> int:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM cafe_playlist_item WHERE playlist_id=?", (playlist_id,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO cafe_playlist_item (playlist_id, spotify_track_id, spotify_track_uri, local_file_path, title, artist, album_art_url, sort_order, added_by, added_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (playlist_id, spotify_track_id, spotify_track_uri, local_file_path, title, artist, album_art_url, max_order + 1, added_by, now),
        )
        conn.execute("UPDATE cafe_playlist SET updated_at=? WHERE id=?", (now, playlist_id))
        return cur.lastrowid or 0


def get_playlist_items(playlist_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        rows = conn.execute(
            "SELECT * FROM cafe_playlist_item WHERE playlist_id=? ORDER BY sort_order", (playlist_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def remove_playlist_item(item_id: int) -> bool:
    with get_conn() as conn:
        _ensure_playlist_tables(conn)
        cur = conn.execute("DELETE FROM cafe_playlist_item WHERE id=?", (item_id,))
        return cur.rowcount > 0


def get_next_playlist_item(playlist_id: int, current_index: int = -1) -> dict[str, Any] | None:
    """Get the next unplayed item in the playlist."""
    items = get_playlist_items(playlist_id)
    next_idx = current_index + 1
    if 0 <= next_idx < len(items):
        return items[next_idx]
    return None


# ── new operations helpers ──────────────────────────────────────

def rollback_customer_track_request(request_id: int) -> dict[str, Any] | None:
    """Rollback a completed/cancelled track request back to REQUESTED status."""
    now = utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE customer_track_request
            SET status = 'REQUESTED',
                played_at = NULL,
                returned_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, int(request_id)),
        )
    return get_customer_track_request(int(request_id))


def get_shelf_location_by_owned_item(owned_item_id: int) -> dict[str, Any] | None:
    """Retrieve the physical cabinet slot code and display name for an owned item."""
    from app.db import _storage_slot_display_name
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT ss.slot_code, ss.cabinet_name, ss.column_code, ss.cell_code, ss.allowed_size_group, ss.is_overflow_zone
            FROM owned_item oi
            JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.id = ?
            """,
            (int(owned_item_id),),
        ).fetchone()
        if row:
            display_name = _storage_slot_display_name(dict(row))
            return {
                "slot_code": row["slot_code"],
                "display_name": display_name
            }
        return None


__all__ = [
    "_ensure_playlist_tables",
    "create_playlist", "get_playlist", "list_playlists", "delete_playlist",
    "add_playlist_item", "get_playlist_items", "remove_playlist_item", "get_next_playlist_item",
    "rollback_customer_track_request", "get_shelf_location_by_owned_item",
]
