"""Album master read surface.

Twentieth slice extracted from the legacy `app/db.py`. Owns every
read-only album-master query plus a couple of small writes that
directly compose with those reads.

Public exports
  * list_album_masters / count_album_masters — main listing + total
    count for the admin grid. Both delegate filter building to the
    private helper below.
  * get_album_master_binding_for_owned_item — for a given
    owned_item_id, return the bound album_master row joined with
    its source code/master id. Used by the auto-linking path.
  * get_album_master_domain_hint — short helper that picks a
    `domain_code` for an album master from member-derived priority.
  * list_owned_items_by_album_master — all owned_items currently
    linked to a master, used by merge / detail views.
  * set_owned_item_linked_album_master — single-column write that
    rebinds an owned_item to a different master (or unbinds with
    None). Sits with the reads because it is the dual to
    `get_album_master_binding_for_owned_item`.

Module-private
  * _build_album_master_filter_sql — shared WHERE/ORDER builder for
    list/count. Heavy generic with many filter axes (q, source,
    domain, year ranges, has-members, etc.) — the bulk of this
    slice's line count.

Cross-package dependencies kept on the package surface
  * `_normalize_domain_code_value`, `_normalize_owned_item_row`,
    `_owned_item_select_query`, `_search_token_groups`,
    `_build_compact_token_match_sql`, `_column_exists` — all
    cross-cutting helpers used by other still-in-__init__.py paths.
    The submodule pulls them via the package surface.

`app/db/__init__.py` re-exports every public symbol so existing
callers (`app/main.py`, the test suite, the album-master admin
routes) keep working unchanged.
"""

from __future__ import annotations

import os
from typing import Any

from app.db._schema_helpers import _column_exists
from app.db import (  # noqa: E402  — package surface
    _build_compact_token_match_sql,
    _normalize_domain_code_value,
    _normalize_owned_item_row,
    _owned_item_select_query,
    _search_token_groups,
    get_conn,
    utc_now_iso,
)
from app.db.catalog_search import fts_escape

_USE_FTS = os.environ.get("SEARCH_USE_FTS", "1") != "0"


