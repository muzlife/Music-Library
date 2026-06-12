"""Album master core writes — upsert / normalize / promote / merge.

Nineteenth slice extracted from the legacy `app/db.py`. Owns the
heart of the album-master domain — the four public writers plus
the cross-cutting helpers they share:

  * `upsert_album_master` — INSERT…ON CONFLICT for the canonical
    `(source_code, source_master_id)` key. Also calls
    `ensure_album_master_external_ref` to keep the cross-source
    lookup table in sync.
  * `normalize_album_master_source_id` — operator/sync correction
    for an album_master row's `source_master_id`. Handles the
    "another row already has the new id" collision by merging
    members + owned_item links into the survivor and DELETEing the
    duplicate.
  * `promote_album_master_source` — switches a master from one
    source provider to another (e.g. a MANIADB-backed master upgraded
    to DISCOGS), with the same collision-merge handling as normalise.
  * `merge_album_masters` — the operator-driven merge button. Moves
    members + owned_item links + external_refs from `source` to
    `target`, deletes the source, and writes a full audit row to
    `album_master_merge_history` (read by the rollback path in
    `app.db.album_master_merge_history`).

  * `_sync_album_master_domain_code_in_conn` — keeps a master's
    `domain_code` consistent with its members'. Shared with the
    `album_master_member.bind_album_master_members` writer and the
    owned-item update path that stays in `__init__.py`.
  * `_snapshot_album_master_record`, `_snapshot_member_link_records`,
    `_snapshot_external_ref_records` — JSON-serialisable shape
    builders used by `merge_album_masters` to snapshot the source
    side before it's deleted, so the merge_history rollback path
    has enough state to undo the merge.

Cross-package dependencies kept on the package surface
  * `_normalize_domain_code_value` — used 25+ times across the
    package, stays in `app/db/__init__.py`.
  * `ensure_album_master_external_ref` — lives in
    `app/db/album_master_external_ref.py`. Pulled here via the
    package surface; see the bottom of `__init__.py` for the
    re-export ordering invariant (album_master_external_ref MUST be
    re-exported BEFORE album_master_core, and album_master_core
    MUST be re-exported BEFORE album_master_member, because
    album_master_member depends on
    `_sync_album_master_domain_code_in_conn` which lives here).

`app/db/__init__.py` re-exports every public symbol so existing
callers (`app/main.py`, `app/api/album_masters.py`, the test suite)
keep working unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_domain_code_value,
    ensure_album_master_external_ref,
    get_conn,
    get_write_conn,
    utc_now_iso,
)


def get_album_master_basic(album_master_id: int) -> dict[str, Any] | None:
    """Return a minimal dict with id, title, artist_or_brand, release_year,
    cover_image_url for a single album_master row, or None if not found."""
    mid = int(album_master_id or 0)
    if mid <= 0:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id,
                   COALESCE(override_title, title) AS title,
                   COALESCE(override_artist_or_brand, artist_or_brand) AS artist_or_brand,
                   COALESCE(override_release_year, release_year) AS release_year,
                   COALESCE(
                       json_extract(raw_json, '$.cover_image'),
                       json_extract(raw_json, '$.thumb')
                   ) AS cover_image_url,
                   source_code,
                   source_master_id,
                   spotify_album_id,
                   spotify_album_uri,
                   spotify_image_url,
                   CAST(json_extract(raw_json, '$.id') AS TEXT) AS source_release_id,
                   review_text,
                   review_source,
                   review_url,
                   genres_json,
                   styles_json,
                   domain_code,
                   source_domain_code,
                   override_domain_code,
                   source_release_year,
                   override_release_year,
                   override_note,
                   override_title,
                   override_artist_or_brand,
                   sort_artist_name,
                   release_type
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (mid,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    # Parse genres and styles from JSON
    raw_genres = result.pop("genres_json", None)
    result["genres"] = json.loads(raw_genres) if isinstance(raw_genres, str) and raw_genres.strip() else []
    raw_styles = result.pop("styles_json", None)
    result["styles"] = json.loads(raw_styles) if isinstance(raw_styles, str) and raw_styles.strip() else []
    return result


def update_album_master_genres(
    album_master_id: int,
    genres: list[str],
    styles: list[str],
) -> None:
    """Update genres_json and/or styles_json on an album_master row.

    Each list is cleaned (stripped, empty strings dropped).  If both
    cleaned lists are empty the function is a no-op.  Columns are
    updated independently — a non-empty genres list overwrites
    genres_json; a non-empty styles list overwrites styles_json.
    updated_at is refreshed whenever any write happens.
    """
    clean_genres = [g.strip() for g in genres if g and g.strip()]
    clean_styles = [s.strip() for s in styles if s and s.strip()]

    if not clean_genres and not clean_styles:
        return

    sets: list[str] = []
    params: list[Any] = []

    if clean_genres:
        sets.append("genres_json = ?")
        params.append(json.dumps(clean_genres, ensure_ascii=True))

    if clean_styles:
        sets.append("styles_json = ?")
        params.append(json.dumps(clean_styles, ensure_ascii=True))

    sets.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(album_master_id)

    sql = f"UPDATE album_master SET {', '.join(sets)} WHERE id = ?"
    with get_conn() as conn:
        conn.execute(sql, params)


def _sync_album_master_domain_code_in_conn(
    conn: sqlite3.Connection,
    album_master_id: int,
    preferred_domain_code: str | None = None,
) -> str | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None

    master_row = conn.execute(
        "SELECT domain_code FROM album_master WHERE id = ? LIMIT 1",
        (master_id,),
    ).fetchone()
    if master_row is None:
        return None

    current_code = _normalize_domain_code_value(master_row["domain_code"])
    resolved_code = _normalize_domain_code_value(preferred_domain_code)
    # No longer derives domain from oi.domain_code — master domain is authoritative
    if not resolved_code:
        return current_code
    if resolved_code != current_code:
        conn.execute(
            "UPDATE album_master SET domain_code = ?, updated_at = ? WHERE id = ?",
            (resolved_code, utc_now_iso(), master_id),
        )
    return resolved_code


def upsert_album_master(
    source_code: str,
    source_master_id: str,
    title: str,
    artist_or_brand: str | None,
    domain_code: str | None,
    release_year: int | None,
    raw: dict[str, Any],
    release_type: str | None = None,
) -> int:
    now = utc_now_iso()
    normalized_domain_code = _normalize_domain_code_value(domain_code)
    with get_conn() as conn:
        _existing = conn.execute(
            """
            SELECT id, title, artist_or_brand, domain_code, release_year
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_code, source_master_id),
        ).fetchone()
        _is_new = _existing is None
        _before = dict(_existing) if _existing is not None else {}

        _valid_release_types = ("ALBUM", "EP", "SINGLE")
        normalized_release_type = str(release_type or "").strip().upper() or None
        if normalized_release_type not in _valid_release_types:
            normalized_release_type = None
        conn.execute(
            """
            INSERT INTO album_master
              (source_code, source_master_id, title, artist_or_brand, domain_code, release_year, raw_json, release_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_code, source_master_id) DO UPDATE SET
              title = excluded.title,
              artist_or_brand = excluded.artist_or_brand,
              domain_code = COALESCE(excluded.domain_code, album_master.domain_code),
              release_year = excluded.release_year,
              raw_json = excluded.raw_json,
              release_type = COALESCE(excluded.release_type, album_master.release_type),
              updated_at = excluded.updated_at
            """,
            (
                source_code,
                source_master_id,
                title,
                artist_or_brand,
                normalized_domain_code,
                release_year,
                json.dumps(raw, ensure_ascii=True),
                normalized_release_type,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            """,
            (source_code, source_master_id),
        ).fetchone()

    if row is None:
        raise RuntimeError("album_master upsert failed")
    album_master_id = int(row["id"])
    ensure_album_master_external_ref(
        album_master_id=album_master_id,
        source_code=source_code,
        source_master_id=source_master_id,
        title_hint=title,
        artist_or_brand_hint=artist_or_brand,
        release_year=release_year,
        raw=raw,
    )
    try:
        from app.db.audit_log import log_audit_event
        if _is_new:
            log_audit_event(
                entity_type="album_master", entity_id=album_master_id,
                action="CREATE", changed_by=None,
                snapshot={"source_code": source_code, "title": title,
                          "artist_or_brand": artist_or_brand, "domain_code": normalized_domain_code},
            )
        else:
            _FIELDS = ("title", "artist_or_brand", "domain_code", "release_year")
            _after_vals = {"title": title, "artist_or_brand": artist_or_brand,
                           "domain_code": normalized_domain_code, "release_year": release_year}
            _before_vals = {f: _before.get(f) for f in _FIELDS}
            log_audit_event(
                entity_type="album_master", entity_id=album_master_id,
                action="UPDATE", changed_by=None,
                before=_before_vals, after=_after_vals,
            )
    except Exception:
        pass
    return album_master_id


def normalize_album_master_source_id(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        return master_id

    now = utc_now_iso()
    with get_conn() as conn:
        current = conn.execute(
            """
            SELECT id, source_code, source_master_id, domain_code, sort_artist_name
            FROM album_master
            WHERE id = ?
            """,
            (master_id,),
        ).fetchone()
        if current is None:
            return 0

        current_source = str(current["source_code"] or "").strip().upper()
        current_source_master = str(current["source_master_id"] or "").strip()
        if current_source != source_u:
            return master_id
        if current_source_master == source_master:
            return master_id

        existing = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()

        if existing is not None:
            target_master_id = int(existing["id"])
            if target_master_id == master_id:
                return master_id

            conn.execute(
                """
                INSERT OR IGNORE INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                SELECT ?, owned_item_id, ?
                FROM album_master_member
                WHERE album_master_id = ?
                """,
                (target_master_id, now, master_id),
            )
            conn.execute(
                """
                UPDATE owned_item
                SET linked_album_master_id = ?, updated_at = ?
                WHERE linked_album_master_id = ?
                """,
                (target_master_id, now, master_id),
            )
            _sync_album_master_domain_code_in_conn(
                conn,
                target_master_id,
                preferred_domain_code=_normalize_domain_code_value(current["domain_code"]),
            )
            current_sort_artist_name = str(current["sort_artist_name"] or "").strip() or None
            if current_sort_artist_name:
                conn.execute(
                    """
                    UPDATE album_master
                    SET sort_artist_name = CASE
                                             WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                             ELSE sort_artist_name
                                           END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (current_sort_artist_name, now, target_master_id),
                )
            conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
            conn.execute(
                "UPDATE album_master SET updated_at = ? WHERE id = ?",
                (now, target_master_id),
            )
            return target_master_id

        conn.execute(
            """
            UPDATE album_master
            SET source_master_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (source_master, now, master_id),
        )
    ensure_album_master_external_ref(
        album_master_id=master_id,
        source_code=source_u,
        source_master_id=source_master,
    )
    return master_id


def promote_album_master_source(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
    title: str,
    artist_or_brand: str | None,
    domain_code: str | None,
    release_year: int | None,
    raw: dict[str, Any],
    release_type: str | None = None,
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        return 0

    now = utc_now_iso()
    raw_json = json.dumps(raw or {}, ensure_ascii=True)
    title_text = str(title or "").strip() or f"{source_u} Master {source_master}"
    artist_text = str(artist_or_brand or "").strip() or None
    domain_text = _normalize_domain_code_value(domain_code)
    release_type_text = str(release_type or "").strip() or None
    year_value = int(release_year) if isinstance(release_year, int) else None

    with get_conn() as conn:
        current = conn.execute(
            """
            SELECT id, sort_artist_name
            FROM album_master
            WHERE id = ?
            """,
            (master_id,),
        ).fetchone()
        if current is None:
            return 0

        existing = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()

        if existing is not None:
            target_master_id = int(existing["id"])
            if target_master_id != master_id:
                current_sort_artist_name = str(current["sort_artist_name"] or "").strip() or None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO album_master_member
                      (album_master_id, owned_item_id, created_at)
                    SELECT ?, owned_item_id, ?
                    FROM album_master_member
                    WHERE album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute(
                    """
                    UPDATE owned_item
                    SET linked_album_master_id = ?, updated_at = ?
                    WHERE linked_album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute(
                    """
                    UPDATE album_master
                    SET title = ?,
                        artist_or_brand = ?,
                        sort_artist_name = CASE
                                             WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                             ELSE sort_artist_name
                                           END,
                        domain_code = COALESCE(?, domain_code),
                        release_type = COALESCE(?, release_type),
                        release_year = ?,
                        raw_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (title_text, artist_text, current_sort_artist_name, domain_text, release_type_text, year_value, raw_json, now, target_master_id),
                )
                conn.execute(
                    """
                    UPDATE album_master_external_ref
                    SET album_master_id = ?, updated_at = ?
                    WHERE album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
                master_id = target_master_id
            else:
                master_id = target_master_id

        conn.execute(
            """
            UPDATE album_master
            SET source_code = ?,
                source_master_id = ?,
                title = ?,
                artist_or_brand = ?,
                domain_code = COALESCE(?, domain_code),
                release_type = COALESCE(?, release_type),
                release_year = ?,
                raw_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (source_u, source_master, title_text, artist_text, domain_text, release_type_text, year_value, raw_json, now, master_id),
        )
    ensure_album_master_external_ref(
        album_master_id=master_id,
        source_code=source_u,
        source_master_id=source_master,
        title_hint=title_text,
        artist_or_brand_hint=artist_text,
        release_year=year_value,
        raw=raw,
    )
    return master_id


# `_album_master_source_priority` and `list_duplicate_album_masters`
# live in app/db/album_master_duplicates.py and are re-exported from
# this package's __init__ at the bottom of the file.


# `_json_loads_or_default` lives in app/db/album_master_merge_history.py
# and is module-private to that slice. Code in this module that needs
# defensive JSON parsing inlines its own try/except.


def _snapshot_album_master_record(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    data = dict(row)
    return {
        "id": int(data.get("id") or 0),
        "source_code": str(data.get("source_code") or "").strip(),
        "source_master_id": str(data.get("source_master_id") or "").strip(),
        "title": str(data.get("title") or "").strip(),
        "artist_or_brand": str(data.get("artist_or_brand") or "").strip() or None,
        "sort_artist_name": str(data.get("sort_artist_name") or "").strip() or None,
        "domain_code": _normalize_domain_code_value(data.get("domain_code")),
        "release_year": int(data["release_year"]) if data.get("release_year") not in (None, "") else None,
        "raw_json": str(data.get("raw_json") or "{}"),
        "created_at": str(data.get("created_at") or "").strip(),
        "updated_at": str(data.get("updated_at") or "").strip(),
    }


def _snapshot_member_link_records(rows: list[sqlite3.Row] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        data = dict(row)
        owned_item_id = int(data.get("owned_item_id") or 0)
        if owned_item_id <= 0:
            continue
        out.append(
            {
                "owned_item_id": owned_item_id,
                "linked_album_master_id": int(data["linked_album_master_id"]) if data.get("linked_album_master_id") not in (None, "") else None,
                "created_at": str(data.get("created_at") or "").strip() or utc_now_iso(),
            }
        )
    return out


def _snapshot_external_ref_records(rows: list[sqlite3.Row] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        data = dict(row)
        ref_id = int(data.get("id") or 0)
        if ref_id <= 0:
            continue
        out.append(
            {
                "id": ref_id,
                "source_code": str(data.get("source_code") or "").strip(),
                "source_master_id": str(data.get("source_master_id") or "").strip(),
                "title_hint": str(data.get("title_hint") or "").strip() or None,
                "artist_or_brand_hint": str(data.get("artist_or_brand_hint") or "").strip() or None,
                "release_year": int(data["release_year"]) if data.get("release_year") not in (None, "") else None,
                "raw_json": str(data.get("raw_json") or "{}"),
                "created_at": str(data.get("created_at") or "").strip() or utc_now_iso(),
                "updated_at": str(data.get("updated_at") or "").strip() or utc_now_iso(),
            }
        )
    return out


# `_album_master_merge_history_record`,
# `_latest_open_album_master_merge_history_id`,
# `list_album_master_merge_history`, and
# `rollback_latest_album_master_merge` live in
# app/db/album_master_merge_history.py and are re-exported from
# this package's __init__ at the bottom of the file.


def merge_album_masters(
    source_album_master_id: int,
    target_album_master_id: int,
    merged_by: str | None = None,
) -> dict[str, int | None]:
    source_id = int(source_album_master_id or 0)
    target_id = int(target_album_master_id or 0)
    normalized_actor = str(merged_by or "").strip() or None
    if source_id <= 0 or target_id <= 0:
        raise ValueError("source/target album_master_id must be positive")

    # Source-code priority: higher rank = preferred as target (survives merge).
    # When the caller-supplied target has lower priority than the source,
    # swap them so the higher-priority master always survives.
    _SOURCE_PRIORITY = {"DISCOGS": 10, "MANIADB": 5, "ALADIN": 3, "MANUAL": 1}

    def _source_priority(master_id: int) -> int:
        with get_conn() as _c:
            _r = _c.execute("SELECT source_code FROM album_master WHERE id=?", (master_id,)).fetchone()
        code = str((_r["source_code"] if _r else None) or "").strip().upper()
        return _SOURCE_PRIORITY.get(code, 0)

    if _source_priority(source_id) > _source_priority(target_id):
        source_id, target_id = target_id, source_id

    # Album master merge fans into many UPDATEs (album_master_member,
    # owned_item.linked_album_master_id, album_master_external_ref) and a
    # final DELETE on the source row. Hold the write lock from the start so
    # a concurrent metadata sync can't sneak an UPDATE on the source row
    # mid-merge.
    with get_write_conn() as conn:
        target_row = conn.execute(
            """
            SELECT id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        if target_row is None:
            raise LookupError("target album_master not found")

        if source_id == target_id:
            target_member_count_row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM album_master_member
                WHERE album_master_id = ?
                """,
                (target_id,),
            ).fetchone()
            return {
                "source_album_master_id": source_id,
                "target_album_master_id": target_id,
                "moved_member_count": 0,
                "target_member_count": int(target_member_count_row["cnt"] or 0) if target_member_count_row else 0,
                "merge_history_id": None,
            }

        source_row = conn.execute(
            """
            SELECT id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        if source_row is None:
            raise LookupError("source album_master not found")

        source_member_rows = conn.execute(
            """
            SELECT amm.owned_item_id, amm.created_at, oi.linked_album_master_id
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE album_master_id = ?
            ORDER BY amm.id ASC
            """,
            (source_id,),
        ).fetchall()
        source_member_links = _snapshot_member_link_records(source_member_rows)
        source_owned_item_ids = [int(item["owned_item_id"]) for item in source_member_links if int(item["owned_item_id"]) > 0]
        overlap_owned_item_ids: list[int] = []
        if source_owned_item_ids:
            placeholders = ",".join("?" for _ in source_owned_item_ids)
            overlap_rows = conn.execute(
                f"""
                SELECT owned_item_id
                FROM album_master_member
                WHERE album_master_id = ? AND owned_item_id IN ({placeholders})
                ORDER BY owned_item_id ASC
                """,
                [target_id, *source_owned_item_ids],
            ).fetchall()
            overlap_owned_item_ids = [int(row["owned_item_id"] or 0) for row in overlap_rows if int(row["owned_item_id"] or 0) > 0]
        source_external_ref_rows = conn.execute(
            """
            SELECT id, source_code, source_master_id, title_hint, artist_or_brand_hint, release_year, raw_json, created_at, updated_at
            FROM album_master_external_ref
            WHERE album_master_id = ?
            ORDER BY id ASC
            """,
            (source_id,),
        ).fetchall()
        source_external_refs = _snapshot_external_ref_records(source_external_ref_rows)
        source_snapshot = _snapshot_album_master_record(source_row)
        target_snapshot = _snapshot_album_master_record(target_row)

        now = utc_now_iso()
        moved_member_count = max(0, len(source_owned_item_ids) - len(overlap_owned_item_ids))

        conn.execute(
            """
            INSERT OR IGNORE INTO album_master_member
              (album_master_id, owned_item_id, created_at)
            SELECT ?, owned_item_id, ?
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute(
            """
            UPDATE owned_item
            SET linked_album_master_id = ?, updated_at = ?
            WHERE linked_album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute(
            """
            UPDATE album_master
            SET title = CASE
                          WHEN TRIM(COALESCE(title, '')) = '' THEN ?
                          ELSE title
                        END,
                artist_or_brand = CASE
                                    WHEN TRIM(COALESCE(artist_or_brand, '')) = '' THEN ?
                                    ELSE artist_or_brand
                                  END,
                sort_artist_name = CASE
                                     WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                     ELSE sort_artist_name
                                   END,
                domain_code = CASE
                                WHEN TRIM(COALESCE(domain_code, '')) = '' THEN ?
                                ELSE domain_code
                              END,
                release_year = COALESCE(release_year, ?),
                raw_json = CASE
                             WHEN TRIM(COALESCE(raw_json, '')) IN ('', '{}') THEN ?
                             ELSE raw_json
                           END,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(source_row["title"] or "").strip() or None,
                str(source_row["artist_or_brand"] or "").strip() or None,
                str(source_row["sort_artist_name"] or "").strip() or None,
                _normalize_domain_code_value(source_row["domain_code"]),
                source_row["release_year"],
                str(source_row["raw_json"] or "{}"),
                now,
                target_id,
            ),
        )
        _sync_album_master_domain_code_in_conn(conn, target_id)
        conn.execute(
            """
            UPDATE album_master_external_ref
            SET album_master_id = ?, updated_at = ?
            WHERE album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute("DELETE FROM album_master WHERE id = ?", (source_id,))

        target_after_row = conn.execute(
            """
            SELECT id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        target_member_count_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (target_id,),
        ).fetchone()
        history_cur = conn.execute(
            """
            INSERT INTO album_master_merge_history
              (
                source_album_master_id,
                target_album_master_id,
                source_master_snapshot_json,
                target_master_snapshot_json,
                source_member_links_json,
                source_external_refs_json,
                overlap_owned_item_ids_json,
                moved_member_count,
                target_member_count,
                merged_by,
                created_at,
                target_updated_at_after_merge
              )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                target_id,
                json.dumps(source_snapshot, ensure_ascii=True),
                json.dumps(target_snapshot, ensure_ascii=True),
                json.dumps(source_member_links, ensure_ascii=True),
                json.dumps(source_external_refs, ensure_ascii=True),
                json.dumps(overlap_owned_item_ids, ensure_ascii=True),
                moved_member_count,
                int(target_member_count_row["cnt"] or 0) if target_member_count_row else 0,
                normalized_actor,
                now,
                str(target_after_row["updated_at"] or "").strip() if target_after_row else None,
            ),
        )

    return {
        "source_album_master_id": source_id,
        "target_album_master_id": target_id,
        "moved_member_count": moved_member_count,
        "target_member_count": int(target_member_count_row["cnt"] or 0) if target_member_count_row else 0,
        "merge_history_id": int(history_cur.lastrowid or 0) or None,
    }


# `bind_album_master_members`, `album_master_exists`, and
# `update_album_master_sort_artist_name` live in
# app/db/album_master_member.py and are re-exported from this
# package's __init__ at the bottom of the file.


# `get_album_master_correction_state` and
# `update_album_master_correction` live in
# app/db/album_master_correction.py and are re-exported from this
# package's __init__ at the bottom of the file.


__all__ = [
    "_sync_album_master_domain_code_in_conn",
    "_snapshot_album_master_record",
    "_snapshot_member_link_records",
    "_snapshot_external_ref_records",
    "upsert_album_master",
    "update_album_master_genres",
    "normalize_album_master_source_id",
    "promote_album_master_source",
    "merge_album_masters",
]
