"""Operator catalog search DB surface.

Thirty-third slice extracted from the legacy `app/db.py`. Owns the
free-text "운영자 통합 검색" engine — the search box at the top of
the operator screens that returns owned_items + storage_slots +
album_masters all at once, ranked by token-match strength.

Public exports
  * search_operator_catalog — given a free-form query string, return
    a dict of {owned_items, storage_slots, album_masters} hits.
    Used by the operator search box (every screen) and the test
    suite. The largest single search query in the codebase (~270
    lines).

Cross-package dependencies kept on the package surface
  * `_search_token_groups`, `_matches_search_text`,
    `_compact_search_text`, `_build_compact_token_match_sql` — the
    text-token search infrastructure used by half a dozen lookups
    across the package.
  * `_normalize_owned_item_row`, `_storage_slot_display_name`,
    `_parse_label_id_query` — shared row-shape / display helpers.
  * `get_conn` — package surface.

`app/db/__init__.py` re-exports the public function so existing
callers (the operator search box, the test suite) keep working
unchanged.
"""

from __future__ import annotations

import re
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _build_compact_token_match_sql,
    _matches_search_text,
    _normalize_owned_item_row,
    _parse_label_id_query,
    _search_token_groups,
    _storage_slot_display_name,
    get_conn,
)


