"""Owned-item / barcode location recommendation DB surface.

Eighteenth slice extracted from the legacy `app/db.py`. Owns the
"이 음반을 어디에 꽂아야 할까?" engine — the algorithm that ranks
storage_slots for a given (size_group, artist, year, format) tuple
and returns the recommended slot id plus a few alternatives.

Public exports
  * recommend_owned_item_location — the core ranker. Takes the
    incoming item's profile (size_group required, plus optional
    artist / year / domain / title / thickness / format / package
    hints) and returns
    `{anchor_owned_item_id, anchor_position, recommended_storage_slot_id,
     slot_code, candidate_slots[], reason, used_fallback_slot}`.
    Used by the new-item form preview and the barcode-lookup
    suggestion panel.
  * recommend_barcode_candidate_locations — the barcode-lookup wrapper.
    Calls recommend_owned_item_location for the canonical anchor pick,
    then assembles a top-N (default 3) slot list ranked by
    domain match → free-thickness margin → cabinet/column sort key.

Cross-package dependencies kept on the package surface
  Many helpers are cross-cutting (used by other still-in-__init__.py
  writers / readers) and stay in `app/db/__init__.py`. The submodule
  pulls them via the package surface:
    * SIZE_GROUP_CODES (constant)
    * build_storage_slot_occupancy_summary (public)
    * _backfill_order_keys, _compact_search_sql_expr,
      _normalize_domain_code_value, _normalize_master_release_sort_text,
      _normalize_recommendation_text, _normalize_released_date_sort_text,
      _resolve_owned_item_thickness_mm, _storage_slot_display_name,
      _storage_slot_sort_key, _title_first_group_artist_key

`app/db/__init__.py` re-exports both public functions so existing
callers (`/owned-items/...` routes, the barcode-recommendation
endpoint, the new-item form preview, the test suite) keep working
unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    SIZE_GROUP_CODES,
    _backfill_order_keys,
    _compact_search_sql_expr,
    _normalize_domain_code_value,
    _normalize_master_release_sort_text,
    _normalize_recommendation_text,
    _normalize_released_date_sort_text,
    _resolve_owned_item_thickness_mm,
    _storage_slot_display_name,
    _storage_slot_sort_key,
    _title_first_group_artist_key,
    build_storage_slot_occupancy_summary,
    get_conn,
)


def recommend_owned_item_location(
    size_group: str,
    artist_or_brand: str | None,
    release_year: int | None,
    released_date: str | None = None,
    domain_code: str | None = None,
    item_title: str | None = None,
    exclude_owned_item_id: int | None = None,
    incoming_thickness_mm: int | None = None,
    incoming_format_name: str | None = None,
    incoming_package_hint: str | None = None,
) -> dict[str, Any]:
    size = str(size_group or "").strip().upper()
    if size not in SIZE_GROUP_CODES:
        return {
            "anchor_owned_item_id": None,
            "anchor_position": None,
            "recommended_storage_slot_id": None,
            "slot_code": None,
            "candidate_slots": [],
            "reason": "INVALID_SIZE_GROUP",
            "used_fallback_slot": False,
        }

    artist_norm = _normalize_recommendation_text(artist_or_brand)
    title_norm = _normalize_recommendation_text(item_title)
    try:
        year_value = int(release_year) if release_year is not None else None
    except (TypeError, ValueError):
        year_value = None
    released_date_value = _normalize_released_date_sort_text(released_date)
    exclude_id = int(exclude_owned_item_id or 0)
    requested_domain_code = _normalize_domain_code_value(domain_code)
    incoming_has_context = any(
        value not in (None, "")
        for value in (incoming_thickness_mm, incoming_format_name, incoming_package_hint)
    )
    required_thickness_mm = (
        _resolve_owned_item_thickness_mm(
            thickness_mm=incoming_thickness_mm,
            size_group=size,
            format_name=incoming_format_name,
            package_hint=incoming_package_hint,
        )
        if incoming_has_context
        else None
    )

    anchor_row: sqlite3.Row | None = None
    anchor_position: str | None = None
    anchor_reason = "NO_ANCHOR"
    preferred_slot_id = 0
    recommended_slot_id: int | None = None
    recommended_slot_code: str | None = None
    slot_reason = "NO_SLOT"
    candidate_slots: list[dict[str, Any]] = []

    def _recommendation_sort_key(row: sqlite3.Row | dict[str, Any]) -> tuple[Any, ...]:
        raw_year = row["release_year"] if isinstance(row, sqlite3.Row) else row.get("release_year")
        try:
            row_year = int(raw_year) if raw_year is not None else None
        except (TypeError, ValueError):
            row_year = None
        master_release_sort_value = _normalize_master_release_sort_text(
            row["master_release_date"] if isinstance(row, sqlite3.Row) else row.get("master_release_date"),
            row_year,
        )
        row_released_date = _normalize_released_date_sort_text(
            row["released_date"] if isinstance(row, sqlite3.Row) else row.get("released_date")
        )
        row_title_norm = _normalize_recommendation_text(
            row["item_title"] if isinstance(row, sqlite3.Row) else row.get("item_title")
        )
        if _title_first_group_artist_key(artist_norm):
            return (
                row_title_norm,
                master_release_sort_value,
                1 if not row_released_date else 0,
                row_released_date or "9999-99-99",
            )
        return (
            master_release_sort_value,
            1 if not row_released_date else 0,
            row_released_date or "9999-99-99",
            row_title_norm,
        )

    with get_conn() as conn:
        _backfill_order_keys(conn)
        exclude_sql = " AND oi.id <> ? " if exclude_id > 0 else " "
        exclude_params = [exclude_id] if exclude_id > 0 else []
        slot_rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, cabinet_domain_code, cabinet_group_name, cabinet_group_order, column_code, cell_code, allowed_size_group
            FROM storage_slot
            WHERE allowed_size_group = ?
              AND cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
            """,
            (size,),
        ).fetchall()
        slot_item_rows = conn.execute(
            """
            SELECT
              oi.storage_slot_id,
              oi.size_group,
              oi.thickness_mm,
              oi.notes,
              oi.item_name_override,
              mid.format_name,
              mid.disc_count,
              mid.format_items_json
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.status = 'IN_COLLECTION'
              AND ss.allowed_size_group = ?
              AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
            """,
            (size,),
        ).fetchall()
        slot_item_map: dict[int, list[dict[str, Any]]] = {}
        for row in slot_item_rows:
            storage_slot_id = int(row["storage_slot_id"] or 0)
            if storage_slot_id <= 0:
                continue
            slot_item_map.setdefault(storage_slot_id, []).append(dict(row))
        slot_occupancy_map: dict[int, dict[str, Any]] = {
            int(row["id"]): build_storage_slot_occupancy_summary(dict(row), slot_item_map.get(int(row["id"]), []))
            for row in slot_rows
            if row["id"] is not None
        }
        slot_domain_map: dict[int, str | None] = {
            int(row["id"]): _normalize_domain_code_value(row["cabinet_domain_code"])
            for row in slot_rows
            if row["id"] is not None
        }

        def _slot_domain_rank(slot_id: int | None) -> int:
            if not requested_domain_code:
                return 0
            safe_slot_id = int(slot_id or 0)
            slot_domain_code = slot_domain_map.get(safe_slot_id)
            if slot_domain_code == requested_domain_code:
                return 0
            if slot_domain_code is None:
                return 1
            return 2

        def _slot_has_capacity(slot_id: int | None) -> bool:
            if required_thickness_mm is None:
                return True
            safe_slot_id = int(slot_id or 0)
            if safe_slot_id <= 0:
                return False
            summary = slot_occupancy_map.get(safe_slot_id)
            if summary is None:
                return False
            return int(summary.get("free_thickness_mm") or 0) >= int(required_thickness_mm)

        available_slot_ids = [
            int(row["id"] or 0)
            for row in slot_rows
            if int(row["id"] or 0) > 0 and _slot_has_capacity(int(row["id"] or 0))
        ]
        allowed_domain_rank = min((_slot_domain_rank(slot_id) for slot_id in available_slot_ids), default=0)

        def _slot_matches_domain(slot_id: int | None) -> bool:
            return _slot_domain_rank(slot_id) == allowed_domain_rank

        artist_rows: list[sqlite3.Row] = []
        if artist_norm:
            artist_rows = conn.execute(
                f"""
                SELECT
                  oi.id,
                  oi.order_key,
                  oi.storage_slot_id,
                  ss.slot_code,
                  ss.cabinet_name,
                  ss.column_code,
                  ss.cell_code,
                  COALESCE(am.release_year, mid.release_year) AS release_year,
                  TRIM(COALESCE(json_extract(am.raw_json, '$.release_date'), json_extract(am.raw_json, '$.master_release_date'), '')) AS master_release_date,
                  mid.released_date AS released_date,
                  CASE
                    WHEN oi.item_name_override IS NOT NULL
                      AND COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) IS NOT NULL
                    THEN COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) || ' - ' || oi.item_name_override
                    ELSE COALESCE(oi.item_name_override, am.title, '')
                  END AS item_title
                FROM owned_item oi
                JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  AND {_compact_search_sql_expr("COALESCE(am.sort_artist_name, oi.linked_artist_name, mid.artist_or_brand, am.artist_or_brand, '')")} = ?
                  {exclude_sql}
                """,
                [size, artist_norm, *exclude_params],
            ).fetchall()
            artist_rows = sorted(
                artist_rows,
                key=lambda row: (
                    *_recommendation_sort_key(row),
                    str(row["order_key"] or "").strip(),
                    int(row["id"] or 0),
                ),
            )
        incoming_sort_key = _recommendation_sort_key(
            {
                "release_year": year_value,
                "released_date": released_date_value,
                "item_title": item_title,
            }
        )

        candidate_slot_map: dict[int, dict[str, Any]] = {}
        for row in artist_rows:
            slot_id = int(row["storage_slot_id"] or 0)
            if slot_id <= 0 or slot_id in candidate_slot_map:
                continue
            slot_code = str(row["slot_code"] or "").strip()
            cabinet_name = str(row["cabinet_name"] or "").strip()
            column_code = str(row["column_code"] or "").strip()
            cell_code = str(row["cell_code"] or "").strip()
            display_name = " / ".join(
                [
                    value
                    for value in (
                        cabinet_name,
                        f"{column_code}열" if column_code else "",
                        f"{cell_code}칸" if cell_code else "",
                    )
                    if value
                ]
            ) or slot_code
            candidate_slot_map[slot_id] = {
                "storage_slot_id": slot_id,
                "slot_code": slot_code or None,
                "cabinet_name": cabinet_name or None,
                "column_code": column_code or None,
                "cell_code": cell_code or None,
                "display_name": display_name or None,
            }
        candidate_slots = list(candidate_slot_map.values())
        if required_thickness_mm is not None:
            candidate_slots = [
                slot for slot in candidate_slots
                if _slot_has_capacity(int(slot.get("storage_slot_id") or 0))
                and _slot_matches_domain(int(slot.get("storage_slot_id") or 0))
            ]

        def _boundary_tail_anchor(
            rows: list[sqlite3.Row],
            *,
            newer_index: int,
            boundary_reason: str,
        ) -> tuple[sqlite3.Row | None, str | None, str | None]:
            if newer_index <= 0 or newer_index >= len(rows):
                return None, None, None
            newer_row = rows[newer_index]
            previous_row = rows[newer_index - 1]
            try:
                newer_slot_id = int(newer_row["storage_slot_id"] or 0)
                previous_slot_id = int(previous_row["storage_slot_id"] or 0)
            except (TypeError, ValueError):
                return None, None, None
            if newer_slot_id <= 0 or previous_slot_id <= 0 or newer_slot_id == previous_slot_id:
                return None, None, None
            return previous_row, "AFTER", boundary_reason

        def _previous_row_anchor(
            rows: list[sqlite3.Row],
            *,
            newer_index: int,
            reason: str,
        ) -> tuple[sqlite3.Row | None, str | None, str | None]:
            if newer_index <= 0 or newer_index >= len(rows):
                return None, None, None
            previous_row = rows[newer_index - 1]
            try:
                previous_slot_id = int(previous_row["storage_slot_id"] or 0)
            except (TypeError, ValueError):
                return None, None, None
            if previous_slot_id <= 0:
                return None, None, None
            return previous_row, "AFTER", reason

        if artist_rows:
            if _title_first_group_artist_key(artist_norm):
                newer_row: sqlite3.Row | None = None
                newer_row_index = -1
                for index, row in enumerate(artist_rows):
                    if _recommendation_sort_key(row) > incoming_sort_key:
                        newer_row = row
                        newer_row_index = index
                        break
                if newer_row is not None:
                    boundary_anchor_row, boundary_anchor_position, boundary_anchor_reason = _boundary_tail_anchor(
                        artist_rows,
                        newer_index=newer_row_index,
                        boundary_reason="SAME_GROUP_BOUNDARY_TAIL",
                    )
                    if boundary_anchor_row is not None:
                        anchor_row = boundary_anchor_row
                        anchor_position = boundary_anchor_position
                        anchor_reason = boundary_anchor_reason
                    else:
                        previous_anchor_row, previous_anchor_position, previous_anchor_reason = _previous_row_anchor(
                            artist_rows,
                            newer_index=newer_row_index,
                            reason="SAME_GROUP_PREVIOUS",
                        )
                        if previous_anchor_row is not None:
                            anchor_row = previous_anchor_row
                            anchor_position = previous_anchor_position
                            anchor_reason = previous_anchor_reason
                        else:
                            anchor_row = newer_row
                            anchor_position = "BEFORE"
                            anchor_reason = "SAME_GROUP_TITLE"
                else:
                    anchor_row = artist_rows[-1]
                    anchor_position = "AFTER"
                    anchor_reason = "SAME_GROUP_TAIL"
            elif year_value is not None or released_date_value:
                newer_row = None
                newer_row_index = -1
                for index, row in enumerate(artist_rows):
                    if _recommendation_sort_key(row) > incoming_sort_key:
                        newer_row = row
                        newer_row_index = index
                        break
                if newer_row is not None:
                    boundary_anchor_row, boundary_anchor_position, boundary_anchor_reason = _boundary_tail_anchor(
                        artist_rows,
                        newer_index=newer_row_index,
                        boundary_reason="SAME_ARTIST_BOUNDARY_TAIL",
                    )
                    if boundary_anchor_row is not None:
                        anchor_row = boundary_anchor_row
                        anchor_position = boundary_anchor_position
                        anchor_reason = boundary_anchor_reason
                    else:
                        previous_anchor_row, previous_anchor_position, previous_anchor_reason = _previous_row_anchor(
                            artist_rows,
                            newer_index=newer_row_index,
                            reason="SAME_ARTIST_PREVIOUS",
                        )
                        if previous_anchor_row is not None:
                            anchor_row = previous_anchor_row
                            anchor_position = previous_anchor_position
                            anchor_reason = previous_anchor_reason
                        else:
                            anchor_row = newer_row
                            anchor_position = "BEFORE"
                            anchor_reason = "SAME_ARTIST_YEAR_TITLE"
                else:
                    anchor_row = artist_rows[-1]
                    anchor_position = "AFTER"
                    anchor_reason = "SAME_ARTIST_TAIL"
            else:
                anchor_row = artist_rows[-1]
                anchor_position = "AFTER"
                anchor_reason = "SAME_ARTIST_TAIL"

        if anchor_row is None:
            fallback_row = conn.execute(
                f"""
                SELECT oi.id, oi.order_key, oi.storage_slot_id
                FROM owned_item oi
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  {exclude_sql}
                ORDER BY oi.order_key DESC, oi.id DESC
                LIMIT 1
                """,
                [size, *exclude_params],
            ).fetchone()
            if fallback_row is not None:
                anchor_row = fallback_row
                anchor_position = "AFTER"
                anchor_reason = "FALLBACK_COLLECTION_TAIL"

        if anchor_row is not None and anchor_row["storage_slot_id"] is not None:
            try:
                preferred_slot_id = int(anchor_row["storage_slot_id"])
            except (TypeError, ValueError):
                preferred_slot_id = 0

        if preferred_slot_id > 0:
            slot_row = conn.execute(
                """
                SELECT id, slot_code
                FROM storage_slot
                WHERE id = ?
                  AND allowed_size_group = ?
                LIMIT 1
                """,
                (preferred_slot_id, size),
            ).fetchone()
            if slot_row is not None and _slot_has_capacity(int(slot_row["id"] or 0)) and _slot_matches_domain(int(slot_row["id"] or 0)):
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "ANCHOR_SLOT"

        if recommended_slot_id is None and artist_norm:
            slot_rows = conn.execute(
                f"""
                SELECT
                  ss.id,
                  ss.slot_code,
                  ss.cabinet_name,
                  ss.cabinet_group_name,
                  ss.cabinet_group_order,
                  ss.column_code,
                  ss.cell_code,
                  ss.is_overflow_zone,
                  COUNT(*) AS cnt
                FROM owned_item oi
                JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  AND {_compact_search_sql_expr("COALESCE(am.sort_artist_name, oi.linked_artist_name, mid.artist_or_brand, am.artist_or_brand, '')")} = ?
                  AND ss.allowed_size_group = ?
                  {exclude_sql}
                GROUP BY ss.id, ss.slot_code, ss.cabinet_name, ss.cabinet_group_name, ss.cabinet_group_order, ss.column_code, ss.cell_code, ss.is_overflow_zone
                """,
                [artist_norm, size, *exclude_params],
            ).fetchall()
            slot_rows = sorted(
                slot_rows,
                key=lambda row: (
                    -int(row["cnt"] or 0),
                    bool(row["is_overflow_zone"]),
                    _storage_slot_sort_key(dict(row)),
                ),
            )
            slot_row = next(
                (
                    row for row in slot_rows
                    if _slot_has_capacity(int(row["id"] or 0))
                    and _slot_matches_domain(int(row["id"] or 0))
                ),
                None,
            )
            if slot_row is not None:
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "ARTIST_SLOT"

        if recommended_slot_id is None:
            slot_rows = conn.execute(
                """
                SELECT
                  ss.id,
                  ss.slot_code,
                  ss.cabinet_name,
                  ss.cabinet_group_name,
                  ss.cabinet_group_order,
                  ss.column_code,
                  ss.cell_code,
                  ss.is_overflow_zone,
                  COUNT(oi.id) AS usage_count
                FROM storage_slot ss
                LEFT JOIN owned_item oi
                  ON oi.storage_slot_id = ss.id
                 AND oi.status = 'IN_COLLECTION'
                WHERE ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                GROUP BY ss.id, ss.slot_code, ss.cabinet_name, ss.cabinet_group_name, ss.cabinet_group_order, ss.column_code, ss.cell_code, ss.is_overflow_zone
                """,
                (size,),
            ).fetchall()
            slot_rows = sorted(
                slot_rows,
                key=lambda row: (
                    bool(row["is_overflow_zone"]),
                    int(row["usage_count"] or 0),
                    _storage_slot_sort_key(dict(row)),
                ),
            )
            slot_row = next(
                (
                    row for row in slot_rows
                    if _slot_has_capacity(int(row["id"] or 0))
                    and _slot_matches_domain(int(row["id"] or 0))
                ),
                None,
            )
            if slot_row is not None:
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "LEAST_OCCUPIED_SLOT"

    if recommended_slot_id is not None and requested_domain_code:
        resolved_domain_code = slot_domain_map.get(int(recommended_slot_id))
        if resolved_domain_code == requested_domain_code:
            slot_reason = "DOMAIN_SLOT"

    used_fallback_slot = slot_reason in {"ARTIST_SLOT", "LEAST_OCCUPIED_SLOT"}
    if slot_reason == "ANCHOR_SLOT":
        used_fallback_slot = False
    if recommended_slot_id is None:
        used_fallback_slot = False

    return {
        "anchor_owned_item_id": int(anchor_row["id"]) if anchor_row is not None else None,
        "anchor_position": anchor_position,
        "recommended_storage_slot_id": recommended_slot_id,
        "slot_code": recommended_slot_code,
        "candidate_slots": candidate_slots,
        "reason": f"{anchor_reason}/{slot_reason}",
        "used_fallback_slot": used_fallback_slot,
    }


