"""Backfill worker functions and globals extracted from main.py."""
from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import HTTPException

from .. import db
from ..services.metadata_sync import _get_db_conn, _now_iso
from ..services.providers import get_source_release_snapshot

logger = logging.getLogger(__name__)

# ── Aladin-Discogs 백필 ──
ALADIN_DISCOGS_BACKFILL_LOCK = threading.Lock()
ALADIN_DISCOGS_BACKFILL_THREAD: threading.Thread | None = None
ALADIN_DISCOGS_BACKFILL_LAST_RESULT: dict[str, Any] | None = None
ALADIN_DISCOGS_BACKFILL_LAST_ERROR: str | None = None

# ── Spotify 배치 매칭 ──
SPOTIFY_BATCH_LOCK = threading.Lock()
SPOTIFY_BATCH_THREAD: threading.Thread | None = None
SPOTIFY_BATCH_LAST_RESULT: dict[str, Any] | None = None
SPOTIFY_BATCH_LAST_ERROR: str | None = None

# ── Discogs 한국 아티스트 한글명 백필 ──
DISCOGS_KOREAN_BACKFILL_LOCK = threading.Lock()
DISCOGS_KOREAN_BACKFILL_THREAD: threading.Thread | None = None
DISCOGS_KOREAN_BACKFILL_RESULT: dict[str, Any] | None = None

# ── ManiaDB release_type 백필 ──
MANIADB_RELEASE_TYPE_BACKFILL_LOCK = threading.Lock()
MANIADB_RELEASE_TYPE_BACKFILL_RESULT: dict[str, Any] | None = None


