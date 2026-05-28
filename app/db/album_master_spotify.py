"""Spotify matching for album_master — multi-strategy auto-matching.

Strategy pipeline (each tries in order until success):
  1. Album search: artist + title → match Spotify album
  2. Track search: pick representative tracks → search by "artist track"
     → collect album IDs, majority vote
  3. Title-only fallback

Validation: cross-check album name similarity, skip compilations.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.db.connection import get_conn, utc_now_iso

logger = logging.getLogger(__name__)


# ── helpers ─────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    s = str(s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_track_names(track_list_json: str | None) -> list[str]:
    """Parse track_list_json like ['A1 Track Name', ...] → clean track names."""
    if not track_list_json:
        return []
    try:
        raw = json.loads(track_list_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    names = []
    for item in raw:
        if not isinstance(item, str):
            continue
        # Strip side prefix like "A1 ", "B2 ", "1. ", "01 - ", etc.
        cleaned = re.sub(r"^[A-H]\d{1,2}\s+", "", item)
        cleaned = re.sub(r"^\d{1,2}[\.\)\-]\s*", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned and len(cleaned) > 1:
            names.append(cleaned)
    return names


def _pick_representative_tracks(track_names: list[str], count: int = 3) -> list[str]:
    """Pick diverse tracks: first, middle, and last non-instrumental."""
    if not track_names:
        return []
    candidates = [t for t in track_names if len(t) > 3]
    if len(candidates) <= count:
        return candidates
    # Pick first, middle, last for diversity
    result = [candidates[0]]
    if count >= 3 and len(candidates) >= 3:
        result.append(candidates[len(candidates) // 2])
        result.append(candidates[-1])
    elif count >= 2:
        result.append(candidates[-1])
    return result


def _titles_match(db_title: str, spotify_album_name: str) -> bool:
    """Check if Spotify album name reasonably matches DB title."""
    d = _norm(db_title)
    s = _norm(spotify_album_name)
    if not d or not s:
        return False
    # Direct containment
    if d in s or s in d:
        return True
    # Word overlap
    dw = set(d.split())
    sw = set(s.split())
    if not dw:
        return False
    overlap = dw & sw
    # At least 60% of DB title words must be in Spotify result
    return len(overlap) >= max(1, len(dw) * 0.5)


def _is_compilation(spotify_album_name: str) -> bool:
    """Check if a Spotify album name looks like a compilation."""
    s = str(spotify_album_name or "").lower()
    compilation_keywords = [
        "greatest hits", "best of", "collection", "anthology",
        "compilation", "various artists", "soundtrack", "ost",
        "original motion picture", "tribute to", "gold", "platinum",
        "ultimate", "definitive", "essential", "very best",
        "complete", "box set", "deluxe edition", "remastered",
    ]
    for kw in compilation_keywords:
        if kw in s:
            return True
    return False


def _resolve_album_from_track(sp: Any, spotify_track_id: str) -> dict[str, str | None]:
    """Given a Spotify track ID, return {album_id, album_uri, album_name}."""
    client = sp._ensure_client()
    if client is None:
        return {}
    try:
        track = client.track(spotify_track_id)
        album = track.get("album", {})
        return {
            "album_id": album.get("id"),
            "album_uri": album.get("uri"),
            "album_name": album.get("name", ""),
        }
    except Exception:
        logger.debug("Failed to resolve album from track %s", spotify_track_id)
        return {}


# ── matching strategies ─────────────────────────────────────────────

def _match_by_album_search(sp: Any, artist: str, title: str) -> dict[str, str | None] | None:
    """Strategy 1: Search Spotify by artist + title, return best album match."""
    query = f"{artist} {title}" if artist else title
    results = sp.search_tracks_sync(query, limit=5)
    if not results:
        return None

    for r in results:
        album_name = r.get("album_name", "")
        if _is_compilation(album_name):
            continue
        if _titles_match(title, album_name):
            album = _resolve_album_from_track(sp, r.get("spotify_track_id", ""))
            if album.get("album_id"):
                album["match_method"] = "album_search"
                return album
    return None


def _match_by_track_search(
    sp: Any, artist: str, track_names: list[str]
) -> dict[str, str | None] | None:
    """Strategy 2: Search by "artist + track_name", vote on album ID."""
    candidates = _pick_representative_tracks(track_names, count=3)
    if not candidates:
        return None

    album_votes: dict[str, int] = {}
    album_details: dict[str, dict[str, str | None]] = {}

    for track in candidates:
        query = f"{artist} {track}" if artist else track
        results = sp.search_tracks_sync(query, limit=3)
        if not results:
            continue
        for r in results:
            album = _resolve_album_from_track(sp, r.get("spotify_track_id", ""))
            aid = album.get("album_id")
            if not aid:
                continue
            album_votes[aid] = album_votes.get(aid, 0) + 1
            if aid not in album_details:
                # Also verify track name closeness
                track_name = r.get("title", "")
                if _norm(track)[:5] in _norm(track_name) or _norm(track_name)[:5] in _norm(track):
                    album_votes[aid] = album_votes.get(aid, 0) + 1  # bonus for track match
                album_details[aid] = album

    if not album_votes:
        return None

    # Pick the album with most votes
    best_id = max(album_votes, key=album_votes.get)
    if album_votes[best_id] < 2:
        return None  # need at least 2 votes for confidence

    result = dict(album_details[best_id])
    result["match_method"] = "track_search"
    return result


def _match_by_title_only(sp: Any, title: str) -> dict[str, str | None] | None:
    """Strategy 3: Title-only search as last resort."""
    results = sp.search_tracks_sync(title, limit=3)
    if not results:
        return None
    for r in results:
        album_name = r.get("album_name", "")
        if _is_compilation(album_name):
            continue
        if _titles_match(title, album_name):
            album = _resolve_album_from_track(sp, r.get("spotify_track_id", ""))
            if album.get("album_id"):
                album["match_method"] = "title_only"
                return album
    return None


# ── main matcher ────────────────────────────────────────────────────

def match_spotify_for_master(conn: Any, master_id: int, sp: Any) -> dict[str, Any]:
    """Multi-strategy match for one album_master. Returns result dict."""
    row = conn.execute(
        """SELECT am.id, am.title, am.artist_or_brand,
                  (SELECT mid.track_list_json FROM album_master_member amm
                   JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
                   WHERE amm.album_master_id = am.id
                     AND mid.track_list_json IS NOT NULL AND mid.track_list_json <> '[]'
                   LIMIT 1) AS track_list_json
           FROM album_master am WHERE am.id = ?""",
        (master_id,),
    ).fetchone()

    if not row:
        return {"master_id": master_id, "matched": False, "reason": "not_found"}

    title = str(row["title"] or "").strip()
    artist = str(row["artist_or_brand"] or "").strip()
    track_names = _extract_track_names(row["track_list_json"])

    if not title:
        return {"master_id": master_id, "matched": False, "reason": "no_title"}

    # Strategy pipeline
    result = None
    strategy = None

    # 1. Album search (artist + title)
    result = _match_by_album_search(sp, artist, title)
    if result:
        strategy = "album_search"

    # 2. Track search (artist + representative tracks)
    if not result and track_names and artist:
        result = _match_by_track_search(sp, artist, track_names)
        if result:
            strategy = "track_search"

    # 3. Title-only fallback
    if not result:
        result = _match_by_title_only(sp, title)
        if result:
            strategy = "title_only"

    if not result or not result.get("album_id"):
        return {
            "master_id": master_id,
            "matched": False,
            "reason": "no_spotify_match",
            "tracks_available": len(track_names),
        }

    # Store
    now = utc_now_iso()
    conn.execute(
        """UPDATE album_master
           SET spotify_album_id = ?, spotify_album_uri = ?, spotify_matched_at = ?, updated_at = ?
           WHERE id = ?""",
        (result["album_id"], result["album_uri"], now, now, master_id),
    )
    conn.commit()

    return {
        "master_id": master_id,
        "matched": True,
        "strategy": strategy,
        "spotify_album_id": result["album_id"],
        "spotify_album_name": result.get("album_name", ""),
        "tracks_available": len(track_names),
    }


# ── batch ───────────────────────────────────────────────────────────

def batch_match_spotify(
    sp: Any,
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
                """SELECT id FROM album_master
                   WHERE (spotify_album_id IS NULL OR TRIM(spotify_album_id) = '')
                     AND title IS NOT NULL AND TRIM(title) <> ''
                   ORDER BY updated_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id FROM album_master
                   WHERE title IS NOT NULL AND TRIM(title) <> ''
                   ORDER BY updated_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()

        for row in rows:
            try:
                result = match_spotify_for_master(conn, row["id"], sp)
                if result["matched"]:
                    matched += 1
                else:
                    skipped += 1
                time.sleep(0.25)  # rate limit (~4 req/s)
            except Exception:
                logger.exception("Spotify match failed for master %s", row["id"])
                errors += 1

    return {"matched": matched, "skipped": skipped, "errors": errors}