def _fetch_anchor_display(conn: sqlite3.Connection, owned_item_id: int | None) -> str | None:
    """Return 'Artist - Title (Year)' for the anchor item, or None."""
    if not owned_item_id:
        return None
    row = conn.execute(
        """
        SELECT
          COALESCE(oi.item_name_override, am.title, '') AS item_title,
          COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name, '') AS artist,
          COALESCE(am.release_year, mid.release_year) AS release_year
        FROM owned_item oi
        LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
        LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
        WHERE oi.id = ?
        """,
        (owned_item_id,),
    ).fetchone()
    if not row:
        return None
    item_title = str(row["item_title"] or "").strip()
    if not item_title:
        return None
    artist = str(row["artist"] or "").strip()
    try:
        year = int(row["release_year"]) if row["release_year"] is not None else None
    except (TypeError, ValueError):
        year = None
    display = f"{artist} - {item_title}" if artist else item_title
    if year and year > 0:
        display = f"{display} ({year})"
    return display


def _fetch_slot_anchor(
    conn: sqlite3.Connection,
    slot_id: int,
    artist_norm: str | None,
) -> tuple[int | None, str | None]:
    """Return (owned_item_id, 'AFTER') for the tail item in a slot.
    Prefers an artist-matched tail; falls back to the absolute last item."""
    if artist_norm:
        row = conn.execute(
            f"""
            SELECT oi.id FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.storage_slot_id = ?
              AND {_compact_search_sql_expr("COALESCE(am.sort_artist_name, oi.linked_artist_name, mid.artist_or_brand, am.artist_or_brand, '')")} = ?
            ORDER BY oi.order_key DESC, oi.id DESC
            LIMIT 1
            """,
            [slot_id, artist_norm],
        ).fetchone()
        if row:
            return int(row["id"]), "AFTER"
    row = conn.execute(
        """
        SELECT oi.id FROM owned_item oi
        WHERE oi.status = 'IN_COLLECTION'
          AND oi.storage_slot_id = ?
        ORDER BY oi.order_key DESC, oi.id DESC
        LIMIT 1
        """,
        [slot_id],
    ).fetchone()
    if row:
        return int(row["id"]), "AFTER"
    return None, None