def _run_aladin_discogs_backfill(*, dry_run: bool = False, sleep_sec: float = 2.0) -> dict[str, Any]:
    """ALADIN owned_item 전체를 대상으로 Discogs 마스터 매칭 + 포맷 정보 업데이트."""
    global ALADIN_DISCOGS_BACKFILL_LAST_RESULT, ALADIN_DISCOGS_BACKFILL_LAST_ERROR

    acquired = ALADIN_DISCOGS_BACKFILL_LOCK.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=409, detail="aladin discogs backfill already running")

    started_at = _now_iso()
    stats: dict[str, Any] = {
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "scanned": 0,
        "no_crossref": 0,
        "master_created": 0,
        "master_linked": 0,
        "already_discogs": 0,
        "detail_updated": 0,
        "error": 0,
        "matched_items": [],
    }

    try:
        import time as _time
        import app.main as _m

        with db.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT oi.id, oi.source_external_id, oi.linked_album_master_id,
                       am.source_code AS master_source_code,
                       am.source_master_id AS master_source_id
                FROM owned_item oi
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                WHERE oi.source_code = 'ALADIN'
                ORDER BY oi.id
                """
            ).fetchall()

        items = [dict(r) for r in rows]
        stats["scanned"] = 0  # will count per loop

        for row in items:
            owned_item_id = int(row["id"])
            source_ext = str(row["source_external_id"] or "").strip()
            current_master_id = row["linked_album_master_id"]
            current_master_source = str(row.get("master_source_code") or "").strip().upper()
            stats["scanned"] += 1

            try:
                snap = get_source_release_snapshot(source="ALADIN", external_id=source_ext)
                crossref: dict[str, Any] | None = (snap or {}).get("discogs_crossref")
                _time.sleep(sleep_sec)

                if not crossref:
                    stats["no_crossref"] += 1
                    continue

                d_ext = str(crossref.get("external_id") or "").strip()
                d_master_id = str(crossref.get("master_id") or "").strip()
                d_src_id = d_master_id or d_ext
                d_title = str(crossref.get("title") or "").strip() or f"ALADIN#{source_ext}"
                d_artist = str(crossref.get("artist_or_brand") or "").strip() or None
                d_year = crossref.get("master_release_year") or crossref.get("release_year")
                d_raw = crossref.get("raw") or {}
                d_domain = _m._infer_album_master_domain_code(
                    source_code="DISCOGS", title=d_title, artist_or_brand=d_artist, raw=d_raw
                )

                matched_entry: dict[str, Any] = {
                    "owned_item_id": owned_item_id,
                    "aladin_id": source_ext,
                    "discogs_release_id": d_ext,
                    "discogs_master_id": d_src_id,
                    "artist": d_artist,
                    "title": d_title,
                    "format": crossref.get("format_name"),
                    "barcode": crossref.get("barcode"),
                    "label": crossref.get("label_name"),
                    "album_master_id": None,
                    "action": None,
                }

                if current_master_source == "DISCOGS":
                    stats["already_discogs"] += 1
                    album_master_id = int(current_master_id)
                    matched_entry["album_master_id"] = album_master_id
                    matched_entry["action"] = "detail_only"
                else:
                    if not dry_run:
                        album_master_id = db.upsert_album_master(
                            source_code="DISCOGS",
                            source_master_id=d_src_id,
                            title=d_title,
                            artist_or_brand=d_artist,
                            domain_code=d_domain,
                            release_year=d_year,
                            raw=d_raw,
                        )
                        db.bind_album_master_members(
                            album_master_id=album_master_id,
                            owned_item_ids=[owned_item_id],
                            replace_existing=False,
                        )
                        db.set_owned_item_linked_album_master(
                            owned_item_id=owned_item_id, album_master_id=album_master_id
                        )
                    else:
                        album_master_id = -1
                    stats["master_created"] += 1
                    matched_entry["album_master_id"] = album_master_id
                    matched_entry["action"] = "dry_run" if dry_run else "created"

                music_detail_raw = {
                    "format_name": crossref.get("format_name"),
                    "artist_or_brand": d_artist,
                    "release_year": d_year,
                    "released_date": crossref.get("released_date"),
                    "barcode": crossref.get("barcode"),
                    "label_name": crossref.get("label_name"),
                    "catalog_no": crossref.get("catalog_no"),
                    "cover_image_url": crossref.get("cover_image_url"),
                    "track_list": crossref.get("track_list") or [],
                    "media_type": crossref.get("media_type") or crossref.get("format_name"),
                    "genres": crossref.get("genres") or [],
                    "styles": crossref.get("styles") or [],
                    "disc_count": crossref.get("disc_count"),
                    "speed_rpm": crossref.get("speed_rpm"),
                    "has_obi": crossref.get("has_obi"),
                    "runout_matrix": crossref.get("runout_matrix") or [],
                    "pressing_country": crossref.get("pressing_country"),
                    "source_notes": crossref.get("source_notes"),
                    "credits": crossref.get("credits") or [],
                    "identifier_items": crossref.get("identifier_items") or [],
                    "image_items": crossref.get("image_items") or [],
                    "company_items": crossref.get("company_items") or [],
                    "series": crossref.get("series") or [],
                    "format_items": crossref.get("format_items") or [],
                    "track_items": crossref.get("track_items") or [],
                    "label_items": crossref.get("label_items") or [],
                }
                music_detail_clean = {k: v for k, v in music_detail_raw.items() if v is not None}

                if not dry_run:
                    with _get_db_conn() as conn:
                        db._upsert_music_item_detail_in_conn(conn, owned_item_id, music_detail_clean)
                stats["detail_updated"] += 1
                stats["matched_items"].append(matched_entry)

            except Exception as exc:
                stats["error"] += 1
                logger.exception("aladin_discogs_backfill item %s error: %s", owned_item_id, exc)

        stats["finished_at"] = _now_iso()
        ALADIN_DISCOGS_BACKFILL_LAST_RESULT = stats
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = None
        return stats

    except HTTPException:
        raise
    except Exception as exc:
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = f"{_now_iso()} | {exc}"
        logger.exception("aladin_discogs_backfill failed: %s", exc)
        raise
    finally:
        ALADIN_DISCOGS_BACKFILL_LOCK.release()


def _aladin_discogs_backfill_thread_worker(dry_run: bool, sleep_sec: float) -> None:
    global ALADIN_DISCOGS_BACKFILL_LAST_ERROR
    from app.services.perf_tracker import perf_track
    try:
        with perf_track("aladin_discogs_backfill", context={"dry_run": dry_run}):
            _run_aladin_discogs_backfill(dry_run=dry_run, sleep_sec=sleep_sec)
    except HTTPException:
        pass
    except Exception as exc:
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = f"{_now_iso()} | {exc}"
        logger.exception("aladin_discogs_backfill thread error: %s", exc)


def _spotify_batch_thread_worker(limit: int, require_tracks: bool) -> None:
    global SPOTIFY_BATCH_LAST_RESULT, SPOTIFY_BATCH_LAST_ERROR
    from app.services.spotify import SpotifyService
    from app.db.album_master_spotify import batch_match_spotify
    from app.services.perf_tracker import perf_track
    try:
        with SPOTIFY_BATCH_LOCK:
            sp = SpotifyService()
            with perf_track("spotify_batch_match", context={"limit": limit}):
                result = batch_match_spotify(sp, limit=limit, require_tracks=require_tracks)
            SPOTIFY_BATCH_LAST_RESULT = result
            SPOTIFY_BATCH_LAST_ERROR = None
    except Exception as exc:
        SPOTIFY_BATCH_LAST_ERROR = f"{_now_iso()} | {exc}"
        SPOTIFY_BATCH_LAST_RESULT = None
        logger.exception("spotify_batch thread error: %s", exc)


def _discogs_korean_backfill_worker(limit: int | None) -> None:
    global DISCOGS_KOREAN_BACKFILL_RESULT
    from app.services.perf_tracker import perf_track
    import app.main as _m
    try:
        with DISCOGS_KOREAN_BACKFILL_LOCK:
            with perf_track("discogs_korean_backfill", context={"limit": limit}):
                result = _m.backfill_discogs_korean_artist_names(limit=limit)
            DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "done", **result}
    except Exception as exc:
        DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "error", "detail": str(exc)}
        logger.exception("discogs_korean_backfill error: %s", exc)


def _run_maniadb_release_type_backfill(limit: int = 200, sleep_sec: float = 0.3) -> dict[str, Any]:
    """ManiaDB album_master 중 release_type 미반영건을 재요청해 채운다."""
    import time as _time
    from app.services.providers import get_maniadb_master_variants

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source_master_id
            FROM album_master
            WHERE source_code = 'MANIADB'
              AND release_type IS NULL
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    candidates = [dict(r) for r in rows]

    updated = 0
    skipped = 0
    failed = 0
    now = _now_iso()

    for row in candidates:
        master_id = int(row["id"])
        raw_sid = str(row["source_master_id"] or "").strip()
        album_id = raw_sid.split(":")[0].strip()
        if not album_id:
            skipped += 1
            continue
        try:
            variants = get_maniadb_master_variants(album_id, limit=1)
            release_type = None
            if variants:
                release_type = str(variants[0].get("release_type") or "").strip().upper() or None
            if release_type not in ("ALBUM", "EP", "SINGLE"):
                release_type = None
            if release_type:
                with db.get_conn() as wconn:
                    wconn.execute(
                        "UPDATE album_master SET release_type = ?, updated_at = ? WHERE id = ?",
                        (release_type, now, master_id),
                    )
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("maniadb_release_type_backfill error id=%s: %s", master_id, exc)
            failed += 1
        if sleep_sec > 0:
            _time.sleep(sleep_sec)

    remaining = 0
    with db.get_conn() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM album_master WHERE source_code='MANIADB' AND release_type IS NULL"
        ).fetchone()[0]

    return {
        "processed": len(candidates),
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "remaining": remaining,
    }


def _maniadb_release_type_backfill_worker(limit: int, sleep_sec: float) -> None:
    global MANIADB_RELEASE_TYPE_BACKFILL_RESULT
    try:
        with MANIADB_RELEASE_TYPE_BACKFILL_LOCK:
            result = _run_maniadb_release_type_backfill(limit=limit, sleep_sec=sleep_sec)
            MANIADB_RELEASE_TYPE_BACKFILL_RESULT = {"status": "done", **result}
    except Exception as exc:
        MANIADB_RELEASE_TYPE_BACKFILL_RESULT = {"status": "error", "detail": str(exc)}
        logger.exception("maniadb_release_type_backfill error: %s", exc)
