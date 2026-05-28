"""Spotify matching for album_master.

Provides batch matching: search Spotify by artist+title, store
spotify_album_id/uri on album_master.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.db.connection import get_conn, utc_now_iso

logger = logging.getLogger(__name__)


def match_spotify_for_master(conn: Any, master_id: int, sp_service: Any) -> bool:
    """Search Spotify for one album_master and store the match. Returns True if matched."""
    row = conn.execute(
        "SELECT id, title, artist_or_brand FROM album_master WHERE id = ?",
        (master_id,),
    ).fetchone()
    if not row:
        return False

    title = str(row["title"] or "").strip()
    artist = str(row["artist_or_brand"] or "").strip()
    if not title:
        return False

    query = f"{artist} {title}" if artist else title
    results = sp_service.search_tracks_sync(query, limit=3)
    if not results:
        return False

    # Take the first result's album
    best = results[0]
    album_name = best.get("album_name", "")
    # Simple relevance check: album name should contain a meaningful part of the title
    if not _titles_match(title, album_name):
        return False

    # We need the album URI, not track URI. Get it from the track's album info.
    # Spotify track URI format: spotify:track:XXXX, album URI: spotify:album:XXXX
    track_uri = best.get("track_uri", "")
    spotify_track_id = best.get("spotify_track_id", "")

    # Derive album ID/URI from track — we'll search for the album directly
    album_id, album_uri = _resolve_album(sp_service, spotify_track_id)
    if not album_id:
        return False

    now = utc_now_iso()
    conn.execute(
        """UPDATE album_master SET spotify_album_id = ?, spotify_album_uri = ?, spotify_matched_at = ?, updated_at = ?
           WHERE id = ?""",
        (album_id, album_uri, now, now, master_id),
    )
    conn.commit()
    return True


def _titles_match(db_title: str, spotify_title: str) -> bool:
    """Check if Spotify album name is reasonably close to the DB title."""
    import re
    def norm(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r'[^\w\s]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return s
    db_norm = norm(db_title)
    sp_norm = norm(spotify_title)
    # At least one should contain the other, or they share significant words
    if db_norm in sp_norm or sp_norm in db_norm:
        return True
    db_words = set(db_norm.split())
    sp_words = set(sp_norm.split())
    if not db_words:
        return False
    overlap = db_words & sp_words
    return len(overlap) >= len(db_words) * 0.5


def _resolve_album(sp_service: Any, spotify_track_id: str) -> tuple[str | None, str | None]:
    """Given a Spotify track ID, get its album ID and URI."""
    sp = sp_service._ensure_client()
    if sp is None:
        return None, None
    try:
        track = sp.track(spotify_track_id)
        album = track.get("album", {})
        return album.get("id"), album.get("uri")
    except Exception:
        logger.exception("Failed to resolve album from track %s", spotify_track_id)
        return None, None


def batch_match_spotify(
    sp_service: Any,
    limit: int = 50,
    only_unmatched: bool = True,
) -> dict[str, int]:
    """Batch match album_masters to Spotify. Returns {matched, skipped, errors}."""
    matched = 0
    skipped = 0
    errors = 0

    with get_conn() as conn:
        if only_unmatched:
            rows = conn.execute(
                """SELECT id, title, artist_or_brand FROM album_master
                   WHERE (spotify_album_id IS NULL OR TRIM(spotify_album_id) = '')
                   ORDER BY updated_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, artist_or_brand FROM album_master ORDER BY updated_at ASC LIMIT ?",
                (limit,),
            ).fetchall()

        for row in rows:
            try:
                if match_spotify_for_master(conn, row["id"], sp_service):
                    matched += 1
                else:
                    skipped += 1
                time.sleep(0.3)  # rate limit
            except Exception:
                logger.exception("Spotify match failed for master %s", row["id"])
                errors += 1

    return {"matched": matched, "skipped": skipped, "errors": errors}