def _build_album_master_filter_sql(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
    owned_item_id: int | None = None,
    signature_types: list[str] | None = None,
    packaging: list[str] | None = None,
    package_contents: list[str] | None = None,
    is_limited: bool | None = None,
    is_new: bool | None = None,
    is_promo: bool | None = None,
    album_master_id: int | None = None,
    genre_missing: bool = False,
    format_missing: bool = False,
    catalog_missing: bool = False,
    review_missing: bool = False,
    local_missing: bool = False,
    release_type_missing: bool = False,
    spotify_state: str = "ANY",
) -> tuple[str, list[Any]]:
    where_sql = ""
    params: list[Any] = []
    master_search_expr = "COALESCE(am.artist_or_brand, '') || ' ' || COALESCE(am.title, '')"
    member_search_expr = """
        COALESCE(mid.artist_or_brand, '') || ' ' ||
        COALESCE(oi.item_name_override, '') || ' ' ||
        COALESCE(mid.label_name, '') || ' ' ||
        COALESCE(mid.catalog_no, '') || ' ' ||
        COALESCE(mid.barcode, '') || ' ' ||
        COALESCE(mid.track_list_json, '') || ' ' ||
        COALESCE(mid.track_items_json, '')
    """

    if album_master_id:
        where_sql += " AND am.id = ?"
        params.append(album_master_id)

    if source_code:
        where_sql += " AND am.source_code = ?"
        params.append(source_code)

    if q and q.strip():
        if _USE_FTS:
            q_escaped = fts_escape(q.strip())
            where_sql += """
              AND (
                am.id IN (SELECT rowid FROM album_master_fts WHERE album_master_fts MATCH ?)
                OR am.id IN (
                  SELECT amm.album_master_id FROM album_master_member amm
                  WHERE amm.owned_item_id IN (SELECT rowid FROM catalog_search WHERE catalog_search MATCH ?)
                )
              )
            """
            params.extend([q_escaped, q_escaped])
        else:
            q_norm = f"%{q.strip().lower()}%"
            q_token_groups = _search_token_groups(q)
            master_token_sql, master_token_params = _build_compact_token_match_sql(master_search_expr, q_token_groups)
            member_token_sql, member_token_params = _build_compact_token_match_sql(member_search_expr, q_token_groups)
            where_sql += """
              AND (
                LOWER(am.title) LIKE ?
                OR LOWER(COALESCE(am.artist_or_brand, '')) LIKE ?
                OR EXISTS (
                  SELECT 1
                  FROM album_master_member amm
                  JOIN owned_item oi ON oi.id = amm.owned_item_id
                  LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                  WHERE amm.album_master_id = am.id
                    AND (
                      LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
                      OR LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                      OR LOWER(COALESCE(mid.label_name, '')) LIKE ?
                      OR LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
                      OR LOWER(COALESCE(mid.barcode, '')) LIKE ?
                      OR EXISTS (
                        SELECT 1
                        FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
                        WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
                      )
                      OR EXISTS (
                        SELECT 1
                        FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
                        WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
                           OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
                      )
                  )
              )
            """
            params.extend([q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm])
            if master_token_sql:
                where_sql += f"""
                OR {master_token_sql}
                """
                params.extend(master_token_params)
            if member_token_sql:
                where_sql += f"""
                OR EXISTS (
                  SELECT 1
                  FROM album_master_member amm
                  JOIN owned_item oi ON oi.id = amm.owned_item_id
                  LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                  WHERE amm.album_master_id = am.id
                    AND {member_token_sql}
                )
                """
                params.extend(member_token_params)
            where_sql += """
              )
            """

    if artist_or_brand and artist_or_brand.strip():
        if _USE_FTS:
            artist_escaped = fts_escape(artist_or_brand.strip())
            where_sql += """
              AND (
                am.id IN (SELECT rowid FROM album_master_fts WHERE album_master_fts MATCH ?)
                OR am.id IN (
                  SELECT amm.album_master_id FROM album_master_member amm
                  WHERE amm.owned_item_id IN (SELECT rowid FROM catalog_search WHERE catalog_search MATCH ?)
                )
              )
            """
            params.extend([f"artist : {artist_escaped}", f"artist : {artist_escaped}"])
        else:
            artist_norm = f"%{artist_or_brand.strip().lower()}%"
            where_sql += """
              AND (
                LOWER(COALESCE(am.artist_or_brand, '')) LIKE ?
                OR EXISTS (
                  SELECT 1
                  FROM album_master_member amm
                  JOIN owned_item oi ON oi.id = amm.owned_item_id
                  LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                  WHERE amm.album_master_id = am.id
                    AND LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                )
              )
            """
            params.extend([artist_norm, artist_norm])

    if item_name and item_name.strip():
        if _USE_FTS:
            item_escaped = fts_escape(item_name.strip())
            where_sql += """
              AND (
                am.id IN (SELECT rowid FROM album_master_fts WHERE album_master_fts MATCH ?)
                OR am.id IN (
                  SELECT amm.album_master_id FROM album_master_member amm
                  WHERE amm.owned_item_id IN (SELECT rowid FROM catalog_search WHERE catalog_search MATCH ?)
                )
              )
            """
            params.extend([item_escaped, f"item_name : {item_escaped}"])
        else:
            item_norm = f"%{item_name.strip().lower()}%"
            item_token_groups = _search_token_groups(item_name)
            master_token_sql, master_token_params = _build_compact_token_match_sql(master_search_expr, item_token_groups)
            member_token_sql, member_token_params = _build_compact_token_match_sql(member_search_expr, item_token_groups)
            where_sql += """
              AND (
                LOWER(am.title) LIKE ?
                OR LOWER(COALESCE(am.artist_or_brand, '') || ' ' || COALESCE(am.title, '')) LIKE ?
                OR EXISTS (
                  SELECT 1
                  FROM album_master_member amm
                  JOIN owned_item oi ON oi.id = amm.owned_item_id
                  LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                  WHERE amm.album_master_id = am.id
                    AND (
                      LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
                      OR LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                      OR LOWER(COALESCE(mid.label_name, '')) LIKE ?
                      OR LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
                      OR LOWER(COALESCE(mid.barcode, '')) LIKE ?
                      OR LOWER(COALESCE(mid.artist_or_brand, '') || ' ' || COALESCE(oi.item_name_override, '')) LIKE ?
                      OR EXISTS (
                        SELECT 1
                        FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
                        WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
                      )
                      OR EXISTS (
                        SELECT 1
                        FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
                        WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
                           OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
                      )
            """
            params.extend([item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm])
            if member_token_sql:
                where_sql += f"""
                      OR {member_token_sql}
                """
                params.extend(member_token_params)
            where_sql += """
                    )
                )
            """
            if master_token_sql:
                where_sql += f"""
                OR {master_token_sql}
                """
                params.extend(master_token_params)
            where_sql += """
              )
            """

    if catalog_no and catalog_no.strip():
        if _USE_FTS:
            where_sql += """
              AND am.id IN (
                SELECT amm.album_master_id FROM album_master_member amm
                WHERE amm.owned_item_id IN (SELECT rowid FROM catalog_search WHERE catalog_search MATCH ?)
              )
            """
            params.append(f"catalog_no : {fts_escape(catalog_no.strip())}")
        else:
            catalog_norm = f"%{catalog_no.strip().lower()}%"
            where_sql += """
              AND EXISTS (
                SELECT 1
                FROM album_master_member amm
                JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
                WHERE amm.album_master_id = am.id
                  AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
              )
            """
            params.append(catalog_norm)

    if barcode and barcode.strip():
        barcode_norm = f"%{barcode.strip().replace('-', '')}%"
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND REPLACE(COALESCE(mid.barcode, ''), '-', '') LIKE ?
          )
        """
        params.append(barcode_norm)

    if release_year is not None:
        where_sql += """
          AND (
            am.release_year = ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
              WHERE amm.album_master_id = am.id
                AND mid.release_year = ?
            )
          )
        """
        params.extend([int(release_year), int(release_year)])

    if category:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.category = ?
          )
        """
        params.append(category)

    if media_only:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
          )
        """

    if domain_code:
        where_sql += """
          AND COALESCE(am.override_domain_code, am.domain_code) = ?
        """
        params.append(domain_code)

    if release_type:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.release_type = ?
          )
        """
        params.append(release_type)

    if owned_item_id is not None:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            WHERE amm.album_master_id = am.id
              AND amm.owned_item_id = ?
          )
        """
        params.append(owned_item_id)

    if signature_types:
        placeholders = ", ".join("?" for _ in signature_types)
        where_sql += f"""
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.signature_type IN ({placeholders})
          )
        """
        params.extend(signature_types)

    if packaging:
        pkg_list = [packaging] if isinstance(packaging, str) else list(packaging)
        pkg_list = [p.strip().lower() for p in pkg_list if p and p.strip()]
        if pkg_list:
            pkg_clauses = " OR ".join("LOWER(COALESCE(mid.format_name, '')) LIKE ?" for _ in pkg_list)
            where_sql += f"""
              AND EXISTS (
                SELECT 1
                FROM album_master_member amm
                JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
                WHERE amm.album_master_id = am.id
                  AND ({pkg_clauses})
              )
            """
            for pkg in pkg_list:
                params.append(f"%{pkg}%")

    if package_contents:
        pc_list = [package_contents] if isinstance(package_contents, str) else list(package_contents)
        pc_list = [pc.strip().lower() for pc in pc_list if pc and pc.strip()]
        if pc_list:
            pc_clauses = " OR ".join("LOWER(COALESCE(mid.package_contents, '')) LIKE ?" for _ in pc_list)
            where_sql += f"""
              AND EXISTS (
                SELECT 1
                FROM album_master_member amm
                JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
                WHERE amm.album_master_id = am.id
                  AND ({pc_clauses})
              )
            """
            for pc in pc_list:
                params.append(f"%{pc}%")

    if is_limited:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND mid.is_limited_edition = 1
          )
        """

    if is_new:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.is_second_hand = 0
          )
        """

    if is_promo:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND mid.is_promotional_not_for_sale = 1
          )
        """


    if genre_missing:
        where_sql += """
          AND (am.genres_json IS NULL OR TRIM(am.genres_json) = '' OR am.genres_json = '[]')
        """

    if format_missing:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member ammf
            JOIN owned_item oif ON oif.id = ammf.owned_item_id
            LEFT JOIN music_item_detail midf ON midf.owned_item_id = oif.id
            WHERE ammf.album_master_id = am.id
              AND oif.category IN ('LP','CD','CASSETTE','8TRACK','DIGITAL','REEL_TO_REEL')
              AND (midf.format_name IS NULL OR TRIM(midf.format_name) = '')
          )
        """

    if catalog_missing:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member ammc
            JOIN owned_item oic ON oic.id = ammc.owned_item_id
            LEFT JOIN music_item_detail midc ON midc.owned_item_id = oic.id
            WHERE ammc.album_master_id = am.id
              AND oic.category IN ('LP','CD','CASSETTE','8TRACK','DIGITAL','REEL_TO_REEL')
              AND (midc.catalog_no IS NULL OR TRIM(midc.catalog_no) = '')
          )
        """

    if review_missing:
        where_sql += " AND (am.review_text IS NULL OR TRIM(am.review_text) = '')"

    if release_type_missing:
        where_sql += " AND (am.release_type IS NULL OR TRIM(am.release_type) = '')"

    if local_missing:
        where_sql += """
          AND NOT EXISTS (
            SELECT 1 FROM album_master_local_link amll
            WHERE amll.album_master_id = am.id
          )
        """

    if spotify_state == "MISSING":
        where_sql += " AND (am.spotify_album_id IS NULL OR TRIM(am.spotify_album_id) = '')"
    elif spotify_state == "MATCHED":
        where_sql += " AND (am.spotify_album_id IS NOT NULL AND TRIM(am.spotify_album_id) <> '')"

    return where_sql, params


