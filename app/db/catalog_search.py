from __future__ import annotations

import json
import sqlite3

__all__ = [
    "extract_tracks_text",
    "fts_escape",
    "upsert_catalog_search_in_conn",
    "delete_catalog_search_in_conn",
    "upsert_album_master_fts_in_conn",
    "delete_album_master_fts_in_conn",
]


def extract_tracks_text(track_items_json: str, track_list_json: str) -> str:
    titles: list[str] = []

    if track_items_json:
        try:
            items = json.loads(track_items_json)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        if "display" in item and isinstance(item["display"], str):
                            titles.append(item["display"])
                        elif "title" in item and isinstance(item["title"], str):
                            titles.append(item["title"])
        except (json.JSONDecodeError, TypeError):
            pass

    if track_list_json:
        try:
            entries = json.loads(track_list_json)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, str):
                        titles.append(entry)
                    elif isinstance(entry, dict) and "title" in entry and isinstance(entry["title"], str):
                        titles.append(entry["title"])
        except (json.JSONDecodeError, TypeError):
            pass

    return " ".join(titles)


def fts_escape(text: str) -> str:
    escaped = text.replace('"', '""')
    return f'"{escaped}"'


def upsert_catalog_search_in_conn(conn: sqlite3.Connection, owned_item_id: int) -> None:
    row = conn.execute(
        """
        SELECT oi.item_name_override, mid.artist_or_brand, mid.label_name,
               mid.catalog_no, mid.barcode, mid.track_items_json,
               mid.track_list_json, oi.memory_note
        FROM owned_item oi
        LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
        WHERE oi.id = ?
        """,
        (owned_item_id,),
    ).fetchone()

    if row is None:
        return

    item_name, artist, label_name, catalog_no, barcode, track_items_json, track_list_json, memory_note = row

    tracks_text = extract_tracks_text(track_items_json or "", track_list_json or "")

    conn.execute("DELETE FROM catalog_search WHERE rowid = ?", (owned_item_id,))
    conn.execute(
        """
        INSERT INTO catalog_search(rowid, item_name, artist, label_name,
                                   catalog_no, barcode, tracks_text, memory_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (owned_item_id, item_name, artist, label_name, catalog_no, barcode, tracks_text, memory_note),
    )


def delete_catalog_search_in_conn(conn: sqlite3.Connection, owned_item_id: int) -> None:
    conn.execute("DELETE FROM catalog_search WHERE rowid = ?", (owned_item_id,))


def upsert_album_master_fts_in_conn(conn: sqlite3.Connection, album_master_id: int) -> None:
    row = conn.execute(
        "SELECT title, artist_or_brand FROM album_master WHERE id = ?",
        (album_master_id,),
    ).fetchone()

    if row is None:
        return

    title, artist = row

    conn.execute("DELETE FROM album_master_fts WHERE rowid = ?", (album_master_id,))
    conn.execute(
        "INSERT INTO album_master_fts(rowid, title, artist) VALUES (?, ?, ?)",
        (album_master_id, title, artist),
    )


def delete_album_master_fts_in_conn(conn: sqlite3.Connection, album_master_id: int) -> None:
    conn.execute("DELETE FROM album_master_fts WHERE rowid = ?", (album_master_id,))
