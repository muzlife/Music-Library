"""Spotify matching for album_master — multi-strategy with track-sequence verification.

Strategy pipeline:
  1. Album search: artist + title → verify track sequence → match
     Skips compilations unless soundtracks with track verification.
  2. Track search: sequential track matching → album vote
     Tracks must match in order (1st, 2nd, 3rd...).
  3. Title-only: soundtracks/compilations only → must verify with tracks.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.db.connection import get_conn, utc_now_iso

logger = logging.getLogger(__name__)


# ── text normalization ──────────────────────────────────────────────

def _norm(s: str) -> str:
    s = str(s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _tokens(s: str) -> set[str]:
    return set(_norm(s).split())


# ── track parsing ───────────────────────────────────────────────────

def _parse_track_names(track_list_json: str | None) -> list[str]:
    """Parse [\"A1 Track Name\", ...] → clean track names."""
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
        cleaned = re.sub(r"^[A-H]\d{1,2}\s+", "", item)
        cleaned = re.sub(r"^\d{1,2}[\.\)\-]\s*", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned and len(cleaned) > 1:
            names.append(cleaned)
    return names


def _get_tracks_for_master(conn: Any, master_id: int) -> list[str]:
    row = conn.execute(
        """SELECT mid.track_list_json FROM album_master_member amm
           JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
           WHERE amm.album_master_id = ? AND mid.track_list_json IS NOT NULL AND mid.track_list_json <> '[]'
           LIMIT 1""",
        (master_id,),
    ).fetchone()
    return _parse_track_names(row["track_list_json"] if row else None)


# ── compilation detection ───────────────────────────────────────────

def _is_compilation(spotify_album_name: str) -> bool:
    s = str(spotify_album_name or "").lower()
    keywords = [
        "greatest hits", "best of", "the best",
        "anthology", "compilation", "various artists",
        "tribute to", "very best",
    ]
    for kw in keywords:
        if kw in s:
            return True
    return False


def _is_soundtrack(title: str) -> bool:
    s = str(title or "").lower()
    keywords = [
        "soundtrack", "ost", "original motion picture",
        "original score", "music from", "motion picture",
        "o.s.t", "o.s.t.", "영화", "드라마",
    ]
    for kw in keywords:
        if kw in s:
            return True
    return False


# ── track sequence verification ─────────────────────────────────────

def _get_spotify_album_tracks(sp: Any, album_id: str) -> list[str]:
    """Get track names from a Spotify album."""
    try:
        items = sp.album_tracks_sync(album_id)
        return [t.get("name", "") for t in items]
    except Exception:
        logger.debug("Failed to get tracks for album %s", album_id)
        return []


def _track_sequence_match(db_tracks: list[str], sp_tracks: list[str], min_match: int = 3) -> int:
    """Count how many DB tracks appear in Spotify tracks IN SEQUENCE.
    
    Checks starting from offset 0, 1, or 2 in sp_tracks.
    """
    if not db_tracks or not sp_tracks:
        return 0
        
    best_matches = 0
    # Try offsets 0, 1, 2
    for offset in (0, 1, 2):
        if offset >= len(sp_tracks):
            continue
        matches = 0
        for i in range(len(db_tracks)):
            sp_idx = i + offset
            if sp_idx >= len(sp_tracks):
                break
            db_t = _norm(db_tracks[i])
            sp_t = _norm(sp_tracks[sp_idx])
            if not db_t or not sp_t:
                continue
            if db_t in sp_t or sp_t in db_t:
                matches += 1
            else:
                db_w = set(db_t.split())
                sp_w = set(sp_t.split())
                if db_w and sp_w:
                    overlap = db_w & sp_w
                    if len(overlap) >= min(len(db_w), len(sp_w)) * 0.6:
                        matches += 1
                    else:
                        break
                else:
                    break
        if matches > best_matches:
            best_matches = matches
            
    return best_matches


# ── album resolution ────────────────────────────────────────────────

def _resolve_album(sp: Any, track_id: str) -> dict[str, Any]:
    """Get album info from a Spotify track ID."""
    try:
        track = sp.track_sync(track_id)
        if not track:
            return {}
        album = track.get("album", {})
        images = album.get("images") or []
        return {
            "album_id": album.get("id"),
            "album_uri": album.get("uri"),
            "album_name": album.get("name", ""),
            "album_artist": ", ".join(a.get("name", "") for a in album.get("artists", [])),
            "release_date": album.get("release_date", ""),
            "image_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
        }
    except Exception:
        return {}


# ── strategy 1: album search ────────────────────────────────────────

def _match_by_album(sp: Any, artist: str, title: str, db_tracks: list[str], release_year: int | None = None) -> dict[str, Any] | None:
    """Search Spotify for artist+title, verify with track sequence."""
    query = f"{artist} {title}" if artist else title
    if release_year and 1900 <= release_year <= 2030:
        query = f"{query} year:{release_year}"
    results = sp.search_albums_sync(query, limit=3)
    if not results and release_year:
        query_no_year = f"{artist} {title}" if artist else title
        results = sp.search_albums_sync(query_no_year, limit=3)
    if not results:
        return None

    is_comp = _is_compilation(title) or _is_soundtrack(title)
    min_tracks = 2 if is_comp else 3  # compilations need fewer due to variant tracklists
    num_db_tracks = len(db_tracks)
    if num_db_tracks > 0:
        min_tracks = min(num_db_tracks, min_tracks)

    required_score = 2 if is_comp else 3
    if num_db_tracks > 0:
        required_score = min(num_db_tracks, required_score)

    best = None
    best_score = 0

    for r in results:
        album_name = r.get("name", "")
        # Skip compilations unless we have tracks to verify
        if _is_compilation(album_name) and not db_tracks:
            continue
        
        aid = r.get("spotify_album_id")
        if not aid:
            continue

        # Verify with track sequence
        score = 0
        if db_tracks:
            sp_tracks = _get_spotify_album_tracks(sp, aid)
            score = _track_sequence_match(db_tracks, sp_tracks, min_match=min_tracks)
        
        # Title match bonus
        if _norm(title) in _norm(album_name) or _norm(album_name) in _norm(title):
            score += 1
        # Release year bonus
        sp_date = r.get("release_date", "")
        if sp_date and len(sp_date) >= 4:
            try:
                sp_year = int(sp_date[:4])
                if 1900 <= sp_year <= 2030:
                    score += 0.5
            except ValueError:
                pass

        if score > best_score:
            best_score = score
            best = {
                "album_id": aid,
                "album_uri": r.get("spotify_album_uri"),
                "album_name": album_name,
                "album_artist": r.get("artist"),
                "release_date": sp_date,
                "image_url": r.get("image_url"),
                "match_method": "album_search",
                "track_score": score,
            }

    if best and best_score >= required_score:
        return best
    return None


# ── strategy 2: sequential track search ─────────────────────────────

def _match_by_tracks(sp: Any, artist: str, db_tracks: list[str]) -> dict[str, Any] | None:
    """Search first 3 tracks sequentially, verify order, vote for best album."""
    if len(db_tracks) < 3:
        return None

    candidates = db_tracks[:3]  # first 3 tracks
    album_votes: dict[str, int] = {}
    album_info: dict[str, dict[str, Any]] = {}

    for idx, track_name in enumerate(candidates):
        query = f"{artist} {track_name}" if artist else track_name
        results = sp.search_tracks_sync(query, limit=3)
        if not results:
            continue

        for r in results:
            album = _resolve_album(sp, r.get("spotify_track_id", ""))
            aid = album.get("album_id")
            if not aid:
                continue

            # Verify this track appears at the expected position in the Spotify album
            sp_tracks = _get_spotify_album_tracks(sp, aid)
            if not sp_tracks:
                continue

            # Check if our track matches the Spotify track at position idx
            position_match = False
            if idx < len(sp_tracks):
                sp_t = _norm(sp_tracks[idx])
                db_t = _norm(track_name)
                if db_t in sp_t or sp_t in db_t:
                    position_match = True
                else:
                    db_w = set(db_t.split())
                    sp_w = set(sp_t.split())
                    if db_w and sp_w:
                        overlap = db_w & sp_w
                        if len(overlap) >= min(len(db_w), len(sp_w)) * 0.6:
                            position_match = True

            if position_match:
                album_votes[aid] = album_votes.get(aid, 0) + 2  # position match = 2 points
            else:
                # Check if track exists anywhere in the album
                for sp_t in sp_tracks:
                    if _norm(track_name) in _norm(sp_t) or _norm(sp_t) in _norm(track_name):
                        album_votes[aid] = album_votes.get(aid, 0) + 1  # loose match = 1 point
                        break

            if aid not in album_info:
                album_info[aid] = dict(album)

    if not album_votes:
        return None

    # Best album by votes (need at least 3 points = 2 position matches or 1 position + 1 loose)
    best_id = max(album_votes, key=album_votes.get)
    best_score = album_votes[best_id]

    if best_score < 3:
        return None

    result = dict(album_info[best_id])
    result["match_method"] = "track_search"
    result["track_score"] = best_score
    return result


# ── strategy 3: title-only (soundtrack/compilation) ─────────────────

def _match_by_title(sp: Any, title: str, db_tracks: list[str]) -> dict[str, Any] | None:
    """Title-only search for soundtracks/compilations. Requires track verification."""
    if not _is_soundtrack(title) and not _is_compilation(title):
        return None

    results = sp.search_tracks_sync(title, limit=2)
    if not results:
        return None

    for r in results:
        album = _resolve_album(sp, r.get("spotify_track_id", ""))
        aid = album.get("album_id")
        if not aid:
            continue

        album_name = album.get("album_name", "")
        if not _norm(title) in _norm(album_name) and not _norm(album_name) in _norm(title):
            continue

        # Must verify with tracks
        if db_tracks:
            sp_tracks = _get_spotify_album_tracks(sp, aid)
            score = _track_sequence_match(db_tracks, sp_tracks, min_match=2)
            if score >= 2:
                result = dict(album)
                result["match_method"] = "title_only"
                result["track_score"] = score
                return result

    return None


# ── main matcher ────────────────────────────────────────────────────


def _get_barcode_for_master(conn: Any, master_id: int) -> str | None:
    """Get the first valid barcode from master's owned items."""
    row = conn.execute(
        """SELECT mid.barcode FROM album_master_member amm
           JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
           WHERE amm.album_master_id = ? AND mid.barcode IS NOT NULL
             AND TRIM(mid.barcode) <> '' AND length(TRIM(mid.barcode)) >= 8
             AND TRIM(mid.barcode) GLOB '[0-9]*'
           LIMIT 1""",
        (master_id,),
    ).fetchone()
    if not row:
        return None
    bc = str(row["barcode"] or "").strip()
    # Clean non-digit chars, keep only digits
    import re
    bc = re.sub(r'[^0-9]', '', bc)
    return bc if len(bc) in (12, 13) else None


def _verify_by_barcode(sp: Any, album_id: str, db_barcode: str) -> bool:
    """Check if Spotify album UPC/EAN matches DB barcode."""
    if not db_barcode:
        return False
    sp_client = sp._ensure_client_cc()
    if sp_client is None:
        return False
    try:
        album = sp_client.album(album_id)
        ext_ids = album.get("external_ids", {}) or {}
        upc = str(ext_ids.get("upc", "") or "").strip()
        ean = str(ext_ids.get("ean", "") or "").strip()
        # Normalize: strip leading zeros and compare
        def norm(s):
            s = ''.join(c for c in s if c.isdigit())
            return s.lstrip('0')
        db_norm = norm(db_barcode)
        return bool(db_norm) and (norm(upc) == db_norm or norm(ean) == db_norm)
    except Exception:
        return False

def _match_by_barcode(sp: Any, barcode: str, db_tracks: list[str]) -> dict[str, Any] | None:
    if not barcode:
        return None
    results = sp.search_albums_sync(f"upc:{barcode}", limit=1)
    if not results:
        return None
    
    r = results[0]
    aid = r.get("spotify_album_id")
    if not aid:
        return None
    
    # Verify track sequence if tracks are available
    if db_tracks:
        sp_tracks = _get_spotify_album_tracks(sp, aid)
        score = _track_sequence_match(db_tracks, sp_tracks, min_match=1)
        if score > 0:
            return {
                "album_id": aid,
                "album_uri": r.get("spotify_album_uri"),
                "album_name": r.get("name"),
                "album_artist": r.get("artist"),
                "release_date": r.get("release_date"),
                "image_url": r.get("image_url"),
                "match_method": "barcode_search",
                "track_score": score,
            }
    else:
        return {
            "album_id": aid,
            "album_uri": r.get("spotify_album_uri"),
            "album_name": r.get("name"),
            "album_artist": r.get("artist"),
            "release_date": r.get("release_date"),
            "image_url": r.get("image_url"),
            "match_method": "barcode_search",
            "track_score": 0,
        }
    return None


def _match_various_artists(sp: Any, title: str, db_tracks: list[str]) -> dict[str, Any] | None:
    if not title:
        return None
    query = f"Various Artists {title}"
    results = sp.search_albums_sync(query, limit=2)
    if not results:
        return None
    
    best = None
    best_score = 0
    for r in results:
        aid = r.get("spotify_album_id")
        if not aid:
            continue
        
        score = 0
        if db_tracks:
            sp_tracks = _get_spotify_album_tracks(sp, aid)
            score = _track_sequence_match(db_tracks, sp_tracks, min_match=2)
        
        if score > best_score:
            best_score = score
            best = {
                "album_id": aid,
                "album_uri": r.get("spotify_album_uri"),
                "album_name": r.get("name"),
                "album_artist": r.get("artist"),
                "release_date": r.get("release_date"),
                "image_url": r.get("image_url"),
                "match_method": "various_artists_search",
                "track_score": score,
            }
            
    if best and best_score >= 2:
        return best
    return None


def match_spotify_for_master(conn: Any, master_id: int, sp: Any) -> dict[str, Any]:
    """Multi-strategy match with track sequence verification."""
    row = conn.execute(
        "SELECT id, title, artist_or_brand, release_year FROM album_master WHERE id = ?",
        (master_id,),
    ).fetchone()

    if not row:
        return {"master_id": master_id, "matched": False, "reason": "not_found"}

    title = str(row["title"] or "").strip()
    artist = str(row["artist_or_brand"] or "").strip()
    release_year = int(row["release_year"]) if row["release_year"] else None

    if not title:
        return {"master_id": master_id, "matched": False, "reason": "no_title"}

    db_tracks = _get_tracks_for_master(conn, master_id)
    db_barcode = _get_barcode_for_master(conn, master_id)

    # Strategy pipeline
    result = None

    # 1. Barcode search (highest confidence)
    if db_barcode:
        result = _match_by_barcode(sp, db_barcode, db_tracks)

    # 2. Various Artists search
    if not result and artist == "Various Artists":
        result = _match_various_artists(sp, title, db_tracks)

    # 3. Album search (with track sequence verification + release year)
    if not result:
        result = _match_by_album(sp, artist, title, db_tracks, release_year=release_year)

    # 4. Sequential track search
    if not result and db_tracks:
        result = _match_by_tracks(sp, artist, db_tracks)

    # 5. Title-only (soundtracks/compilations)
    if not result:
        result = _match_by_title(sp, title, db_tracks)

    if not result or not result.get("album_id"):
        return {
            "master_id": master_id,
            "matched": False,
            "reason": "no_spotify_match",
            "tracks_available": len(db_tracks),
        }

    # Barcode cross-validation
    barcode_match = False
    if result.get("match_method") == "barcode_search":
        barcode_match = True
    elif db_barcode:
        barcode_match = _verify_by_barcode(sp, result["album_id"], db_barcode)

    # Store
    now = utc_now_iso()
    before_row = conn.execute(
        "SELECT spotify_album_id, spotify_album_uri FROM album_master WHERE id = ?",
        (master_id,),
    ).fetchone()
    conn.execute(
        """UPDATE album_master
           SET spotify_album_id = ?, spotify_album_uri = ?, spotify_image_url = ?, spotify_matched_at = ?, updated_at = ?
           WHERE id = ?""",
        (result["album_id"], result["album_uri"],
         result.get("image_url"), now, now, master_id),
    )
    conn.commit()

    try:
        from app.db.audit_log import log_audit_event
        log_audit_event(
            entity_type="album_master",
            entity_id=master_id,
            action="SPOTIFY_MATCH",
            changed_by="batch",
            before={"spotify_album_id": before_row["spotify_album_id"] if before_row else None},
            after={
                "spotify_album_id": result["album_id"],
                "spotify_album_uri": result["album_uri"],
                "match_method": result.get("match_method", "unknown"),
            },
        )
    except Exception:
        logger.debug("audit log failed for master %s", master_id)

    return {
        "master_id": master_id,
        "matched": True,
        "strategy": result.get("match_method", "unknown"),
        "spotify_album_id": result["album_id"],
        "spotify_album_name": result.get("album_name", ""),
        "track_score": result.get("track_score", 0),
        "tracks_available": len(db_tracks),
        "barcode_verified": barcode_match,
        "barcode": db_barcode,
    }


# ── batch ───────────────────────────────────────────────────────────

def batch_match_spotify(
    sp: Any,
    limit: int = 50,
    only_unmatched: bool = True,
    domain_code: str | None = None,
    sleep_per_item: float = 2.0,
) -> dict[str, int]:
    """Batch match album_masters to Spotify."""
    matched = 0
    skipped = 0
    errors = 0

    with get_conn() as conn:
        domain_clause = " AND domain_code = ?" if domain_code else ""
        domain_params = [domain_code] if domain_code else []
        track_clause = """AND EXISTS (
                       SELECT 1 FROM album_master_member amm
                       JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
                       WHERE amm.album_master_id = album_master.id
                         AND mid.track_list_json IS NOT NULL AND mid.track_list_json <> '[]'
                   )"""
        if only_unmatched:
            rows = conn.execute(
                f"""SELECT id FROM album_master
                   WHERE (spotify_album_id IS NULL OR TRIM(spotify_album_id) = '')
                     AND title IS NOT NULL AND TRIM(title) <> ''
                     {domain_clause}
                     {track_clause}
                   ORDER BY updated_at ASC
                   LIMIT ?""",
                (*domain_params, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT id FROM album_master
                   WHERE title IS NOT NULL AND TRIM(title) <> ''
                     {domain_clause}
                     {track_clause}
                   ORDER BY updated_at ASC LIMIT ?""",
                (*domain_params, limit),
            ).fetchall()

        for row in rows:
            try:
                result = match_spotify_for_master(conn, row["id"], sp)
                if result["matched"]:
                    matched += 1
                else:
                    skipped += 1
                time.sleep(sleep_per_item)
            except Exception:
                logger.exception("Spotify match failed for master %s", row["id"])
                errors += 1

    return {"matched": matched, "skipped": skipped, "errors": errors}
