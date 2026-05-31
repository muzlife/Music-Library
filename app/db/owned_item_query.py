"""Owned-item list / count / get-list-row query surface.

Twenty-eighth slice extracted from the legacy `app/db.py`. Owns the
operator-facing list view query — the heavy filter/sort engine used
by the collection-dashboard grid, the search box, and the multi-
edit modal's pre-flight count.

Public exports
  * list_owned_items — paged read with many filter axes (source,
    artist/title/year, category, status, slot, classification,
    copy_group, etc.). Returns the row shape produced by
    `_owned_item_select_query` + `_normalize_owned_item_row`.
  * count_owned_items — same WHERE/JOIN as list, just COUNT(*) for
    the grid pagination header.
  * get_owned_item_list_row — single-row variant of list with the
    same shape, used by the operator detail screen's
    "이 항목의 list 행" widget.

Cross-package dependencies kept on the package surface
  * `_owned_item_select_query`, `_normalize_owned_item_row` —
    cross-cutting helpers that 5+ submodules pull via the package
    surface; they stay in `app/db/__init__.py`.
  * `get_album_master_binding_for_owned_item`,
    `get_album_master_domain_hint` — album_master_read (Phase 20).
  * `list_owned_items_by_album_master` — album_master_read.
  * `list_owned_items_by_copy_group`,
    `list_owned_items_by_source_external_ids` —
    owned_item_copy_group (Phase 22).

Re-export ordering invariant
  owned_item_query MUST be re-exported AFTER album_master_read AND
  owned_item_copy_group. Both are loaded earlier in the bottom-of-
  file import block.

`app/db/__init__.py` re-exports every public symbol so existing
callers (`/owned-items/...` list/count routes, the operator
collection grid, the test suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_owned_item_row,
    _owned_item_select_query,
    get_album_master_binding_for_owned_item,
    get_album_master_domain_hint,
    get_conn,
    list_owned_items_by_album_master,
    list_owned_items_by_copy_group,
    list_owned_items_by_source_external_ids,
)


def list_owned_items(
    category: str | None,
    domain_code: str | None,
    release_type: str | None,
    status: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    source_state: str,
    master_state: str,
    cover_state: str,
    slot_state: str,
    preferred_storage_state: str,
    track_state: str,
    music_only: bool,
    sort: str,
    limit: int,
    offset: int,
    media_format_state: str = "ANY",
    size_group_state: str = "ANY",
) -> list[dict[str, Any]]:
    query = _owned_item_select_query() + " WHERE 1 = 1"
    params: list[Any] = []
    query += " AND (oi.source_code IS NULL OR oi.source_code != 'MUSICBRAINZ')"

    if category:
        query += " AND oi.category = ?"
        params.append(category)
    elif music_only:
        query += " AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"

    if domain_code:
        query += " AND oi.domain_code = ?"
        params.append(domain_code)

    if release_type:
        query += " AND oi.release_type = ?"
        params.append(release_type)

    if status:
        query += " AND oi.status = ?"
        params.append(status)

    if q and q.strip():
        q_norm = f"%{q.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
           OR LOWER(COALESCE(oi.purchase_source, '')) LIKE ?
           OR LOWER(COALESCE(oi.memory_note, '')) LIKE ?
         )
        """
        params.extend([q_norm, q_norm, q_norm])

    if artist_or_brand and artist_or_brand.strip():
        v = f"%{artist_or_brand.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
           OR LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
         )
        """
        params.extend([v, v])

    if item_name and item_name.strip():
        query += " AND LOWER(COALESCE(oi.item_name_override, '')) LIKE ?"
        params.append(f"%{item_name.strip().lower()}%")

    if catalog_no and catalog_no.strip():
        query += " AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?"
        params.append(f"%{catalog_no.strip().lower()}%")

    if barcode and barcode.strip():
        normalized = "".join(ch for ch in str(barcode).strip() if ch.isalnum()).lower()
        if normalized:
            query += " AND LOWER(REPLACE(REPLACE(COALESCE(mid.barcode, ''), '-', ''), ' ', '')) LIKE ?"
            params.append(f"%{normalized}%")

    if release_year is not None:
        query += " AND mid.release_year = ?"
        params.append(int(release_year))

    source_state_u = str(source_state or "ANY").strip().upper()
    if source_state_u == "MISSING":
        query += """
         AND (
           oi.source_code IS NULL OR TRIM(oi.source_code) = ''
           OR oi.source_external_id IS NULL OR TRIM(oi.source_external_id) = ''
         )
        """
    elif source_state_u == "LINKED":
        query += """
         AND (
           oi.source_code IS NOT NULL AND TRIM(oi.source_code) <> ''
           AND oi.source_external_id IS NOT NULL AND TRIM(oi.source_external_id) <> ''
         )
        """

    master_state_u = str(master_state or "ANY").strip().upper()
    if master_state_u == "MISSING":
        query += " AND oi.linked_album_master_id IS NULL"
    elif master_state_u == "LINKED":
        query += " AND oi.linked_album_master_id IS NOT NULL"

    cover_state_u = str(cover_state or "ANY").strip().upper()
    if cover_state_u == "MISSING":
        query += " AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')"
    elif cover_state_u == "HAS":
        query += " AND (mid.cover_image_url IS NOT NULL AND TRIM(mid.cover_image_url) <> '')"

    slot_state_u = str(slot_state or "ANY").strip().upper()
    if slot_state_u == "UNSLOTTED":
        query += " AND oi.storage_slot_id IS NULL"
    elif slot_state_u == "SLOTTED":
        query += " AND oi.storage_slot_id IS NOT NULL"

    preferred_storage_state_u = str(preferred_storage_state or "ANY").strip().upper()
    if preferred_storage_state_u == "MISMATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) <> UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """
    elif preferred_storage_state_u == "MATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) = UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """

    track_state_u = str(track_state or "ANY").strip().upper()
    if track_state_u == "MISSING":
        query += """
         AND (
           mid.track_items_json IS NULL OR TRIM(mid.track_items_json) = '' OR TRIM(mid.track_items_json) = '[]'
         )
         AND (
           mid.track_list_json IS NULL OR TRIM(mid.track_list_json) = '' OR TRIM(mid.track_list_json) = '[]'
         )
        """

    media_format_state_u = str(media_format_state or "ANY").strip().upper()
    if media_format_state_u == "MISSING":
        query += " AND (mid.media_type IS NULL OR TRIM(mid.media_type) = '')"
    elif media_format_state_u == "HAS":
        query += " AND (mid.media_type IS NOT NULL AND TRIM(mid.media_type) <> '')"

    size_group_state_u = str(size_group_state or "ANY").strip().upper()
    if size_group_state_u == "MISMATCH":
        query += (" AND ((mid.media_type IN ('Vinyl', 'LP', '10\"', '7\"', 'Box Set', 'All Media') AND COALESCE(oi.size_group, '') NOT IN ('LP', 'LP10', 'LP7'))"
                  " OR (mid.media_type IN ('CD', 'CDr', 'SACD', 'Digital') AND COALESCE(oi.size_group, '') != 'STD')"
                  " OR (mid.media_type IN ('Cassette', '8-Track Cartridge') AND COALESCE(oi.size_group, '') != 'CASSETTE')"
                  " OR (1=0)"
                  " OR (mid.media_type = 'Reel-To-Reel' AND COALESCE(oi.size_group, '') != 'REEL_TO_REEL'))")
    elif size_group_state_u == "MATCH":
        query += (" AND ((mid.media_type IN ('Vinyl', 'LP', '10\"', '7\"', 'Box Set', 'All Media') AND COALESCE(oi.size_group, '') IN ('LP', 'LP10', 'LP7'))"
                  " OR (mid.media_type IN ('CD', 'CDr', 'SACD', 'Digital') AND COALESCE(oi.size_group, '') = 'STD')"
                  " OR (mid.media_type IN ('Cassette', '8-Track Cartridge') AND COALESCE(oi.size_group, '') = 'CASSETTE')"
                  " OR (1=0)"
                  " OR (mid.media_type = 'Reel-To-Reel' AND COALESCE(oi.size_group, '') = 'REEL_TO_REEL'))")
    elif track_state_u == "HAS":
        query += """
         AND (
           (mid.track_items_json IS NOT NULL AND TRIM(mid.track_items_json) <> '' AND TRIM(mid.track_items_json) <> '[]')
           OR (mid.track_list_json IS NOT NULL AND TRIM(mid.track_list_json) <> '' AND TRIM(mid.track_list_json) <> '[]')
         )
        """

    if str(sort or "").upper() == "RECENT":
        query += """
          ORDER BY oi.created_at DESC, oi.id DESC
          LIMIT ? OFFSET ?
        """
    else:
        query += """
          ORDER BY
            CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
            oi.order_key ASC,
            CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
            oi.display_rank ASC,
            oi.created_at DESC,
            oi.id DESC
          LIMIT ? OFFSET ?
        """
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_normalize_owned_item_row(dict(row)) for row in rows]


