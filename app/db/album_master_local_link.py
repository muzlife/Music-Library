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

def auto_match(dry_run: bool = False, min_score: float = 0.72) -> dict[str, int]:
    """Parse NAS album dirs, fuzzy-match to album_master, store links."""
    with get_conn() as conn:
        # distinct album directories from local index
        dir_rows = conn.execute(
            "SELECT DISTINCT file_path FROM local_music_index"
        ).fetchall()

    dirs: dict[str, dict[str, Any]] = {}
    for row in dir_rows:
        parent = str(Path(row["file_path"]).parent)
        if parent not in dirs:
            parsed = parse_dir_name(Path(parent).name)
            if parsed:
                dirs[parent] = parsed

    matched = skipped = 0

    with get_conn() as conn:
        for dir_path, parsed in dirs.items():
            # skip already linked (manual or auto)
            existing = conn.execute(
                "SELECT 1 FROM album_master_local_link WHERE local_dir_path = ? LIMIT 1",
                (dir_path,),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            year = parsed["year"]
            artist = parsed["artist"]
            title = parsed["title"]

            # candidates: same year ±1 to allow reissue offsets
            candidates = conn.execute(
                """
                SELECT id, title, artist_or_brand
                FROM album_master
                WHERE release_year BETWEEN ? AND ?
                  AND title IS NOT NULL
                """,
                (year - 1, year + 1),
            ).fetchall()

            best_id, best_score = None, 0.0
            for c in candidates:
                a_sim = _token_sim(artist, c["artist_or_brand"] or "")
                t_sim = _token_sim(title, c["title"] or "")
                score = a_sim * 0.45 + t_sim * 0.55
                if score > best_score:
                    best_score, best_id = score, c["id"]

            if best_id and best_score >= min_score:
                if not dry_run:
                    now = utc_now_iso()
                    conn.execute(
                        """
                        INSERT INTO album_master_local_link
                          (album_master_id, local_dir_path, match_confidence, linked_at)
                        VALUES (?, ?, 'AUTO', ?)
                        ON CONFLICT(album_master_id) DO NOTHING
                        """,
                        (best_id, dir_path, now),
                    )
                matched += 1
            else:
                skipped += 1

    return {"matched": matched, "skipped": skipped, "total_dirs": len(dirs)}


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
