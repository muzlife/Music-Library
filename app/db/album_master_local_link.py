"""album_master ↔ NAS 로컬 디렉토리 매칭 테이블 관리."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from app.db import get_conn, utc_now_iso
from app.db.local_music_index import AUDIO_EXTS, MUSIC_ROOT

# [YYYY-MM-DD] or [YYYY] Artist - Title  (Year Label optional)
_DIR_RE = re.compile(
    r"^\[(\d{4})(?:-\d{2}-\d{2})?\]\s+(.+?)\s+-\s+(.+?)(?:\s+\([^)]+\))*\s*$"
)


_TRACK_NUM_RE = re.compile(r"^\d{1,3}[\.\-\s]+")


def _norm(text: str) -> str:
    """NFC-normalise, lowercase, strip diacritics, drop punctuation."""
    text = unicodedata.normalize("NFC", text)          # NFD→NFC (macOS filenames)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().lower()


def _norm_track(title: str) -> str:
    """Strip leading track numbers then normalise: '01. 여의도 우린' → '여의도 우린'."""
    title = _TRACK_NUM_RE.sub("", title.strip())
    return _norm(title)


def _token_sim(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _track_jaccard(local_titles: set[str], master_titles: set[str]) -> float:
    if not local_titles or not master_titles:
        return 0.0
    nl = {_norm_track(t) for t in local_titles if t.strip()}
    nm = {_norm_track(t) for t in master_titles if t.strip()}
    nl.discard("")
    nm.discard("")
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


_DISC_SUB_RE = re.compile(r"^(?:CD|Disc|Disk|disc|disk)\s*(\d+)$", re.I)


def _disc_sort_key(file_path: str, prefix: str) -> tuple[int, int, str]:
    """Sort key: (disc_num, track_num, path). Top-level files get disc 0."""
    relative = file_path[len(prefix):]
    parts = relative.split("/")
    if len(parts) > 1:
        m = _DISC_SUB_RE.match(parts[0])
        disc = int(m.group(1)) if m else 999
    else:
        disc = 0
    return (disc, 0, file_path)  # track_number applied after fetch


def list_tracks_in_dir(dir_path: str) -> list[dict[str, Any]]:
    prefix = dir_path.rstrip("/") + "/"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT file_path, title, track_number, duration_seconds
            FROM local_music_index
            WHERE file_path LIKE ?
            """,
            (prefix + "%",),
        ).fetchall()
    if not rows:
        return []

    def sort_key(r: Any) -> tuple[int, int, str]:
        disc, _, path = _disc_sort_key(r["file_path"], prefix)
        tn = r["track_number"]
        try:
            track = int(tn) if tn and int(tn) > 0 else 9999
        except (TypeError, ValueError):
            track = 9999
        return (disc, track, path)

    return [dict(r) for r in sorted(rows, key=sort_key)]


_COVER_PRIORITY = {"cover.jpg", "cover.png", "folder.jpg", "folder.png",
                   "front.jpg", "front.png", "artwork.jpg", "albumart.jpg"}
_IMG_EXTS = {".jpg", ".jpeg", ".png"}


def _scan_dir_for_cover(directory: Path) -> str | None:
    """Case-insensitive cover search: priority names first, then any image."""
    try:
        entries = {f.name.lower(): f for f in directory.iterdir() if f.is_file()}
    except OSError:
        return None
    # 1) 우선 이름 목록에서 케이스 무관 검색
    for name in _COVER_PRIORITY:
        if name in entries:
            return str(entries[name])
    # 2) 이외 이미지 파일 — 이름 정렬 후 첫 번째
    for name, path in sorted(entries.items()):
        if Path(name).suffix in _IMG_EXTS:
            return str(path)
    return None


def find_cover_path(dir_path: str) -> str | None:
    root = Path(dir_path)
    # 1) 루트 디렉토리
    found = _scan_dir_for_cover(root)
    if found:
        return found
    # 2) 하위 디렉토리(디스크별) 탐색
    try:
        for sub in sorted(root.iterdir()):
            if sub.is_dir():
                found = _scan_dir_for_cover(sub)
                if found:
                    return found
    except OSError:
        pass
    return None


# ── Auto-matcher ─────────────────────────────────────────────────────────────

_CD_SUB_RE = re.compile(r"^(CD|Disc|Disk)\s*\d+$", re.I)


def _effective_dir(file_path: str) -> str:
    """Return the album-level directory, skipping CD/Disc subdirs."""
    parent = Path(file_path).parent
    if _CD_SUB_RE.match(parent.name):
        return str(parent.parent)
    return str(parent)


def _build_local_dir_index(track_rows: list) -> dict[str, dict[str, Any]]:
    """Group local_music_index rows by album dir → {dir_path: {tracks, parsed}}."""
    dirs: dict[str, dict[str, Any]] = {}
    for row in track_rows:
        dir_path = _effective_dir(row["file_path"])
        if dir_path not in dirs:
            parsed = parse_dir_name(Path(dir_path).name)
            dirs[dir_path] = {"tracks": set(), "parsed": parsed}
        if row["title"]:
            dirs[dir_path]["tracks"].add(_norm_track(row["title"]))
    return dirs


