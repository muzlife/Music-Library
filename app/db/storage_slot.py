"""Storage-slot DB surface.

Fifth slice extracted from the legacy `app/db.py`. Owns the
`storage_slot` table CRUD plus the cabinet-level operations that
register or delete entire cabinets at once. Migration helpers that mutate
the shape of the table also live here.

Public exports
  * get_storage_slot
  * get_storage_slot_by_code
  * list_storage_slots
  * list_owned_items_for_storage_slot
  * upsert_storage_slot
  * register_storage_cabinet_slots
  * delete_storage_cabinet

Module-private exports (re-exported from `app.db.__init__` so the
legacy migration helpers continue to find them by bare name)
  * _derive_storage_slot_parts
  * _storage_slot_allows_goods
  * _migrate_storage_slot_allow_goods
  * _cleanup_overflow_slots

Cross-cutting helpers (`_storage_slot_display_name`, `_natural_sort_key`,
`_contains_any_token`, `_resolve_owned_item_thickness_mm`, the
recommend_* engines, and the owned-item slot/order moves) deliberately
stay in `app.db.__init__` because they're shared with other slices that
have not been extracted yet.

`app/db/__init__.py` re-exports every public symbol so existing
callers (the dashboard router, /storage-slots/* routes, the test suite)
keep working unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Any

from app.db._schema_helpers import _column_exists
from app.db import (  # noqa: E402  — package surface
    DASHBOARD_MOVE_WINDOW_DAYS,
    SIZE_GROUP_CODES,
    _build_label_id,
    _cabinet_sort_policy_check_sql,
    _compose_storage_slot_code,
    _log_owned_item_location_event_in_conn,
    _natural_sort_key,
    _normalize_cabinet_sort_policy_value,
    _normalize_domain_code_sql,
    _normalize_domain_code_value,
    _normalize_owned_item_row,
    _owned_item_select_query,
    _owned_item_storage_sort_key,
    _preferred_korean_artist_by_master_ids,
    _size_group_check_sql,
    _storage_slot_display_name,
    _storage_slot_sort_key,
    get_conn,
    get_write_conn,
    utc_now_iso,
)

# Article-stripping SQL helper (strips leading The/A/An for ORDER BY)
_STRIP_ARTICLE_SQL = (
    "CASE"
    " WHEN LOWER(TRIM({col})) LIKE 'the %' THEN TRIM(SUBSTR(TRIM({col}), 5))"
    " WHEN LOWER(TRIM({col})) LIKE 'an %'  THEN TRIM(SUBSTR(TRIM({col}), 4))"
    " WHEN LOWER(TRIM({col})) LIKE 'a %'   THEN TRIM(SUBSTR(TRIM({col}), 3))"
    " ELSE TRIM({col}) END"
)


def _derive_storage_slot_parts(
    slot_code: str | None,
    allowed_size_group: str | None,
    is_overflow_zone: bool,
) -> tuple[str | None, str | None, str | None]:
    code = str(slot_code or "").strip()
    size_group = str(allowed_size_group or "").strip().upper() or None
    if is_overflow_zone:
        return ("Overflow", size_group or None, "보조")

    if not code:
        return (None, None, None)

    if "/" in code:
        parts = [part.strip() for part in code.split("/") if part.strip()]
        if len(parts) >= 3:
            return (parts[0], parts[1], "/".join(parts[2:]))
        if len(parts) == 2:
            return (parts[0], parts[1], None)

    if code.count("-") >= 2:
        parts = [part.strip() for part in code.split("-") if part.strip()]
        if len(parts) >= 3:
            return ("-".join(parts[:-2]), parts[-2], parts[-1])

    return (code, None, None)


def _storage_slot_allows_goods(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'storage_slot'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "'GOODS'" in table_sql and "'LP10'" in table_sql and "'LP7'" in table_sql and "'CASSETTE'" in table_sql


def _migrate_storage_slot_allow_goods(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'storage_slot'"
    ).fetchone()
    if not row or _storage_slot_allows_goods(conn):
        return

    if conn.in_transaction:
        conn.commit()

    source_has = lambda column: _column_exists(conn, "storage_slot", column)
    now = utc_now_iso()
    cabinet_name_expr = "cabinet_name" if source_has("cabinet_name") else "NULL"
    column_code_expr = "column_code" if source_has("column_code") else "NULL"
    cell_code_expr = "cell_code" if source_has("cell_code") else "NULL"
    sort_policy_expr = "cabinet_sort_policy" if source_has("cabinet_sort_policy") else "'ARTIST_RELEASE_TITLE'"
    cabinet_domain_expr = _normalize_domain_code_sql("cabinet_domain_code") if source_has("cabinet_domain_code") else "NULL"
    max_thickness_expr = "max_thickness_mm" if source_has("max_thickness_mm") else "NULL"
    cabinet_group_name_expr = "cabinet_group_name" if source_has("cabinet_group_name") else "NULL"
    cabinet_group_order_expr = "cabinet_group_order" if source_has("cabinet_group_order") else "NULL"
    is_overflow_expr = "is_overflow_zone" if source_has("is_overflow_zone") else "0"
    created_at_expr = "created_at" if source_has("created_at") else f"'{now}'"
    updated_at_expr = "updated_at" if source_has("updated_at") else f"'{now}'"

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            f"""
            BEGIN;
            DROP TABLE IF EXISTS storage_slot_new;
            CREATE TABLE storage_slot_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slot_code TEXT NOT NULL UNIQUE,
              allowed_size_group TEXT NOT NULL CHECK (allowed_size_group IN ('{_size_group_check_sql()}')),
              cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('{_cabinet_sort_policy_check_sql()}')),
              cabinet_domain_code TEXT CHECK (cabinet_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              max_thickness_mm INTEGER,
              cabinet_group_name TEXT,
              cabinet_group_order INTEGER,
              is_overflow_zone INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              cabinet_name TEXT,
              column_code TEXT,
              cell_code TEXT
            );
            INSERT INTO storage_slot_new
              (
                id, slot_code, allowed_size_group, cabinet_sort_policy, cabinet_domain_code, max_thickness_mm,
                cabinet_group_name, cabinet_group_order, is_overflow_zone, created_at, updated_at,
                cabinet_name, column_code, cell_code
              )
            SELECT
              id, slot_code, allowed_size_group, {sort_policy_expr}, {cabinet_domain_expr}, {max_thickness_expr},
              {cabinet_group_name_expr}, {cabinet_group_order_expr}, {is_overflow_expr}, {created_at_expr}, {updated_at_expr},
              {cabinet_name_expr}, {column_code_expr}, {cell_code_expr}
            FROM storage_slot;
            DROP TABLE storage_slot;
            ALTER TABLE storage_slot_new RENAME TO storage_slot;
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _cleanup_overflow_slots(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    overflow_ids = [
        int(row["id"])
        for row in conn.execute(
            """
            SELECT id
            FROM storage_slot
            WHERE is_overflow_zone = 1
               OR UPPER(TRIM(COALESCE(cabinet_name, ''))) = 'OVERFLOW'
               OR UPPER(TRIM(COALESCE(slot_code, ''))) LIKE 'OVERFLOW-%'
            """
        ).fetchall()
        if row["id"] is not None
    ]
    if not overflow_ids:
        return
    placeholders = ",".join("?" for _ in overflow_ids)
    conn.execute(
        f"""
        UPDATE owned_item
        SET storage_slot_id = NULL,
            updated_at = ?
        WHERE storage_slot_id IN ({placeholders})
        """,
        [now, *overflow_ids],
    )
    conn.execute(
        "DELETE FROM storage_slot WHERE id IN (" + placeholders + ")",
        overflow_ids,
    )


def get_storage_slot(slot_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def get_storage_slot_by_code(slot_code: str) -> dict[str, Any] | None:
    code = str(slot_code or "").strip()
    if not code:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM storage_slot WHERE slot_code = ? LIMIT 1", (code,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def list_storage_slots() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
        """
        SELECT 
          s.id, s.slot_code, s.cabinet_name, s.cabinet_domain_code, s.cabinet_group_name, s.cabinet_group_order, s.column_code, s.cell_code, s.allowed_size_group, s.cabinet_sort_policy, s.max_thickness_mm, s.is_overflow_zone,
          (SELECT COUNT(*) FROM owned_item oi WHERE oi.storage_slot_id = s.id AND oi.status = 'IN_COLLECTION') AS item_count,
          (
            SELECT GROUP_CONCAT(COALESCE(NULLIF(oi.item_name_override,''), am.title, '') || ' (' || COALESCE(oi.linked_artist_name, am.artist_or_brand, '') || ')')
            FROM (
              SELECT oi2.item_name_override, oi2.linked_artist_name, oi2.linked_album_master_id
              FROM owned_item oi2
              WHERE oi2.storage_slot_id = s.id AND oi2.status = 'IN_COLLECTION'
              ORDER BY oi2.display_rank ASC, oi2.id ASC
              LIMIT 3
            ) oi
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
          ) AS stored_items_summary
        FROM storage_slot s
        """
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["display_name"] = _storage_slot_display_name(item)
    items.sort(key=_storage_slot_sort_key)
    return items


def list_owned_items_for_storage_slot(
    storage_slot_id: int,
    limit: int = 300,
    offset: int = 0,
) -> list[dict[str, Any]]:
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    slot = get_storage_slot(storage_slot_id) or {}
    cabinet_sort_policy = _normalize_cabinet_sort_policy_value(slot.get("cabinet_sort_policy"))
    master_release_sort_sql = (
        "COALESCE("
        "NULLIF(TRIM(COALESCE(json_extract(am.raw_json, '$.release_date'), json_extract(am.raw_json, '$.master_release_date'), '')), ''), "
        "CASE WHEN COALESCE(am.release_year, base.release_year) IS NOT NULL "
        "THEN printf('%04d-99-99', COALESCE(am.release_year, base.release_year)) ELSE '' END"
        ")"
    )
    _artist_sort_sql = _STRIP_ARTICLE_SQL.format(
        col="LOWER(COALESCE(am.sort_artist_name, base.artist_or_brand, am.artist_or_brand, base.linked_artist_name, ''))"
    )
    _title_sort_sql = _STRIP_ARTICLE_SQL.format(
        col="LOWER(COALESCE(am.title, base.item_name_override, ''))"
    )
    if cabinet_sort_policy == "LABEL_ID":
        order_by_sql = """
          CASE WHEN base.display_rank IS NULL THEN 1 ELSE 0 END,
          base.display_rank ASC,
          base.id ASC
        """
    elif cabinet_sort_policy == "TITLE_RELEASE":
        order_by_sql = f"""
          CASE WHEN base.display_rank IS NULL THEN 1 ELSE 0 END,
          base.display_rank ASC,
          {_title_sort_sql} ASC,
          CASE WHEN {master_release_sort_sql} = '' THEN 1 ELSE 0 END,
          {master_release_sort_sql} ASC,
          CASE WHEN base.released_date IS NULL OR TRIM(base.released_date) = '' THEN 1 ELSE 0 END,
          TRIM(COALESCE(base.released_date, '')) ASC,
          {_artist_sort_sql} ASC,
          CASE WHEN base.order_key IS NULL OR TRIM(base.order_key) = '' THEN 1 ELSE 0 END,
          base.order_key ASC,
          base.id ASC
        """
    else:
        order_by_sql = f"""
          CASE WHEN base.display_rank IS NULL THEN 1 ELSE 0 END,
          base.display_rank ASC,
          {_artist_sort_sql} ASC,
          CASE WHEN {master_release_sort_sql} = '' THEN 1 ELSE 0 END,
          {master_release_sort_sql} ASC,
          CASE WHEN base.released_date IS NULL OR TRIM(base.released_date) = '' THEN 1 ELSE 0 END,
          TRIM(COALESCE(base.released_date, '')) ASC,
          {_title_sort_sql} ASC,
          CASE WHEN base.order_key IS NULL OR TRIM(base.order_key) = '' THEN 1 ELSE 0 END,
          base.order_key ASC,
          base.id ASC
        """
    query = f"""
        WITH base AS (
{_owned_item_select_query()}
        )
        SELECT
          base.*,
          am.title AS master_title,
          am.artist_or_brand AS master_artist_or_brand,
          am.sort_artist_name AS master_sort_artist_name,
          am.domain_code AS master_domain_code,
          am.release_year AS master_release_year,
          TRIM(COALESCE(json_extract(am.raw_json, '$.release_date'), json_extract(am.raw_json, '$.master_release_date'), '')) AS master_release_date,
          (
            SELECT e.from_slot_code
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
              AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS previous_slot_code,
          (
            SELECT e.from_slot_display_name
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
              AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS previous_slot_display_name,
          (
            SELECT e.created_at
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS last_slot_event_at,
          COALESCE((
            SELECT CASE
              WHEN e.to_storage_slot_id = base.storage_slot_id
               AND e.movement_kind IN ('INITIAL_ASSIGN', 'ASSIGN', 'MOVE')
               AND e.created_at >= ?
              THEN 1 ELSE 0 END
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ), 0) AS recently_moved_to_current_slot
        FROM base
        LEFT JOIN album_master am ON am.id = base.linked_album_master_id
        WHERE base.status = 'IN_COLLECTION'
          AND base.storage_slot_id = ?
        ORDER BY
          {order_by_sql}
        LIMIT ? OFFSET ?
    """
    with get_conn() as conn:
        rows = conn.execute(query, (recent_cutoff, int(storage_slot_id), int(limit), int(offset))).fetchall()
    items = [_normalize_owned_item_row(dict(row)) for row in rows]
    if cabinet_sort_policy == "LABEL_ID":
        items.sort(
            key=lambda row: (
                0 if row.get("display_rank") is not None else 1,
                int(row.get("display_rank") or 0) if row.get("display_rank") is not None else 999999,
                _natural_sort_key(_build_label_id(row.get("category"), int(row.get("id") or 0))),
                int(row.get("id") or 0),
            )
        )
    else:
        korean_artist_by_master_id = _preferred_korean_artist_by_master_ids(
            [int(item.get("linked_album_master_id") or 0) for item in items]
        )
        items.sort(key=lambda row: _owned_item_storage_sort_key(row, korean_artist_by_master_id, cabinet_sort_policy))
    return items


def upsert_storage_slot(
    cabinet_name: str,
    column_code: str | None,
    cell_code: str | None,
    allowed_size_group: str,
    cabinet_domain_code: str | None = None,
    cabinet_sort_policy: str | None = None,
    max_thickness_mm: int | None = None,
    is_overflow_zone: bool = False,
    slot_id: int | None = None,
) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")
    column = str(column_code or "").strip() or None
    cell = str(cell_code or "").strip() or None
    size_group = str(allowed_size_group or "").strip().upper()
    if size_group not in SIZE_GROUP_CODES:
        raise ValueError("invalid allowed_size_group")
    domain_code = _normalize_domain_code_value(cabinet_domain_code)
    sort_policy = _normalize_cabinet_sort_policy_value(cabinet_sort_policy)
    capacity_override = int(max_thickness_mm or 0) if max_thickness_mm not in (None, "") else 0
    if capacity_override < 0:
        raise ValueError("invalid max_thickness_mm")
    capacity_override_value = capacity_override or None
    overflow = bool(is_overflow_zone)
    slot_code = _compose_storage_slot_code(cabinet, column, cell, size_group, overflow)
    now = utc_now_iso()

    with get_conn() as conn:
        if slot_id is not None:
            existing = conn.execute("SELECT id, cabinet_sort_policy, cabinet_domain_code, max_thickness_mm FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
            if existing is None:
                raise ValueError("storage_slot not found")
            dup = conn.execute("SELECT id FROM storage_slot WHERE slot_code = ? AND id <> ?", (slot_code, slot_id)).fetchone()
            if dup is not None:
                raise ValueError("duplicate storage_slot code")
            if cabinet_sort_policy is None:
                sort_policy = _normalize_cabinet_sort_policy_value(existing["cabinet_sort_policy"])
            if cabinet_domain_code is None:
                domain_code = _normalize_domain_code_value(existing["cabinet_domain_code"])
            if max_thickness_mm is None:
                capacity_override_value = existing["max_thickness_mm"]
            conn.execute(
                """
                UPDATE storage_slot
                SET slot_code = ?, cabinet_name = ?, column_code = ?, cell_code = ?,
                    allowed_size_group = ?, cabinet_sort_policy = ?, cabinet_domain_code = ?, max_thickness_mm = ?, is_overflow_zone = ?, updated_at = ?
                WHERE id = ?
                """,
                (slot_code, cabinet, column, cell, size_group, sort_policy, domain_code, capacity_override_value, int(overflow), now, slot_id),
            )
            row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
        else:
            existing = conn.execute("SELECT id, cabinet_sort_policy, cabinet_domain_code, max_thickness_mm FROM storage_slot WHERE slot_code = ?", (slot_code,)).fetchone()
            if existing is not None:
                if cabinet_sort_policy is None:
                    sort_policy = _normalize_cabinet_sort_policy_value(existing["cabinet_sort_policy"])
                if cabinet_domain_code is None:
                    domain_code = _normalize_domain_code_value(existing["cabinet_domain_code"])
                if max_thickness_mm is None:
                    capacity_override_value = existing["max_thickness_mm"]
                conn.execute(
                    """
                    UPDATE storage_slot
                    SET cabinet_name = ?, column_code = ?, cell_code = ?,
                        allowed_size_group = ?, cabinet_sort_policy = ?, cabinet_domain_code = ?, max_thickness_mm = ?, is_overflow_zone = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (cabinet, column, cell, size_group, sort_policy, domain_code, capacity_override_value, int(overflow), now, int(existing["id"])),
                )
                row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (int(existing["id"]),)).fetchone()
            else:
                cur = conn.execute(
                    """
                    INSERT INTO storage_slot
                      (slot_code, cabinet_name, column_code, cell_code, allowed_size_group, cabinet_sort_policy, cabinet_domain_code, max_thickness_mm, is_overflow_zone, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slot_code, cabinet, column, cell, size_group, sort_policy, domain_code, capacity_override_value, int(overflow), now, now),
                )
                row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (int(cur.lastrowid),)).fetchone()

    if row is None:
        raise ValueError("storage_slot save failed")
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def register_storage_cabinet_slots(
    cabinet_name: str,
    floor_count: int,
    cell_count: int,
    allowed_size_group: str,
    cabinet_domain_code: str | None = None,
    cabinet_sort_policy: str | None = None,
    max_thickness_mm: int | None = None,
    floor_start: int = 1,
    cell_start: int = 1,
    cabinet_group_name: str | None = None,
    cabinet_group_order: int | None = None,
) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")
    group_name = str(cabinet_group_name or "").strip() or None
    group_order = int(cabinet_group_order or 0) if cabinet_group_order not in (None, "") else 0
    if group_order < 0:
        raise ValueError("invalid cabinet_group_order")
    group_order_value = group_order or None

    floors = int(floor_count or 0)
    cells = int(cell_count or 0)
    floor_begin = int(floor_start or 0)
    cell_begin = int(cell_start or 0)
    if floors <= 0 or cells <= 0:
        raise ValueError("floor_count and cell_count must be positive")
    if floor_begin <= 0 or cell_begin <= 0:
        raise ValueError("floor_start and cell_start must be positive")

    size_group = str(allowed_size_group or "").strip().upper()
    if size_group not in SIZE_GROUP_CODES:
        raise ValueError("invalid allowed_size_group")
    domain_code = _normalize_domain_code_value(cabinet_domain_code)
    sort_policy = _normalize_cabinet_sort_policy_value(cabinet_sort_policy)
    capacity_override = int(max_thickness_mm or 0) if max_thickness_mm not in (None, "") else 0
    if capacity_override < 0:
        raise ValueError("invalid max_thickness_mm")
    capacity_override_value = capacity_override or None

    max_floor = floor_begin + floors - 1
    max_cell = cell_begin + cells - 1
    floor_width = max(2, len(str(max_floor)))
    cell_width = max(2, len(str(max_cell)))

    created_count = 0
    updated_count = 0
    now = utc_now_iso()

    # Inserts up to floors * cells slot rows. Wrap as IMMEDIATE so we don't
    # half-register a cabinet under contention.
    with get_write_conn() as conn:
        for floor_no in range(floor_begin, floor_begin + floors):
            floor_code = str(floor_no).zfill(floor_width)
            for cell_no in range(cell_begin, cell_begin + cells):
                cell_code = str(cell_no).zfill(cell_width)
                slot_code = _compose_storage_slot_code(cabinet, floor_code, cell_code, size_group, False)
                existing = conn.execute(
                    "SELECT id FROM storage_slot WHERE slot_code = ?",
                    (slot_code,),
                ).fetchone()
                if existing is not None:
                    conn.execute(
                        """
                        UPDATE storage_slot
                        SET cabinet_name = ?, column_code = ?, cell_code = ?,
                            allowed_size_group = ?, cabinet_sort_policy = ?, cabinet_domain_code = ?, max_thickness_mm = ?, cabinet_group_name = ?, cabinet_group_order = ?, is_overflow_zone = 0, updated_at = ?
                        WHERE id = ?
                        """,
                        (cabinet, floor_code, cell_code, size_group, sort_policy, domain_code, capacity_override_value, group_name, group_order_value, now, int(existing["id"])),
                    )
                    updated_count += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO storage_slot
                          (slot_code, cabinet_name, column_code, cell_code, allowed_size_group, cabinet_sort_policy, cabinet_domain_code, max_thickness_mm, cabinet_group_name, cabinet_group_order, is_overflow_zone, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (slot_code, cabinet, floor_code, cell_code, size_group, sort_policy, domain_code, capacity_override_value, group_name, group_order_value, now, now),
                    )
                    created_count += 1

        conn.execute(
            """
            UPDATE storage_slot
            SET cabinet_domain_code = ?,
                updated_at = ?
            WHERE cabinet_name = ?
              AND is_overflow_zone = 0
            """,
            (domain_code, now, cabinet),
        )

        total_slot_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM storage_slot
            WHERE is_overflow_zone = 0
              AND cabinet_name = ?
            """,
            (cabinet,),
        ).fetchone()

    return {
        "cabinet_name": cabinet,
        "cabinet_domain_code": domain_code,
        "cabinet_group_name": group_name,
        "cabinet_group_order": group_order_value,
        "floor_count": floors,
        "cell_count": cells,
        "cabinet_sort_policy": sort_policy,
        "max_thickness_mm": capacity_override,
        "created_count": created_count,
        "updated_count": updated_count,
        "total_slot_count": int(total_slot_row["cnt"] or 0) if total_slot_row is not None else 0,
    }


def delete_storage_cabinet(cabinet_name: str) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")

    # Cabinet delete clears slot assignments on every owned_item in the
    # cabinet, drops the slot rows, and writes location events for each.
    # IMMEDIATE prevents a concurrent slot reassignment from leaking.
    with get_write_conn() as conn:
        slot_rows = conn.execute(
            """
            SELECT id
            FROM storage_slot
            WHERE cabinet_name = ?
              AND is_overflow_zone = 0
            """,
            (cabinet,),
        ).fetchall()
        slot_ids = [int(row["id"]) for row in slot_rows if row["id"] is not None]
        if not slot_ids:
            raise ValueError("storage_cabinet not found")

        placeholders = ",".join("?" for _ in slot_ids)
        item_rows = conn.execute(
            f"""
            SELECT id, storage_slot_id
            FROM owned_item
            WHERE storage_slot_id IN ({placeholders})
            """,
            slot_ids,
        ).fetchall()
        unassigned_item_count = len(item_rows)
        now = utc_now_iso()

        conn.execute(
            f"""
            UPDATE owned_item
            SET storage_slot_id = NULL, updated_at = ?
            WHERE storage_slot_id IN ({placeholders})
            """,
            (now, *slot_ids),
        )
        for row in item_rows:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=int(row["id"]),
                from_storage_slot_id=int(row["storage_slot_id"]) if row["storage_slot_id"] is not None else None,
                to_storage_slot_id=None,
                movement_kind="CABINET_DELETE",
                note=cabinet,
                now=now,
            )
        cur = conn.execute(
            f"DELETE FROM storage_slot WHERE id IN ({placeholders})",
            slot_ids,
        )

    return {
        "cabinet_name": cabinet,
        "deleted_slot_count": int(cur.rowcount or 0),
        "unassigned_item_count": unassigned_item_count,
    }




__all__ = [
    "_derive_storage_slot_parts",
    "_storage_slot_allows_goods",
    "_migrate_storage_slot_allow_goods",
    "_cleanup_overflow_slots",
    "get_storage_slot",
    "get_storage_slot_by_code",
    "list_storage_slots",
    "list_owned_items_for_storage_slot",
    "upsert_storage_slot",
    "register_storage_cabinet_slots",
    "delete_storage_cabinet",
]