def recommend_barcode_candidate_locations(
    *,
    category: str,
    size_group: str | None,
    domain_code: str | None = None,
    format_name: str | None,
    artist_or_brand: str | None,
    title: str | None,
    release_year: int | None,
    thickness_mm: int | None,
    package_hint: str | None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    category_code = str(category or "").strip().upper()
    fallback_size_group = (
        "LP"
        if category_code == "LP"
        else "CASSETTE"
        if category_code == "CASSETTE"
        else "GOODS"
        if category_code in {"T_SHIRT", "POSTER", "LIGHT_STICK", "HAT", "BAG", "CUP", "OTHER"}
        else "STD"
    )
    size = str(size_group or "").strip().upper() or fallback_size_group
    if size not in SIZE_GROUP_CODES:
        return []

    safe_limit = max(1, min(int(limit or 3), 3))
    required_thickness_mm = _resolve_owned_item_thickness_mm(
        thickness_mm=thickness_mm,
        size_group=size,
        format_name=format_name,
        package_hint=package_hint,
    )
    suggestion = recommend_owned_item_location(
        size_group=size,
        artist_or_brand=artist_or_brand,
        release_year=release_year,
        domain_code=domain_code,
        item_title=title,
        incoming_thickness_mm=required_thickness_mm,
    )

    with get_conn() as conn:
        slot_rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, cabinet_domain_code, cabinet_group_name, cabinet_group_order, column_code, cell_code, allowed_size_group, is_overflow_zone
            FROM storage_slot
            WHERE allowed_size_group = ?
              AND cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
            """,
            (size,),
        ).fetchall()
        slot_item_rows = conn.execute(
            """
            SELECT
              oi.storage_slot_id,
              oi.size_group,
              oi.thickness_mm,
              oi.notes,
              oi.item_name_override,
              mid.format_name,
              mid.disc_count,
              mid.format_items_json
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.status = 'IN_COLLECTION'
              AND ss.allowed_size_group = ?
              AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
            """,
            (size,),
        ).fetchall()

    slot_item_map: dict[int, list[dict[str, Any]]] = {}
    for row in slot_item_rows:
        storage_slot_id = int(row["storage_slot_id"] or 0)
        if storage_slot_id <= 0:
            continue
        slot_item_map.setdefault(storage_slot_id, []).append(dict(row))

    ranked_slots: list[dict[str, Any]] = []
    requested_domain_code = _normalize_domain_code_value(domain_code)
    for row in slot_rows:
        item = dict(row)
        slot_id = int(item.get("id") or 0)
        if slot_id <= 0:
            continue
        summary = build_storage_slot_occupancy_summary(item, slot_item_map.get(slot_id, []))
        if int(summary.get("free_thickness_mm") or 0) < required_thickness_mm:
            continue
        ranked_slots.append(
            {
                "storage_slot_id": slot_id,
                "slot_code": str(item.get("slot_code") or "").strip(),
                "cabinet_name": str(item.get("cabinet_name") or "").strip() or None,
                "column_code": str(item.get("column_code") or "").strip() or None,
                "cell_code": str(item.get("cell_code") or "").strip() or None,
                "slot_display_name": _storage_slot_display_name(item),
                "free_thickness_mm": int(summary.get("free_thickness_mm") or 0),
                "used_thickness_mm": int(summary.get("used_thickness_mm") or 0),
                "capacity_mm": int(summary.get("capacity_mm") or 0),
                "occupancy_percent": int(summary.get("occupancy_percent") or 0),
                "is_overflow_zone": bool(item.get("is_overflow_zone")),
                "cabinet_domain_code": _normalize_domain_code_value(item.get("cabinet_domain_code")),
                "_sort_key": (
                    0 if _normalize_domain_code_value(item.get("cabinet_domain_code")) == requested_domain_code else 1 if not _normalize_domain_code_value(item.get("cabinet_domain_code")) else 2,
                    max(int(summary.get("free_thickness_mm") or 0) - required_thickness_mm, 0),
                    _storage_slot_sort_key(item),
                ),
            }
        )

    ranked_slots.sort(key=lambda row: (bool(row.get("is_overflow_zone")), *row["_sort_key"]))

    preferred_slot_id = int(suggestion.get("recommended_storage_slot_id") or 0)
    result: list[dict[str, Any]] = []
    seen_slot_ids: set[int] = set()

    if preferred_slot_id > 0:
        preferred_row = next((row for row in ranked_slots if int(row["storage_slot_id"]) == preferred_slot_id), None)
        if preferred_row is not None:
            seen_slot_ids.add(preferred_slot_id)
            result.append(preferred_row)

    for row in ranked_slots:
        slot_id = int(row["storage_slot_id"])
        if slot_id in seen_slot_ids:
            continue
        seen_slot_ids.add(slot_id)
        result.append(row)
        if len(result) >= safe_limit:
            break

    artist_norm = _normalize_recommendation_text(artist_or_brand)
    anchor_map: dict[int, dict[str, Any]] = {}
    with get_conn() as conn:
        for row in result[:safe_limit]:
            slot_id = int(row["storage_slot_id"])
            if slot_id == preferred_slot_id:
                a_id = suggestion.get("anchor_owned_item_id")
                a_pos = suggestion.get("anchor_position")
                a_reason = suggestion.get("reason")
            else:
                a_id, a_pos = _fetch_slot_anchor(conn, slot_id, artist_norm)
                a_reason = None
            a_display = _fetch_anchor_display(conn, a_id)
            anchor_map[slot_id] = {
                "anchor_owned_item_id": int(a_id) if a_id else None,
                "anchor_position": a_pos,
                "anchor_display": a_display,
                "reason": a_reason,
            }

    return [
        {
            "rank": index,
            "storage_slot_id": int(row["storage_slot_id"]),
            "slot_code": str(row["slot_code"]),
            "cabinet_name": row.get("cabinet_name"),
            "column_code": row.get("column_code"),
            "cell_code": row.get("cell_code"),
            "slot_display_name": str(row["slot_display_name"]),
            "free_thickness_mm": int(row["free_thickness_mm"]),
            "used_thickness_mm": int(row["used_thickness_mm"]),
            "capacity_mm": int(row["capacity_mm"]),
            "occupancy_percent": int(row["occupancy_percent"]),
            **anchor_map.get(int(row["storage_slot_id"]), {
                "anchor_owned_item_id": None,
                "anchor_position": None,
                "anchor_display": None,
                "reason": None,
            }),
        }
        for index, row in enumerate(result[:safe_limit], start=1)
    ]


__all__ = [
    "recommend_owned_item_location",
    "recommend_barcode_candidate_locations",
]
