"""Album master external-ref DB surface.

Twelfth slice extracted from the legacy `app/db.py`. Owns the
`album_master_external_ref` table CRUD — the lookup that maps third-
party source ids (`(source_code, source_master_id)` like
`("DISCOGS", "12345")`) to local `album_master_id`s and remembers
the title/artist/year hints that came with each ref.

Public exports
  * get_album_master_id_by_external_ref — single-row reverse lookup
    used by metadata sync to dedupe by source key before falling
    back to fuzzy match.
  * list_album_master_external_refs — list every external ref
    attached to a master, optionally filtered by source. Powers the
    "외부 ID" 패널 on the album-master detail screen.
  * ensure_album_master_external_ref — INSERT…ON CONFLICT
    upsert that the metadata sync calls every time it sees a
    confirmed link from the various provider modules.

Cross-package dependencies kept on the package surface
  * `_ensure_album_master_external_ref_table` is the table-creation
    helper called from init_db / migrations and stays in
    `app/db/__init__.py`.
  * `normalize_album_master_source_id` and `promote_album_master_source`
    perform major surgery on `album_master` itself (UPDATE / DELETE,
    member moves, owned_item linked-master rewires) — those stay in
    `__init__.py` and call into THIS slice for the external-ref
    upserts (via the package surface).

`app/db/__init__.py` re-exports every public symbol so existing
callers (the album-master admin route, the metadata sync providers,
the upsert path inside __init__.py itself) keep working unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import get_conn, utc_now_iso  # noqa: E402  — package surface


def get_album_master_id_by_external_ref(source_code: str, source_master_id: str) -> int | None:
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if not source_u or not source_master:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT album_master_id
            FROM album_master_external_ref
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()
    if row is None:
        return None
    return int(row["album_master_id"] or 0) or None


def list_album_master_external_refs(
    album_master_id: int,
    source_code: str | None = None,
) -> list[dict[str, Any]]:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return []
    query = """
        SELECT
          id,
          album_master_id,
          source_code,
          source_master_id,
          title_hint,
          artist_or_brand_hint,
          release_year,
          raw_json,
          created_at,
          updated_at
        FROM album_master_external_ref
        WHERE album_master_id = ?
    """
    params: list[Any] = [master_id]
    source_u = str(source_code or "").strip().upper()
    if source_u:
        query += " AND source_code = ?"
        params.append(source_u)
    query += " ORDER BY updated_at DESC, id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def ensure_album_master_external_ref(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
    title_hint: str | None = None,
    artist_or_brand_hint: str | None = None,
    release_year: int | None = None,
    raw: dict[str, Any] | None = None,
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        raise ValueError("album_master_id, source_code, source_master_id required")

    now = utc_now_iso()
    raw_json = json.dumps(raw or {}, ensure_ascii=True)
    with get_conn() as conn:
        _existing_ref = conn.execute(
            "SELECT album_master_id FROM album_master_external_ref WHERE source_code=? AND source_master_id=?",
            (source_u, source_master),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO album_master_external_ref
              (album_master_id, source_code, source_master_id, title_hint, artist_or_brand_hint, release_year, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_code, source_master_id) DO UPDATE SET
              album_master_id = excluded.album_master_id,
              title_hint = COALESCE(excluded.title_hint, album_master_external_ref.title_hint),
              artist_or_brand_hint = COALESCE(excluded.artist_or_brand_hint, album_master_external_ref.artist_or_brand_hint),
              release_year = COALESCE(excluded.release_year, album_master_external_ref.release_year),
              raw_json = CASE
                           WHEN TRIM(COALESCE(excluded.raw_json, '{}')) IN ('', '{}') THEN album_master_external_ref.raw_json
                           ELSE excluded.raw_json
                         END,
              updated_at = excluded.updated_at
            """,
            (
                master_id,
                source_u,
                source_master,
                str(title_hint or "").strip() or None,
                str(artist_or_brand_hint or "").strip() or None,
                release_year,
                raw_json,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM album_master_external_ref
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()
    if row is None:
        raise RuntimeError("album_master_external_ref upsert failed")
    if _existing_ref and int(_existing_ref["album_master_id"]) != master_id:
        try:
            from app.db.audit_log import log_audit_event
            log_audit_event(
                entity_type="album_master", entity_id=master_id,
                action="EXTERNAL_REF_UPDATE", changed_by=None,
                snapshot={
                    "source": source_u,
                    "source_master_id": source_master,
                    "before_album_master_id": int(_existing_ref["album_master_id"]),
                    "after_album_master_id": master_id,
                },
            )
        except Exception:
            pass
    return int(row["id"])


__all__ = [
    "get_album_master_id_by_external_ref",
    "list_album_master_external_refs",
    "ensure_album_master_external_ref",
]
