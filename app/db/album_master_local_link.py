"""album_master ↔ NAS 로컬 디렉토리 매칭 테이블 관리."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from app.db import get_conn, utc_now_iso
from app.db.local_music_index import AUDIO_EXTS, MUSIC_ROOT

# [YYYY-MM-DD] Artist - Title  or  [YYYY-MM-DD] Artist - Title (Year Label)
_DIR_RE = re.compile(
    r"^\[(\d{4})-\d{2}-\d{2}\]\s+(.+?)\s+-\s+(.+?)(?:\s+\([^)]+\))*\s*$"
)


def _norm(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, drop punctuation."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().lower()


def _token_sim(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _track_jaccard(local_titles: set[str], master_titles: set[str]) -> float:
    if not local_titles or not master_titles:
        return 0.0
    nl = {_norm(t) for t in local_titles if t.strip()}
    nm = {_norm(t) for t in master_titles if t.strip()}
    if not nl or not nm:
        return 0.0
    return len(nl & nm) / len(nl | nm)


def parse_dir_name(dirname: str) -> dict[str, Any] | None:
    m = _DIR_RE.match(dirname.strip())
    if not m:
        return None
    return {"year": int(m.group(1)), "artist": m.group(2).strip(), "title": m.group(3).strip()}


# ── CRUD ────────────────────────────────────────────────────────────────────

def get_local_link(master_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM album_master_local_link WHERE album_master_id = ? LIMIT 1",
            (master_id,),
        ).fetchone()
    return dict(row) if row else None


def set_local_link(master_id: int, dir_path: str, confidence: str = "MANUAL") -> None:
    now = utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO album_master_local_link
              (album_master_id, local_dir_path, match_confidence, linked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(album_master_id) DO UPDATE SET
              local_dir_path   = excluded.local_dir_path,
              match_confidence = excluded.match_confidence,
              linked_at        = excluded.linked_at
            """,
            (master_id, str(dir_path), confidence, now),
        )


def delete_local_link(master_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM album_master_local_link WHERE album_master_id = ?",
            (master_id,),
        )


def list_tracks_for_link(master_id: int) -> list[dict[str, Any]]:
    link = get_local_link(master_id)
    if not link:
        return []
    return list_tracks_in_dir(link["local_dir_path"])