def auto_match(dry_run: bool = False,
               track_min_ratio: float = 0.50,
               name_min_score: float = 0.72) -> dict[str, int]:
    """Two-pass KOREA-only matching.

    Pass 1 (track-centric): build local track→dir reverse index, then for each
    KOREA master with tracks, score dirs by matching-track ratio. Threshold: 50%.

    Pass 2 (name-centric): for remaining unmatched dirs with parseable names,
    do year-bucketed artist+title token similarity. Threshold: 0.72.
    """
    import json as _json
    from collections import defaultdict

    with get_conn() as conn:
        track_rows = conn.execute(
            "SELECT file_path, title FROM local_music_index WHERE title != ''"
        ).fetchall()

        master_rows = conn.execute(
            """
            SELECT am.id, am.title, am.artist_or_brand, am.release_year,
                   mid.track_list_json
            FROM album_master am
            LEFT JOIN (
              SELECT amm2.album_master_id, mid2.track_list_json
              FROM album_master_member amm2
              JOIN owned_item oi2 ON oi2.id = amm2.owned_item_id
              JOIN music_item_detail mid2 ON mid2.owned_item_id = oi2.id
              WHERE mid2.track_list_json IS NOT NULL AND mid2.track_list_json != '[]'
              GROUP BY amm2.album_master_id
            ) mid ON mid.album_master_id = am.id
            WHERE COALESCE(am.override_domain_code, am.domain_code) = 'KOREA'
              AND am.title IS NOT NULL
            """
        ).fetchall()

        linked_dirs: set[str] = {
            r[0] for r in conn.execute("SELECT local_dir_path FROM album_master_local_link").fetchall()
        }
        linked_masters: set[int] = {
            r[0] for r in conn.execute("SELECT album_master_id FROM album_master_local_link").fetchall()
        }

    # ── Build local dir index ────────────────────────────────────────────────
    local_dirs = _build_local_dir_index(track_rows)  # dir_path → {tracks, parsed}

    # ── Build local track → dir reverse index ───────────────────────────────
    # norm_track → [dir_path, ...]
    track_to_dirs: dict[str, list[str]] = defaultdict(list)
    for dir_path, info in local_dirs.items():
        if dir_path in linked_dirs:
            continue
        for t in info["tracks"]:  # already _norm_track'd in _build_local_dir_index
            if t:
                track_to_dirs[t].append(dir_path)

    # ── Parse master data ────────────────────────────────────────────────────
    masters_with_tracks: list[dict] = []
    masters_no_tracks: list[dict] = []
    for r in master_rows:
        if r["id"] in linked_masters:
            continue
        yr = r["release_year"]
        track_list: list[str] = []
        if r["track_list_json"]:
            try:
                track_list = _json.loads(r["track_list_json"])
            except Exception:
                pass
        m = {
            "id": r["id"],
            "title": r["title"] or "",
            "artist": r["artist_or_brand"] or "",
            "year": int(yr) if yr else None,
            "tracks": track_list,
        }
        if track_list:
            masters_with_tracks.append(m)
        else:
            masters_no_tracks.append(m)

    matched = 0
    new_links: list[tuple] = []
    now = utc_now_iso()

    # ══ Pass 1: track-centric ════════════════════════════════════════════════
    for m in masters_with_tracks:
        if m["id"] in linked_masters:
            continue

        # count how many master tracks each candidate dir matches
        dir_hits: dict[str, int] = defaultdict(int)
        norm_master_tracks = [_norm_track(t) for t in m["tracks"] if _norm_track(t)]
        for nt in norm_master_tracks:
            for dp in track_to_dirs.get(nt, []):
                if dp not in linked_dirs:
                    dir_hits[dp] += 1

        if not dir_hits:
            continue

        best_dir = max(dir_hits, key=lambda d: dir_hits[d])
        hit_ratio = dir_hits[best_dir] / len(norm_master_tracks)

        # Require at least track_min_ratio AND ≥3 tracks matched (avoid accidental short-list matches)
        min_hits = max(2, round(len(norm_master_tracks) * track_min_ratio))
        if dir_hits[best_dir] < min_hits:
            continue

        # Sanity checks using dir-name metadata
        parsed = local_dirs[best_dir]["parsed"]
        if parsed:
            # Year must be within ±2 years
            if m["year"] and abs(parsed["year"] - m["year"]) > 2:
                continue
            a_sim = _token_sim(parsed["artist"], m["artist"])
            t_sim = _token_sim(parsed["title"], m["title"])
            name_score = a_sim * 0.45 + t_sim * 0.55
            # Reject if name is strongly contradictory
            if name_score < 0.20 and a_sim < 0.15:
                continue

        matched += 1
        linked_masters.add(m["id"])
        linked_dirs.add(best_dir)
        if not dry_run:
            new_links.append((m["id"], best_dir, now))

    # ══ Pass 2: name-centric for masters without tracks ══════════════════════
    by_year: dict[int, list[dict]] = defaultdict(list)
    no_year_masters: list[dict] = []
    for m in masters_no_tracks:
        if m["id"] in linked_masters:
            continue
        if m["year"]:
            by_year[m["year"]].append(m)
        else:
            no_year_masters.append(m)

    for dir_path, info in local_dirs.items():
        if dir_path in linked_dirs:
            continue
        parsed = info["parsed"]
        if not parsed:
            continue

        year, dir_artist, dir_title = parsed["year"], parsed["artist"], parsed["title"]
        candidates = (
            by_year.get(year, [])
            + by_year.get(year - 1, [])
            + by_year.get(year + 1, [])
            + no_year_masters  # 연도 없는 마스터는 모든 디렉토리와 비교
        )

        best_id, best_score = None, 0.0
        for c in candidates:
            if c["id"] in linked_masters:
                continue
            score = _token_sim(dir_artist, c["artist"]) * 0.45 + \
                    _token_sim(dir_title, c["title"]) * 0.55
            if score > best_score:
                best_score, best_id = score, c["id"]

        if best_id and best_score >= name_min_score:
            matched += 1
            linked_masters.add(best_id)
            linked_dirs.add(dir_path)
            if not dry_run:
                new_links.append((best_id, dir_path, now))

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

    return {"matched": matched, "skipped": len(local_dirs) - matched, "total_dirs": len(local_dirs)}


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
