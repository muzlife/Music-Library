"""Local music file index — caches NAS file listing + metadata in SQLite for fast search."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from app.db import get_conn, utc_now_iso

MUSIC_ROOT = "/Volumes/Music"
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".aiff", ".wma"}


def _ensure_index_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS local_music_index (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_path TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          artist TEXT NOT NULL,
          album TEXT,
          genre TEXT,
          year TEXT,
          track_number INTEGER,
          duration_seconds REAL,
          file_size INTEGER,
          has_cover INTEGER NOT NULL DEFAULT 0,
          indexed_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_title ON local_music_index (title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_artist ON local_music_index (artist)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_genre ON local_music_index (genre)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_album ON local_music_index (album)")


def _read_tags(file_path: str) -> dict[str, Any]:
    """Extract metadata from audio file using tinytag."""
    try:
        from tinytag import TinyTag
        tag = TinyTag.get(file_path)
        return {
            "title": str(tag.title or "").strip(),
            "artist": str(tag.artist or "").strip(),
            "album": str(tag.album or "").strip(),
            "genre": str(tag.genre or "").strip(),
            "year": str(tag.year or "") if tag.year else "",
            "track_number": int(tag.track or 0) if tag.track else 0,
            "duration_seconds": round(tag.duration or 0, 1),
        }
    except Exception:
        return {}


def rebuild_index() -> dict[str, Any]:
    """Scan NAS and rebuild the local file index. Extracts ID3 tags. Takes ~5 min."""
    start = time.time()
    indexed = 0
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_index_table(conn)
        conn.execute("DELETE FROM local_music_index")

        try:
            proc = subprocess.Popen(
                ["find", MUSIC_ROOT, "-type", "f"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            batch = []
            for line in proc.stdout:
                fp = line.strip()
                if not fp:
                    continue
                ext = Path(fp).suffix.lower()
                if ext not in AUDIO_EXTS:
                    continue

                # Extract tags
                tags = _read_tags(fp)
                title = tags.get("title") or ""
                artist = tags.get("artist") or ""
                if not title and not artist:
                    # Fallback: parse from filename
                    name = Path(fp).stem
                    if " - " in name:
                        parts = name.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    else:
                        title = name

                album = tags.get("album") or str(Path(fp).parent.name)
                genre = tags.get("genre") or ""
                year = tags.get("year") or ""
                track_num = tags.get("track_number") or 0
                duration = tags.get("duration_seconds") or 0.0

                try:
                    fsize = os.path.getsize(fp)
                except OSError:
                    fsize = 0

                # Check for embedded cover art
                has_cover = 0
                try:
                    ttag = __import__('tinytag', fromlist=['TinyTag']).TinyTag.get(fp, image=True)
                    if ttag.get_image():
                        has_cover = 1
                except Exception:
                    pass

                batch.append((fp, title, artist, album, genre, year, track_num, duration, fsize, has_cover, now))
                indexed += 1

                if len(batch) >= 200:
                    conn.executemany(
                        "INSERT OR REPLACE INTO local_music_index (file_path, title, artist, album, genre, year, track_number, duration_seconds, file_size, has_cover, indexed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        batch,
                    )
                    if indexed % 1000 == 0:
                        print(f"  indexed {indexed} files...")
                    batch = []

            if batch:
                conn.executemany(
                    "INSERT OR REPLACE INTO local_music_index (file_path, title, artist, album, genre, year, track_number, duration_seconds, file_size, has_cover, indexed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
            proc.wait(timeout=600)
        except Exception:
            pass

    elapsed = time.time() - start
    return {"indexed": indexed, "elapsed_seconds": round(elapsed, 1)}


def search_local_index(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search the local index by title, artist, album, or genre."""
    q = f"%{query.strip()}%"
    with get_conn() as conn:
        _ensure_index_table(conn)
        rows = conn.execute(
            "SELECT * FROM local_music_index WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ? ORDER BY title LIMIT ?",
            (q, q, q, q, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_index_stats() -> dict[str, Any]:
    with get_conn() as conn:
        _ensure_index_table(conn)
        total = conn.execute("SELECT COUNT(*) FROM local_music_index").fetchone()[0]
        last = conn.execute("SELECT MAX(indexed_at) FROM local_music_index").fetchone()[0]
        genres = conn.execute(
            "SELECT genre, COUNT(*) as cnt FROM local_music_index WHERE genre != '' GROUP BY genre ORDER BY cnt DESC LIMIT 20"
        ).fetchall()
    return {
        "total_files": total,
        "last_indexed": last,
        "top_genres": [{"genre": r[0], "count": r[1]} for r in genres],
    }


def backfill_durations(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For tracks with duration_seconds == 0, read from file via tinytag and update DB."""
    missing = [t for t in tracks if not t.get("duration_seconds")]
    if not missing:
        return tracks
    try:
        from tinytag import TinyTag
    except ImportError:
        return tracks
    updates: list[tuple[float, str]] = []
    dur_map: dict[str, float] = {}
    for t in missing:
        fp = t.get("file_path", "")
        if not fp or not os.path.isfile(fp):
            continue
        try:
            tag = TinyTag.get(fp)
            dur = round(tag.duration or 0.0, 1)
        except Exception:
            dur = 0.0
        if dur > 0:
            dur_map[fp] = dur
            updates.append((dur, fp))
    if updates:
        with get_conn() as conn:
            conn.executemany(
                "UPDATE local_music_index SET duration_seconds = ? WHERE file_path = ?",
                updates,
            )
    return [
        {**t, "duration_seconds": dur_map.get(t.get("file_path", ""), t.get("duration_seconds", 0))}
        for t in tracks
    ]


def get_local_track_by_path(file_path: str) -> dict[str, Any] | None:
    """Get metadata for a local track from the index. Falls back to dynamic reading if missing in DB."""
    with get_conn() as conn:
        _ensure_index_table(conn)
        row = conn.execute(
            "SELECT * FROM local_music_index WHERE file_path = ?",
            (file_path,),
        ).fetchone()
    if row:
        return dict(row)
    
    # Fallback to dynamic parsing
    if os.path.isfile(file_path):
        tags = _read_tags(file_path)
        if not tags:
            # Fallback parsing from filename
            name = Path(file_path).stem
            artist = ""
            title = name
            if " - " in name:
                parts = name.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            tags = {
                "title": title,
                "artist": artist,
                "album": str(Path(file_path).parent.name),
                "genre": "",
                "year": "",
                "track_number": 0,
                "duration_seconds": 0.0,
            }
        # Check has_cover
        has_cover = 0
        try:
            from tinytag import TinyTag
            ttag = TinyTag.get(file_path, image=True)
            if ttag.get_image():
                has_cover = 1
        except Exception:
            pass
        tags["has_cover"] = has_cover
        tags["file_path"] = file_path
        return tags
    return None


# Re-export
__all__ = ["_ensure_index_table", "rebuild_index", "search_local_index", "get_index_stats", "get_local_track_by_path", "backfill_durations"]