def list_tracks_in_dir(dir_path: str) -> list[dict[str, Any]]:
    prefix = dir_path.rstrip("/") + "/"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT file_path, title, track_number, duration_seconds
            FROM local_music_index
            WHERE file_path LIKE ?
            ORDER BY
              CASE WHEN CAST(track_number AS INTEGER) > 0 THEN 0 ELSE 1 END,
              CAST(track_number AS INTEGER),
              file_path
            """,
            (prefix + "%",),
        ).fetchall()
    # exclude files in subdirectories
    return [
        dict(r) for r in rows
        if "/" not in r["file_path"][len(prefix):]
    ]


def find_cover_path(dir_path: str) -> str | None:
    for name in ("cover.jpg", "cover.png", "folder.jpg", "folder.png",
                 "front.jpg", "front.png", "artwork.jpg"):
        p = Path(dir_path) / name
        if p.is_file():
            return str(p)
    return None


# ── Auto-matcher ─────────────────────────────────────────────────────────────

def _build_local_dir_index(track_rows: list) -> dict[str, dict[str, Any]]:
    """Group local_music_index rows by parent dir → {dir_path: {tracks, parsed}}."""
    dirs: dict[str, dict[str, Any]] = {}
    for row in track_rows:
        parent = str(Path(row["file_path"]).parent)
        if parent not in dirs:
            parsed = parse_dir_name(Path(parent).name)
            dirs[parent] = {"tracks": set(), "parsed": parsed}
        if row["title"]:
            dirs[parent]["tracks"].add(row["title"])
    return dirs


def auto_match(dry_run: bool = False, min_score: float = 0.62) -> dict[str, int]:
    """Match NAS album dirs to KOREA album_masters using dir-name + track-title signals."""
    import json as _json
    from collections import defaultdict

    with get_conn() as conn:
        # 1. Load all local tracks (title + path) for building dir index
        track_rows = conn.execute(
            "SELECT file_path, title FROM local_music_index"
        ).fetchall()

        # 2. KOREA masters only (unmatched) + their track lists
        master_rows = conn.execute(
            """
            SELECT am.id, am.title, am.artist_or_brand, am.release_year,
                   mid.track_list_json
            FROM album_master am
            LEFT JOIN (
              SELECT amm.album_master_id,
                     mid2.track_list_json
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              JOIN music_item_detail mid2 ON mid2.owned_item_id = oi.id
              WHERE mid2.track_list_json IS NOT NULL AND mid2.track_list_json != '[]'
              GROUP BY amm.album_master_id
            ) mid ON mid.album_master_id = am.id
            WHERE COALESCE(am.override_domain_code, am.domain_code) = 'KOREA'
              AND am.title IS NOT NULL
            """
        ).fetchall()

        linked_dirs = {
            r[0] for r in conn.execute("SELECT local_dir_path FROM album_master_local_link").fetchall()
        }
        linked_masters = {
            r[0] for r in conn.execute("SELECT album_master_id FROM album_master_local_link").fetchall()
        }

    # Build local dir index: dir_path → {tracks: set, parsed: dict|None}
    local_dirs = _build_local_dir_index(track_rows)

    # Build master year index + track sets
    by_year: dict[int, list[dict]] = defaultdict(list)
    for r in master_rows:
        if r["id"] in linked_masters:
            continue
        yr = r["release_year"]
        if not yr:
            continue
        track_list = []
        if r["track_list_json"]:
            try:
                track_list = _json.loads(r["track_list_json"])
            except Exception:
                pass
        by_year[int(yr)].append({
            "id": r["id"],
            "title": r["title"] or "",
            "artist": r["artist_or_brand"] or "",
            "tracks": set(track_list),
        })

    matched = skipped = 0
    new_links: list[tuple] = []
    now = utc_now_iso()

    for dir_path, info in local_dirs.items():
        if dir_path in linked_dirs:
            continue

        parsed = info["parsed"]
        local_tracks = info["tracks"]

        if not parsed:
            skipped += 1
            continue

        year = parsed["year"]
        dir_artist = parsed["artist"]
        dir_title = parsed["title"]

        candidates = (
            by_year.get(year, [])
            + by_year.get(year - 1, [])
            + by_year.get(year + 1, [])
        )

        best_id, best_score = None, 0.0
        for c in candidates:
            if c["id"] in linked_masters:
                continue

            a_sim = _token_sim(dir_artist, c["artist"])
            t_sim = _token_sim(dir_title, c["title"])

            # Track overlap: strong discriminator when both sides have tracks
            tr_sim = _track_jaccard(local_tracks, c["tracks"])

            if c["tracks"] and local_tracks:
                # Both have tracks → weighted with track overlap
                score = a_sim * 0.30 + t_sim * 0.40 + tr_sim * 0.30
            else:
                # One or both sides missing tracks → dir-name only
                score = a_sim * 0.45 + t_sim * 0.55

            if score > best_score:
                best_score, best_id = score, c["id"]

        if best_id and best_score >= min_score:
            matched += 1
            linked_masters.add(best_id)
            if not dry_run:
                new_links.append((best_id, dir_path, now))
        else:
            skipped += 1

    if not dry_run and new_links:
        with get_conn() as conn:
            conn.executemany(
                """
                INSERT INTO album_master_local_link
                  (album_master_id, local_dir_path, match_confidence, linked_at)
                VALUES (?, ?, 'AUTO', ?)
                ON CONFLICT(album_master_id) DO NOTHING
                """,
                new_links,
            )

    return {"matched": matched, "skipped": skipped, "total_dirs": len(local_dirs)}


__all__ = [
    "parse_dir_name",
    "get_local_link",
    "set_local_link",
    "delete_local_link",
    "list_tracks_for_link",
    "list_tracks_in_dir",
    "find_cover_path",
    "auto_match",
    "MUSIC_ROOT",
]