def get_album_master_binding_for_owned_item(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              am.id AS album_master_id,
              am.source_code,
              am.source_master_id,
              am.title,
              am.artist_or_brand,
              am.sort_artist_name,
              am.release_year,
              am.domain_code,
              am.source_release_year,
              am.source_domain_code,
              am.override_release_year,
              am.override_domain_code,
              am.override_note,
              am.override_title,
              am.override_artist_or_brand,
              am.spotify_album_id,
              am.review_text,
              am.review_source,
              am.review_url,
              am.genres_json,
              am.styles_json
            FROM album_master_member amm
            JOIN album_master am ON am.id = amm.album_master_id
            WHERE amm.owned_item_id = ?
            ORDER BY am.updated_at DESC, am.id DESC
            LIMIT 1
            """,
            (owned_item_id,),
        ).fetchone()
    return dict(row) if row else None


def get_album_master_domain_hint(album_master_id: int) -> str | None:
    with get_conn() as conn:
        if _column_exists(conn, "album_master", "domain_code"):
            master_row = conn.execute(
                """
                SELECT domain_code
                FROM album_master
                WHERE id = ?
                LIMIT 1
                """,
                (int(album_master_id),),
            ).fetchone()
            direct_code = _normalize_domain_code_value(master_row["domain_code"]) if master_row is not None else None
            if direct_code:
                return direct_code
        row = conn.execute(
            """
            SELECT oi.domain_code, COUNT(*) AS cnt
            FROM owned_item oi
            WHERE oi.linked_album_master_id = ?
              AND oi.domain_code IS NOT NULL
              AND TRIM(oi.domain_code) <> ''
            GROUP BY oi.domain_code
            ORDER BY cnt DESC, oi.domain_code ASC
            LIMIT 1
            """,
            (int(album_master_id),),
        ).fetchone()
    if row is None:
        return None
    return _normalize_domain_code_value(row["domain_code"])


# `_sync_album_master_domain_code_in_conn` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


def list_owned_items_by_album_master(album_master_id: int) -> list[dict[str, Any]]:
    query = (
        _owned_item_select_query()
        + """
        JOIN album_master_member amm ON amm.owned_item_id = oi.id
        WHERE amm.album_master_id = ?
        ORDER BY
          CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
          oi.order_key ASC,
          CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
          oi.display_rank ASC,
          oi.created_at DESC,
          oi.id DESC
        """
    )
    with get_conn() as conn:
        rows = conn.execute(query, (album_master_id,)).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


# `get_album_master_id_by_external_ref`,
# `list_album_master_external_refs`, and
# `ensure_album_master_external_ref` live in
# app/db/album_master_external_ref.py and are re-exported from this
# package's __init__ at the bottom of the file. Internal callers in
# this module (upsert_album_master, normalize_album_master_source_id,
# promote_album_master_source) resolve them via the package surface
# at call time, after the bottom-of-file imports have run.


def set_owned_item_linked_album_master(owned_item_id: int, album_master_id: int | None) -> bool:
    oid = int(owned_item_id or 0)
    if oid <= 0:
        return False
    mid = int(album_master_id) if album_master_id is not None else None
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE owned_item SET linked_album_master_id = ?, updated_at = ? WHERE id = ?",
            (mid, utc_now_iso(), oid),
        )
        # album_master_member 정리 — 이전 마스터 멤버십 제거 후 새 마스터에 보장 추가
        if mid is not None:
            conn.execute(
                "DELETE FROM album_master_member WHERE owned_item_id = ? AND album_master_id != ?",
                (oid, mid),
            )
            conn.execute(
                "INSERT OR IGNORE INTO album_master_member (album_master_id, owned_item_id, created_at)"
                " VALUES (?, ?, ?)",
                (mid, oid, utc_now_iso()),
            )
        else:
            conn.execute(
                "DELETE FROM album_master_member WHERE owned_item_id = ?",
                (oid,),
            )
        return int(cur.rowcount or 0) > 0


def get_album_master(album_master_id: int) -> dict[str, Any] | None:
    """Get a single album_master by ID."""
    from app.db.connection import get_conn
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()


def list_album_masters(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
    limit: int,
    offset: int,
    sort_mode: str | None = None,
    owned_item_id: int | None = None,
    signature_types: list[str] | None = None,
    packaging: list[str] | None = None,
    package_contents: list[str] | None = None,
    is_limited: bool | None = None,
    is_new: bool | None = None,
    is_promo: bool | None = None,
    album_master_id: int | None = None,
    genre_missing: bool = False,
    format_missing: bool = False,
    catalog_missing: bool = False,
    review_missing: bool = False,
    local_missing: bool = False,
    release_type_missing: bool = False,
    spotify_state: str = "ANY",
) -> list[dict[str, Any]]:
    filter_sql, params = _build_album_master_filter_sql(
        source_code=source_code,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        category=category,
        media_only=media_only,
        domain_code=domain_code,
        release_type=release_type,
        owned_item_id=owned_item_id,
        signature_types=signature_types,
        packaging=packaging,
        package_contents=package_contents,
        is_limited=is_limited,
        is_new=is_new,
        is_promo=is_promo,
        album_master_id=album_master_id,
        genre_missing=genre_missing,
        format_missing=format_missing,
        catalog_missing=catalog_missing,
        review_missing=review_missing,
        local_missing=local_missing,
        release_type_missing=release_type_missing,
        spotify_state=spotify_state,
    )

    query = """
      SELECT
        am.id,
        am.source_code,
        am.source_master_id,
        am.title,
        am.artist_or_brand,
        am.sort_artist_name,
        am.domain_code,
        COALESCE(am.override_release_year, am.release_year) AS release_year,
        am.updated_at,
        am.spotify_album_id,
        am.spotify_album_uri,
        am.spotify_matched_at,
        am.spotify_image_url,
        am.review_text,
        am.review_source,
        am.review_url,
        am.genres_json,
        am.styles_json,
        COUNT(amm.id) AS member_count,
        MAX(amm.owned_item_id) AS max_owned_item_id,
        (
          SELECT mid.cover_image_url
          FROM album_master_member amm_cov
          JOIN owned_item oi_cov ON oi_cov.id = amm_cov.owned_item_id
          LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_cov.id
          WHERE amm_cov.album_master_id = am.id
            AND mid.cover_image_url IS NOT NULL
            AND TRIM(mid.cover_image_url) <> ''
          ORDER BY
            CASE WHEN oi_cov.order_key IS NULL OR TRIM(oi_cov.order_key) = '' THEN 1 ELSE 0 END,
            oi_cov.order_key ASC,
            oi_cov.id ASC
          LIMIT 1
        ) AS cover_image_url,
        (
          SELECT COUNT(*)
          FROM album_master_member amm_audio
          JOIN owned_item_digital_link oidl ON oidl.owned_item_id = amm_audio.owned_item_id
          JOIN digital_asset da ON da.id = oidl.digital_asset_id
          WHERE amm_audio.album_master_id = am.id
            AND da.asset_type = 'AUDIO'
        ) AS audio_asset_count,
        (
          SELECT GROUP_CONCAT(preview_text, ' || ')
          FROM (
            SELECT TRIM(
              CASE
                WHEN TRIM(COALESCE(mid.label_name, '')) <> '' THEN mid.label_name
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(mid.catalog_no, '')) <> '' THEN
                  CASE WHEN TRIM(COALESCE(mid.label_name, '')) <> '' THEN ' / ' ELSE '' END || mid.catalog_no
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(mid.barcode, '')) <> '' THEN
                  CASE
                    WHEN TRIM(COALESCE(mid.label_name, '')) <> '' OR TRIM(COALESCE(mid.catalog_no, '')) <> '' THEN ' / '
                    ELSE ''
                  END || mid.barcode
                ELSE ''
              END
            ) AS preview_text
            FROM album_master_member amm_prev
            JOIN owned_item oi_prev ON oi_prev.id = amm_prev.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_prev.id
            WHERE amm_prev.album_master_id = am.id
            ORDER BY
              CASE WHEN oi_prev.order_key IS NULL OR TRIM(oi_prev.order_key) = '' THEN 1 ELSE 0 END,
              oi_prev.order_key ASC,
              oi_prev.id ASC
            LIMIT 4
          ) preview_rows
          WHERE TRIM(COALESCE(preview_text, '')) <> ''
        ) AS member_preview_text,
        (
          SELECT GROUP_CONCAT(preview_text, ' || ')
          FROM (
            SELECT TRIM(
              CASE
                WHEN ss.id IS NULL THEN '미배치'
                WHEN TRIM(COALESCE(ss.cabinet_name, '')) <> '' THEN ss.cabinet_name
                WHEN TRIM(COALESCE(ss.slot_code, '')) <> '' THEN ss.slot_code
                ELSE '미배치'
              END ||
              CASE
                WHEN TRIM(COALESCE(ss.column_code, '')) <> '' THEN ' / ' || ss.column_code || '열'
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(ss.cell_code, '')) <> '' THEN ' / ' || ss.cell_code || '칸'
                ELSE ''
              END
            ) AS preview_text
            FROM album_master_member amm_loc
            JOIN owned_item oi_loc ON oi_loc.id = amm_loc.owned_item_id
            LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
            WHERE amm_loc.album_master_id = am.id
            ORDER BY
              CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
              oi_loc.order_key ASC,
              oi_loc.id ASC
            LIMIT 4
          ) preview_rows
          WHERE TRIM(COALESCE(preview_text, '')) <> ''
        ) AS member_location_preview_text,
        (
          SELECT oi_loc.storage_slot_id
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_storage_slot_id,
        (
          SELECT ss.slot_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_slot_code,
        (
          SELECT ss.cabinet_name
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_cabinet_name,
        (
          SELECT ss.column_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_column_code,
        (
          SELECT ss.cell_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_cell_code
      FROM album_master am
      LEFT JOIN album_master_member amm ON amm.album_master_id = am.id
      WHERE 1 = 1
    """
    query += filter_sql
    query += "\n      GROUP BY am.id\n"
    if sort_mode == "RELEASE_DESC":
        query += "      ORDER BY am.release_year DESC, am.id DESC\n"
    elif sort_mode == "UPDATED_DESC":
        query += "      ORDER BY am.updated_at DESC, am.id DESC\n"
    else:
        query += "      ORDER BY max_owned_item_id DESC\n"
    query += "      LIMIT ? OFFSET ?\n"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


# `list_album_master_track_matches` lives in
# app/db/album_master_tracks.py and is re-exported from this
# package's __init__ at the bottom of the file.


def count_album_masters(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
    owned_item_id: int | None = None,
    signature_types: list[str] | None = None,
    packaging: list[str] | None = None,
    package_contents: list[str] | None = None,
    is_limited: bool | None = None,
    is_new: bool | None = None,
    is_promo: bool | None = None,
    genre_missing: bool = False,
    format_missing: bool = False,
    catalog_missing: bool = False,
    review_missing: bool = False,
    local_missing: bool = False,
    release_type_missing: bool = False,
    spotify_state: str = "ANY",
) -> int:
    filter_sql, params = _build_album_master_filter_sql(
        source_code=source_code,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        category=category,
        media_only=media_only,
        domain_code=domain_code,
        release_type=release_type,
        owned_item_id=owned_item_id,
        signature_types=signature_types,
        packaging=packaging,
        package_contents=package_contents,
        is_limited=is_limited,
        is_new=is_new,
        is_promo=is_promo,
        genre_missing=genre_missing,
        format_missing=format_missing,
        catalog_missing=catalog_missing,
        review_missing=review_missing,
        local_missing=local_missing,
        release_type_missing=release_type_missing,
        spotify_state=spotify_state,
    )
    query = """
      SELECT COUNT(*) AS cnt
      FROM album_master am
      WHERE 1 = 1
    """
    query += filter_sql
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return int(row["cnt"]) if row else 0


# `list_album_master_members` and `delete_album_master` live in
# app/db/album_master_member.py and are re-exported from this
# package's __init__ at the bottom of the file.


# `recommend_owned_item_location` and
# `recommend_barcode_candidate_locations` live in
# app/db/location_recommendation.py and are re-exported from
# this package's __init__ at the bottom of the file.


__all__ = [
    "get_album_master_binding_for_owned_item",
    "get_album_master_domain_hint",
    "list_owned_items_by_album_master",
    "set_owned_item_linked_album_master",
    "list_album_masters",
    "count_album_masters",
]