def count_owned_items(
    category: str | None,
    domain_code: str | None,
    release_type: str | None,
    status: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    source_state: str,
    master_state: str,
    cover_state: str,
    slot_state: str,
    preferred_storage_state: str,
    track_state: str,
    music_only: bool,
    media_format_state: str = "ANY",
    size_group_state: str = "ANY",
) -> int:
    query = """
      SELECT COUNT(*) AS cnt
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      WHERE 1 = 1
    """
    params: list[Any] = []
    query += " AND (oi.source_code IS NULL OR oi.source_code != 'MUSICBRAINZ')"

    if category:
        query += " AND oi.category = ?"
        params.append(category)
    elif music_only:
        query += " AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"

    if domain_code:
        query += " AND oi.domain_code = ?"
        params.append(domain_code)

    if release_type:
        query += " AND oi.release_type = ?"
        params.append(release_type)

    if status:
        query += " AND oi.status = ?"
        params.append(status)

    if q and q.strip():
        q_norm = f"%{q.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
           OR LOWER(COALESCE(oi.purchase_source, '')) LIKE ?
           OR LOWER(COALESCE(oi.memory_note, '')) LIKE ?
         )
        """
        params.extend([q_norm, q_norm, q_norm])

    if artist_or_brand and artist_or_brand.strip():
        v = f"%{artist_or_brand.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
           OR LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
         )
        """
        params.extend([v, v])

    if item_name and item_name.strip():
        query += " AND LOWER(COALESCE(oi.item_name_override, '')) LIKE ?"
        params.append(f"%{item_name.strip().lower()}%")

    if catalog_no and catalog_no.strip():
        query += " AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?"
        params.append(f"%{catalog_no.strip().lower()}%")

    if barcode and barcode.strip():
        normalized = "".join(ch for ch in str(barcode).strip() if ch.isalnum()).lower()
        if normalized:
            query += " AND LOWER(REPLACE(REPLACE(COALESCE(mid.barcode, ''), '-', ''), ' ', '')) LIKE ?"
            params.append(f"%{normalized}%")

    if release_year is not None:
        query += " AND mid.release_year = ?"
        params.append(int(release_year))

    source_state_u = str(source_state or "ANY").strip().upper()
    if source_state_u == "MISSING":
        query += """
         AND (
           oi.source_code IS NULL OR TRIM(oi.source_code) = ''
           OR oi.source_external_id IS NULL OR TRIM(oi.source_external_id) = ''
         )
        """
    elif source_state_u == "LINKED":
        query += """
         AND (
           oi.source_code IS NOT NULL AND TRIM(oi.source_code) <> ''
           AND oi.source_external_id IS NOT NULL AND TRIM(oi.source_external_id) <> ''
         )
        """

    master_state_u = str(master_state or "ANY").strip().upper()
    if master_state_u == "MISSING":
        query += " AND oi.linked_album_master_id IS NULL"
    elif master_state_u == "LINKED":
        query += " AND oi.linked_album_master_id IS NOT NULL"

    cover_state_u = str(cover_state or "ANY").strip().upper()
    if cover_state_u == "MISSING":
        query += " AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')"
    elif cover_state_u == "HAS":
        query += " AND (mid.cover_image_url IS NOT NULL AND TRIM(mid.cover_image_url) <> '')"

    slot_state_u = str(slot_state or "ANY").strip().upper()
    if slot_state_u == "UNSLOTTED":
        query += " AND oi.storage_slot_id IS NULL"
    elif slot_state_u == "SLOTTED":
        query += " AND oi.storage_slot_id IS NOT NULL"

    preferred_storage_state_u = str(preferred_storage_state or "ANY").strip().upper()
    if preferred_storage_state_u == "MISMATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) <> UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """
    elif preferred_storage_state_u == "MATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) = UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """

    track_state_u = str(track_state or "ANY").strip().upper()
    if track_state_u == "MISSING":
        query += """
         AND (
           mid.track_items_json IS NULL OR TRIM(mid.track_items_json) = '' OR TRIM(mid.track_items_json) = '[]'
         )
         AND (
           mid.track_list_json IS NULL OR TRIM(mid.track_list_json) = '' OR TRIM(mid.track_list_json) = '[]'
         )
        """

    media_format_state_u = str(media_format_state or "ANY").strip().upper()
    if media_format_state_u == "MISSING":
        query += " AND (mid.media_type IS NULL OR TRIM(mid.media_type) = '')"
    elif media_format_state_u == "HAS":
        query += " AND (mid.media_type IS NOT NULL AND TRIM(mid.media_type) <> '')"

    size_group_state_u = str(size_group_state or "ANY").strip().upper()
    if size_group_state_u == "MISMATCH":
        query += (" AND ((mid.media_type IN ('Vinyl', 'LP', '10\"', '7\"', 'Box Set', 'All Media') AND COALESCE(oi.size_group, '') NOT IN ('LP', 'LP10', 'LP7'))"
                  " OR (mid.media_type IN ('CD', 'CDr', 'SACD', 'Digital') AND COALESCE(oi.size_group, '') != 'STD')"
                  " OR (mid.media_type IN ('Cassette', '8-Track Cartridge') AND COALESCE(oi.size_group, '') != 'CASSETTE')"
                  " OR (1=0)"
                  " OR (mid.media_type = 'Reel-To-Reel' AND COALESCE(oi.size_group, '') != 'REEL_TO_REEL'))")
    elif size_group_state_u == "MATCH":
        query += (" AND ((mid.media_type IN ('Vinyl', 'LP', '10\"', '7\"', 'Box Set', 'All Media') AND COALESCE(oi.size_group, '') IN ('LP', 'LP10', 'LP7'))"
                  " OR (mid.media_type IN ('CD', 'CDr', 'SACD', 'Digital') AND COALESCE(oi.size_group, '') = 'STD')"
                  " OR (mid.media_type IN ('Cassette', '8-Track Cartridge') AND COALESCE(oi.size_group, '') = 'CASSETTE')"
                  " OR (1=0)"
                  " OR (mid.media_type = 'Reel-To-Reel' AND COALESCE(oi.size_group, '') = 'REEL_TO_REEL'))")
    elif track_state_u == "HAS":
        query += """
         AND (
           (mid.track_items_json IS NOT NULL AND TRIM(mid.track_items_json) <> '' AND TRIM(mid.track_items_json) <> '[]')
           OR (mid.track_list_json IS NOT NULL AND TRIM(mid.track_list_json) <> '' AND TRIM(mid.track_list_json) <> '[]')
         )
        """

    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return int((row["cnt"] if row else 0) or 0)


def get_owned_item_list_row(owned_item_id: int) -> dict[str, Any] | None:
    query = _owned_item_select_query() + " WHERE oi.id = ? LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(query, (owned_item_id,)).fetchone()
    if row is None:
        return None
    return _normalize_owned_item_row(dict(row))


# `get_album_master_binding_for_owned_item` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_album_master_domain_hint` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_owned_items_by_album_master` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_owned_items_by_copy_group` lives in app/db/owned_item_copy_group.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_owned_items_by_source_external_ids` lives in app/db/owned_item_copy_group.py and is
# re-exported from this package's __init__ at the bottom of the file.


__all__ = [
    "list_owned_items",
    "count_owned_items",
    "get_owned_item_list_row",
]