def search_operator_catalog(query_text: str, limit: int = 30) -> list[dict[str, Any]]:
    clean_query = str(query_text or "").strip()
    if not clean_query:
        return []

    query_norm = clean_query.lower()
    query_like = f"%{query_norm}%"
    query_token_groups = _search_token_groups(clean_query)
    barcode_digits = re.sub(r"[^0-9]", "", clean_query)
    parsed_label_id = _parse_label_id_query(clean_query)
    requested_limit = max(1, int(limit))
    fetch_limit = max(10, min(200, requested_limit * 4))

    base_sql_template = """
      SELECT
        oi.id,
        oi.category,
        oi.item_name_override,
        oi.linked_album_master_id,
        oi.created_at,
        oi.status,
        oi.signature_type,
        oi.domain_code            AS item_domain_code,
        mid.format_name,
        mid.artist_or_brand,
        mid.released_date,
        mid.pressing_country,
        mid.label_name,
        mid.catalog_no,
        mid.barcode,
        mid.runout_matrix_json,
        mid.format_items_json,
        mid.cover_image_url,
        mid.track_list_json,
        mid.track_items_json,
        CASE
          WHEN oi.item_name_override IS NOT NULL
            AND COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) IS NOT NULL
          THEN COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) || ' - ' || oi.item_name_override
          ELSE COALESCE(oi.item_name_override, am.title)
        END AS item_title,
        am.domain_code            AS master_domain_code,
        am.source_domain_code,
        am.override_domain_code,
        am.sort_artist_name       AS master_sort_artist_name,
        ss.slot_code,
        ss.cabinet_name,
        ss.column_code,
        ss.cell_code,
        ss.allowed_size_group,
        ss.is_overflow_zone,
        (
          SELECT e.from_slot_code
          FROM owned_item_location_event e
          WHERE e.owned_item_id = oi.id
            AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
          ORDER BY e.created_at DESC, e.id DESC
          LIMIT 1
        ) AS previous_slot_code,
        (
          SELECT e.from_slot_display_name
          FROM owned_item_location_event e
          WHERE e.owned_item_id = oi.id
            AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
          ORDER BY e.created_at DESC, e.id DESC
          LIMIT 1
        ) AS previous_slot_display_name
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
      LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
      WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
        AND {where_sql}
      ORDER BY
        CASE WHEN oi.status = 'IN_COLLECTION' THEN 0 ELSE 1 END,
        oi.updated_at DESC,
        oi.id DESC
      LIMIT ?
    """

    def _build_items(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            item = _normalize_owned_item_row(dict(row))
            track_matches: list[str] = []
            seen_tracks: set[str] = set()

            def _push_track(value: Any) -> None:
                text = str(value or "").strip()
                if not text or text.lower() in seen_tracks:
                    return
                if not _matches_search_text(text, clean_query, query_token_groups):
                    return
                seen_tracks.add(text.lower())
                track_matches.append(text)

            for track in item.get("track_list") or []:
                _push_track(track)
            for track_item in item.get("track_items") or []:
                if not isinstance(track_item, dict):
                    continue
                _push_track(track_item.get("display"))
                _push_track(track_item.get("title"))

            current_slot_display_name = "미배치"
            if item.get("slot_code"):
                current_slot_display_name = _storage_slot_display_name(
                    {
                        "slot_code": item.get("slot_code"),
                        "cabinet_name": item.get("cabinet_name"),
                        "column_code": item.get("column_code"),
                        "cell_code": item.get("cell_code"),
                        "allowed_size_group": item.get("allowed_size_group"),
                        "is_overflow_zone": item.get("is_overflow_zone"),
                    }
                )

            item["current_slot_code"] = item.get("slot_code")
            item["current_slot_display_name"] = current_slot_display_name
            item["current_cabinet_name"] = str(item.get("cabinet_name") or "").strip() or None
            item["current_column_code"] = str(item.get("column_code") or "").strip() or None
            item["current_cell_code"] = str(item.get("cell_code") or "").strip() or None
            item["previous_slot_code"] = str(item.get("previous_slot_code") or "").strip() or None
            item["previous_slot_display_name"] = str(item.get("previous_slot_display_name") or "").strip() or None
            item["track_matches"] = track_matches[:8]
            item["matched_track_count"] = len(track_matches)
            out.append(item)
        return out

    def _select_candidate_rows(
        conn: sqlite3.Connection,
        where_clauses: list[str],
        params: list[Any],
        *,
        query_limit: int,
        exclude_ids: list[int] | None = None,
    ) -> list[sqlite3.Row]:
        filters = ["(" + " OR ".join(where_clauses) + ")"]
        query_params = list(params)
        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            filters.append(f"oi.id NOT IN ({placeholders})")
            query_params.extend(exclude_ids)
        sql = base_sql_template.format(where_sql=" AND ".join(filters))
        query_params.append(query_limit)
        return conn.execute(sql, query_params).fetchall()

    primary_where_clauses = [
        "LOWER(COALESCE(oi.item_name_override, '')) LIKE ?",
        "LOWER(COALESCE(am.title, '')) LIKE ?",
        "LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?",
        "LOWER(COALESCE(mid.label_name, '')) LIKE ?",
        "LOWER(COALESCE(mid.catalog_no, '')) LIKE ?",
    ]
    primary_params: list[Any] = [query_like, query_like, query_like, query_like, query_like]
    if parsed_label_id is not None:
        category_codes, owned_item_id = parsed_label_id
        category_placeholders = ",".join("?" for _ in category_codes)
        primary_where_clauses.insert(0, f"(oi.id = ? AND UPPER(COALESCE(oi.category, '')) IN ({category_placeholders}))")
        primary_params = [owned_item_id, *category_codes, *primary_params]
    if barcode_digits:
        primary_where_clauses.append("REPLACE(COALESCE(mid.barcode, ''), '-', '') LIKE ?")
        primary_params.append(f"%{barcode_digits}%")
    if query_token_groups:
        token_sql, token_params = _build_compact_token_match_sql(
            """
            COALESCE(oi.item_name_override, '') || ' ' ||
            COALESCE(am.title, '') || ' ' ||
            COALESCE(mid.artist_or_brand, '') || ' ' ||
            COALESCE(mid.label_name, '') || ' ' ||
            COALESCE(mid.catalog_no, '') || ' ' ||
            COALESCE(mid.barcode, '')
            """,
            query_token_groups,
        )
        if token_sql:
            primary_where_clauses.append(token_sql)
            primary_params.extend(token_params)

    fallback_where_clauses = [
        "LOWER(COALESCE(mid.track_list_json, '')) LIKE ?",
        "LOWER(COALESCE(mid.track_items_json, '')) LIKE ?",
        """
        EXISTS (
          SELECT 1
          FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
          WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
        )
        """,
        """
        EXISTS (
          SELECT 1
          FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
          WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
             OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
        )
        """,
    ]
    fallback_params: list[Any] = [query_like, query_like, query_like, query_like, query_like]
    if query_token_groups:
        token_sql, token_params = _build_compact_token_match_sql(
            """
            COALESCE(mid.track_list_json, '') || ' ' ||
            COALESCE(mid.track_items_json, '')
            """,
            query_token_groups,
        )
        if token_sql:
            fallback_where_clauses.append(token_sql)
            fallback_params.extend(token_params)

    with get_conn() as conn:
        primary_rows = _select_candidate_rows(
            conn,
            primary_where_clauses,
            primary_params,
            query_limit=fetch_limit,
        )
        rows = list(primary_rows)
        if len(rows) < requested_limit:
            fallback_rows = _select_candidate_rows(
                conn,
                fallback_where_clauses,
                fallback_params,
                query_limit=max(10, min(200, (requested_limit - len(rows)) * 4)),
                exclude_ids=[int(row["id"]) for row in rows],
            )
            rows.extend(fallback_rows)

    out = _build_items(rows)
    out.sort(
        key=lambda row: (
            0
            if (
                parsed_label_id is not None
                and int(row.get("id") or 0) == parsed_label_id[1]
                and str(row.get("category") or "").upper() in parsed_label_id[0]
            )
            else 1,
            0 if (row.get("matched_track_count") or 0) > 0 else 1,
            0 if str(row.get("status") or "") == "IN_COLLECTION" else 1,
            str(row.get("item_title") or row.get("item_name_override") or "").lower(),
            int(row.get("id") or 0),
        )
    )
    return out[:requested_limit]


# `_build_ops_home_recent_item` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `count_ops_home_recent_moved_items` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_ops_home_recent_moved_items` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `count_ops_home_recent_registered_items` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_ops_home_recent_registered_items` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_ops_home_recent_sections` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_ops_home_feed` lives in app/db/ops_home_recent.py and is
# re-exported from this package's __init__ at the bottom of the file.




__all__ = [
    "search_operator_catalog",
]
