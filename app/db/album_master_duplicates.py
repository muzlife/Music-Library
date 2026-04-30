"""Album master duplicate-detection DB surface.

Fourteenth slice extracted from the legacy `app/db.py`. Owns the
"이 마스터와 동일한 앨범으로 보이는 다른 마스터 후보" query that
backs the album-master merge UI: given one master id, find other
masters with the same normalised title + artist (and optionally
matching release_year), ranked by source priority.

Public exports
  * list_duplicate_album_masters — duplicate-candidate query.

Module-private
  * _album_master_source_priority — Python-side equivalent of the
    SQL CASE in the duplicate query. Currently unused from inside
    this module (the priority is inlined into the SQL ORDER BY) but
    kept here as the canonical single source of truth so callers
    that need a Python-side ordering of source_codes have somewhere
    consistent to reach for. Also re-exported via the package
    surface for parity with the historical `app/db.py` API.

`app/db/__init__.py` re-exports both symbols so existing call sites
(the album-master admin route's "유사 마스터" panel, the test
suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import get_conn  # noqa: E402  — package surface


def _album_master_source_priority(source_code: str) -> int:
    code = str(source_code or "").strip().upper()
    if code == "DISCOGS":
        return 0
    if code == "MANIADB":
        return 1
    if code == "MUSICBRAINZ":
        return 2
    return 3


def list_duplicate_album_masters(album_master_id: int, limit: int = 20) -> list[dict[str, Any]]:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return []
    limit_n = max(1, min(100, int(limit or 20)))

    with get_conn() as conn:
        source_row = conn.execute(
            """
            SELECT id, title, artist_or_brand, release_year
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
        if source_row is None:
            return []

        norm_title = str(source_row["title"] or "").strip().lower()
        norm_artist = str(source_row["artist_or_brand"] or "").strip().lower()
        if not norm_title:
            return []
        base_year = source_row["release_year"]

        rows = conn.execute(
            """
            SELECT
              am.id AS album_master_id,
              am.source_code,
              am.source_master_id,
              am.title,
              am.artist_or_brand,
              am.release_year,
              am.updated_at,
              (
                SELECT COUNT(*)
                FROM album_master_member amm
                WHERE amm.album_master_id = am.id
              ) AS member_count
            FROM album_master am
            WHERE am.id <> ?
              AND LOWER(TRIM(COALESCE(am.title, ''))) = ?
              AND LOWER(TRIM(COALESCE(am.artist_or_brand, ''))) = ?
              AND (
                ? IS NULL
                OR am.release_year = ?
                OR am.release_year IS NULL
              )
            ORDER BY
              CASE am.source_code
                WHEN 'DISCOGS' THEN 0
                WHEN 'MANIADB' THEN 1
                ELSE 2
              END ASC,
              CASE
                WHEN ? IS NOT NULL AND am.release_year = ? THEN 0
                ELSE 1
              END ASC,
              member_count DESC,
              am.updated_at DESC,
              am.id DESC
            LIMIT ?
            """,
            (master_id, norm_title, norm_artist, base_year, base_year, base_year, base_year, limit_n),
        ).fetchall()

    return [dict(row) for row in rows]


__all__ = [
    "_album_master_source_priority",
    "list_duplicate_album_masters",
]
