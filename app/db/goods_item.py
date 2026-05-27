"""Goods-item DB surface.

Sixth slice extracted from the legacy `app/db.py`. Owns the
`goods_item` table and its mapping companions
(`goods_item_album_master_map`, `goods_item_artist_map`,
`goods_item_label_map`, `goods_item_collectible_relation`).

Public exports
  * create_goods_item, update_goods_item, get_goods_item, delete_goods_item
  * replace_goods_item_mappings, replace_goods_item_collectible_relations
  * search_goods_collectible_targets
  * count_goods_items, search_goods_items
  * list_goods_artist_name_candidates, list_goods_label_name_candidates

Module-private exports (re-exported from `app.db.__init__` so legacy
schema/migration paths continue to find them by bare name)
  * _goods_category_check_sql, _goods_status_check_sql,
    _goods_relation_type_check_sql
  * _normalize_goods_category_value, _normalize_goods_status_value,
    _normalize_goods_relation_type_value, _normalize_goods_mapping_text
  * _goods_item_select_query, _normalize_goods_item_row
  * _list_goods_item_album_master_mappings_in_conn,
    _list_goods_item_artist_mappings_in_conn,
    _list_goods_item_label_mappings_in_conn,
    _list_goods_item_collectible_relations_in_conn
  * _build_goods_item_with_mappings,
    _replace_goods_item_collectible_relations_in_conn,
    _replace_goods_item_mappings_in_conn
  * _build_goods_search_where

The owned-item ↔ goods migration helpers (`_owned_item_allows_goods`,
`_migrate_owned_item_allow_goods`) and the goods-detail upsert helper
that runs inside `insert_owned_item` / `update_owned_item`
(`_upsert_goods_item_detail_in_conn`) deliberately stay in
`app.db.__init__` because they're owned-item-side concerns that
happen to involve the goods schema.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    GOODS_CATEGORY_CODES,
    GOODS_RELATION_TYPE_CODES,
    GOODS_STATUS_CODES,
    SIZE_GROUP_CODES,
    _compact_search_text,
    _normalize_artist_sort_text,
    _normalize_domain_code_value,
    _storage_slot_display_name,
    get_conn,
    utc_now_iso,
)


def _goods_category_check_sql() -> str:
    return "', '".join(GOODS_CATEGORY_CODES)


def _goods_status_check_sql() -> str:
    return "', '".join(GOODS_STATUS_CODES)


def _goods_relation_type_check_sql() -> str:
    return "', '".join(GOODS_RELATION_TYPE_CODES)


def _normalize_goods_category_value(value: Any) -> str:
    category = str(value or "").strip().upper()
    if category not in GOODS_CATEGORY_CODES:
        raise ValueError("invalid goods category")
    return category


def _normalize_goods_status_value(value: Any) -> str:
    status = str(value or "").strip().upper() or "ACTIVE"
    if status not in GOODS_STATUS_CODES:
        raise ValueError("invalid goods status")
    return status


def _normalize_goods_relation_type_value(value: Any) -> str:
    relation_type = str(value or "").strip().upper()
    if relation_type not in GOODS_RELATION_TYPE_CODES:
        raise ValueError("invalid goods relation_type")
    return relation_type


def _normalize_goods_mapping_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _goods_item_select_query() -> str:
    return """
        SELECT
          gi.*,
          ss.slot_code,
          ss.cabinet_name AS slot_cabinet_name,
          ss.column_code AS slot_column_code,
          ss.cell_code AS slot_cell_code
        FROM goods_item gi
        LEFT JOIN storage_slot ss ON ss.id = gi.storage_slot_id
    """


def _normalize_goods_item_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    image_urls_raw = item.get("image_urls_json")
    try:
        image_urls = json.loads(image_urls_raw) if image_urls_raw not in (None, "") else []
    except json.JSONDecodeError:
        image_urls = []
    if not isinstance(image_urls, list):
        image_urls = []
    item["image_urls"] = [str(url or "").strip() for url in image_urls if str(url or "").strip()]
    slot_display_name = None
    if item.get("storage_slot_id"):
        slot_display_name = _storage_slot_display_name(
            {
                "slot_code": item.get("slot_code"),
                "cabinet_name": item.get("slot_cabinet_name"),
                "column_code": item.get("slot_column_code"),
                "cell_code": item.get("slot_cell_code"),
            }
        )
    item["slot_display_name"] = slot_display_name
    item["quantity"] = int(item.get("quantity") or 0)
    raw_linked = item.get("linked_owned_item_id")
    item["linked_owned_item_id"] = int(raw_linked) if raw_linked is not None else None
    return item


def _list_goods_item_album_master_mappings_in_conn(conn: sqlite3.Connection, goods_item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          gam.album_master_id,
          am.title,
          am.artist_or_brand
        FROM goods_item_album_master_map gam
        JOIN album_master am ON am.id = gam.album_master_id
        WHERE gam.goods_item_id = ?
        ORDER BY LOWER(COALESCE(am.sort_artist_name, am.artist_or_brand, '')) ASC,
                 LOWER(COALESCE(am.title, '')) ASC,
                 am.id ASC
        """,
        (int(goods_item_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_goods_item_artist_mappings_in_conn(conn: sqlite3.Connection, goods_item_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT artist_name
        FROM goods_item_artist_map
        WHERE goods_item_id = ?
        ORDER BY normalized_artist_name ASC, artist_name ASC
        """,
        (int(goods_item_id),),
    ).fetchall()
    return [str(row["artist_name"] or "").strip() for row in rows if str(row["artist_name"] or "").strip()]


def _list_goods_item_label_mappings_in_conn(conn: sqlite3.Connection, goods_item_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT label_name
        FROM goods_item_label_map
        WHERE goods_item_id = ?
        ORDER BY normalized_label_name ASC, label_name ASC
        """,
        (int(goods_item_id),),
    ).fetchall()
    return [str(row["label_name"] or "").strip() for row in rows if str(row["label_name"] or "").strip()]


def _list_goods_item_collectible_relations_in_conn(conn: sqlite3.Connection, goods_item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          gcr.relation_type,
          gcr.linked_goods_item_id,
          gcr.note,
          gcr.display_order,
          gi.goods_name AS linked_goods_name,
          gi.category AS linked_category
        FROM goods_item_collectible_relation gcr
        JOIN goods_item gi ON gi.id = gcr.linked_goods_item_id
        WHERE gcr.goods_item_id = ?
        ORDER BY gcr.display_order ASC, gcr.id ASC
        """,
        (int(goods_item_id),),
    ).fetchall()
    row_dicts = [dict(row) for row in rows]
    return [
        {
            "relation_type": str(row["relation_type"] or "").strip().upper(),
            "direction": "OUTGOING",
            "linked_goods_item_id": int(row["linked_goods_item_id"]),
            "linked_goods_name": str(row.get("linked_goods_name") or "").strip() or f"goods_item_id={int(row['linked_goods_item_id'])}",
            "linked_category": str(row.get("linked_category") or "").strip().upper() or None,
            "note": str(row.get("note") or "").strip() or None,
            "display_order": int(row.get("display_order") or 0),
        }
        for row in row_dicts
    ]


def _build_goods_item_with_mappings(conn: sqlite3.Connection, row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = _normalize_goods_item_row(dict(row))
    goods_item_id = int(item["id"])
    item["album_master_mappings"] = _list_goods_item_album_master_mappings_in_conn(conn, goods_item_id)
    item["artist_mappings"] = _list_goods_item_artist_mappings_in_conn(conn, goods_item_id)
    item["label_mappings"] = _list_goods_item_label_mappings_in_conn(conn, goods_item_id)
    item["collectible_relations"] = _list_goods_item_collectible_relations_in_conn(conn, goods_item_id)
    item["collectible_relation_count"] = len(item["collectible_relations"])
    item["relation_badges"] = [
        relation_type
        for relation_type in dict.fromkeys(
            str(row.get("relation_type") or "").strip().upper()
            for row in item["collectible_relations"]
            if str(row.get("relation_type") or "").strip()
        )
    ]
    item["collectible_relation_preview"] = item["collectible_relations"][:2]
    return item


def _replace_goods_item_collectible_relations_in_conn(
    conn: sqlite3.Connection,
    goods_item_id: int,
    *,
    relations: list[dict[str, Any]],
) -> None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        raise ValueError("goods_item_id must be positive")
    now = utc_now_iso()
    normalized: list[tuple[str, int, str | None, int]] = []
    seen: set[tuple[str, int]] = set()
    linked_ids: set[int] = set()
    for index, row in enumerate(relations):
        relation_type = _normalize_goods_relation_type_value(row.get("relation_type"))
        linked_goods_item_id = int(row.get("linked_goods_item_id") or 0)
        if linked_goods_item_id <= 0:
            continue
        if linked_goods_item_id == item_id:
            raise ValueError("collectible relation cannot target itself")
        key = (relation_type, linked_goods_item_id)
        if key in seen:
            continue
        seen.add(key)
        linked_ids.add(linked_goods_item_id)
        normalized.append(
            (
                relation_type,
                linked_goods_item_id,
                _normalize_goods_mapping_text(row.get("note")) or None,
                int(row.get("display_order") if row.get("display_order") is not None else index),
            )
        )
    if linked_ids:
        placeholders = ", ".join("?" for _ in linked_ids)
        rows = conn.execute(
            f"SELECT id FROM goods_item WHERE id IN ({placeholders})",
            tuple(sorted(linked_ids)),
        ).fetchall()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [target_id for target_id in sorted(linked_ids) if target_id not in found_ids]
        if missing_ids:
            raise ValueError(f"linked goods items not found: {', '.join(str(target_id) for target_id in missing_ids)}")

    conn.execute("DELETE FROM goods_item_collectible_relation WHERE goods_item_id = ?", (item_id,))
    for relation_type, linked_goods_item_id, note, display_order in normalized:
        conn.execute(
            """
            INSERT INTO goods_item_collectible_relation (
              goods_item_id,
              relation_type,
              linked_goods_item_id,
              note,
              display_order,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, relation_type, linked_goods_item_id, note, display_order, now, now),
        )


def _replace_goods_item_mappings_in_conn(
    conn: sqlite3.Connection,
    goods_item_id: int,
    *,
    album_master_ids: list[int],
    artist_names: list[str],
    label_names: list[str],
) -> None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        raise ValueError("goods_item_id must be positive")
    now = utc_now_iso()
    normalized_album_master_ids = sorted({int(mid) for mid in album_master_ids if int(mid or 0) > 0})
    normalized_artist_names = []
    seen_artist_keys: set[str] = set()
    for value in artist_names:
        text = _normalize_goods_mapping_text(value)
        key = _normalize_artist_sort_text(text)
        if not text or not key or key in seen_artist_keys:
            continue
        seen_artist_keys.add(key)
        normalized_artist_names.append((text, key))
    normalized_label_names = []
    seen_label_keys: set[str] = set()
    for value in label_names:
        text = _normalize_goods_mapping_text(value)
        key = _compact_search_text(text)
        if not text or not key or key in seen_label_keys:
            continue
        seen_label_keys.add(key)
        normalized_label_names.append((text, key))

    if normalized_album_master_ids:
        placeholders = ", ".join("?" for _ in normalized_album_master_ids)
        rows = conn.execute(
            f"SELECT id FROM album_master WHERE id IN ({placeholders})",
            tuple(normalized_album_master_ids),
        ).fetchall()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [mid for mid in normalized_album_master_ids if mid not in found_ids]
        if missing_ids:
            raise ValueError(f"album masters not found: {', '.join(str(mid) for mid in missing_ids)}")

    conn.execute("DELETE FROM goods_item_album_master_map WHERE goods_item_id = ?", (item_id,))
    conn.execute("DELETE FROM goods_item_artist_map WHERE goods_item_id = ?", (item_id,))
    conn.execute("DELETE FROM goods_item_label_map WHERE goods_item_id = ?", (item_id,))

    for album_master_id in normalized_album_master_ids:
        conn.execute(
            """
            INSERT INTO goods_item_album_master_map (goods_item_id, album_master_id, created_at)
            VALUES (?, ?, ?)
            """,
            (item_id, album_master_id, now),
        )
    for artist_name, normalized_artist_name in normalized_artist_names:
        conn.execute(
            """
            INSERT INTO goods_item_artist_map (goods_item_id, artist_name, normalized_artist_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, artist_name, normalized_artist_name, now),
        )
    for label_name, normalized_label_name in normalized_label_names:
        conn.execute(
            """
            INSERT INTO goods_item_label_map (goods_item_id, label_name, normalized_label_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, label_name, normalized_label_name, now),
        )


def create_goods_item(payload: dict[str, Any]) -> dict[str, Any]:
    category = _normalize_goods_category_value(payload.get("category"))
    goods_name = _normalize_goods_mapping_text(payload.get("goods_name"))
    if not goods_name:
        raise ValueError("goods_name required")
    quantity = max(1, int(payload.get("quantity") or 1))
    size_group = str(payload.get("size_group") or "GOODS").strip().upper() or "GOODS"
    if size_group not in SIZE_GROUP_CODES:
        raise ValueError("invalid goods size_group")
    status = _normalize_goods_status_value(payload.get("status"))
    domain_code = _normalize_domain_code_value(payload.get("domain_code"))
    description = _normalize_goods_mapping_text(payload.get("description")) or None
    memory_note = _normalize_goods_mapping_text(payload.get("memory_note")) or None
    primary_image_url = str(payload.get("primary_image_url") or "").strip() or None
    image_urls = [str(url or "").strip() for url in payload.get("image_urls") or [] if str(url or "").strip()]
    poster_storage_spec = _normalize_goods_mapping_text(payload.get("poster_storage_spec")) or None
    tshirt_size = _normalize_goods_mapping_text(payload.get("tshirt_size")) or None
    cup_material = _normalize_goods_mapping_text(payload.get("cup_material")) or None
    hat_size = _normalize_goods_mapping_text(payload.get("hat_size")) or None
    storage_slot_id = payload.get("storage_slot_id")
    slot_id_value = int(storage_slot_id) if storage_slot_id not in (None, "") else None
    raw_linked_owned = payload.get("linked_owned_item_id")
    linked_owned_item_id = int(raw_linked_owned) if raw_linked_owned not in (None, "") else None
    now = utc_now_iso()

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO goods_item (
              category, goods_name, description, quantity, size_group, storage_slot_id, status, domain_code,
              memory_note, image_urls_json, primary_image_url, poster_storage_spec, tshirt_size, cup_material,
              hat_size, linked_owned_item_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                goods_name,
                description,
                quantity,
                size_group,
                slot_id_value,
                status,
                domain_code,
                memory_note,
                json.dumps(image_urls, ensure_ascii=True),
                primary_image_url,
                poster_storage_spec,
                tshirt_size,
                cup_material,
                hat_size,
                linked_owned_item_id,
                now,
                now,
            ),
        )
        goods_item_id = int(cur.lastrowid)
        _replace_goods_item_mappings_in_conn(
            conn,
            goods_item_id,
            album_master_ids=[int(mid) for mid in payload.get("album_master_ids") or []],
            artist_names=[str(name or "") for name in payload.get("artist_names") or []],
            label_names=[str(name or "") for name in payload.get("label_names") or []],
        )
        row = conn.execute(f"{_goods_item_select_query()} WHERE gi.id = ?", (goods_item_id,)).fetchone()
        item = _build_goods_item_with_mappings(conn, row)
    if item is None:
        raise RuntimeError("goods item create failed")
    return item


def update_goods_item(goods_item_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        raise ValueError("goods_item_id must be positive")
    assignments: list[str] = []
    params: list[Any] = []
    if "category" in payload:
        assignments.append("category = ?")
        params.append(_normalize_goods_category_value(payload.get("category")))
    if "goods_name" in payload:
        goods_name = _normalize_goods_mapping_text(payload.get("goods_name"))
        if not goods_name:
            raise ValueError("goods_name required")
        assignments.append("goods_name = ?")
        params.append(goods_name)
    if "description" in payload:
        assignments.append("description = ?")
        params.append(_normalize_goods_mapping_text(payload.get("description")) or None)
    if "quantity" in payload:
        assignments.append("quantity = ?")
        params.append(max(1, int(payload.get("quantity") or 1)))
    if "size_group" in payload:
        size_group = str(payload.get("size_group") or "").strip().upper()
        if size_group not in SIZE_GROUP_CODES:
            raise ValueError("invalid goods size_group")
        assignments.append("size_group = ?")
        params.append(size_group)
    if "storage_slot_id" in payload:
        storage_slot_id = payload.get("storage_slot_id")
        assignments.append("storage_slot_id = ?")
        params.append(int(storage_slot_id) if storage_slot_id not in (None, "") else None)
    if "status" in payload:
        assignments.append("status = ?")
        params.append(_normalize_goods_status_value(payload.get("status")))
    if "domain_code" in payload:
        assignments.append("domain_code = ?")
        params.append(_normalize_domain_code_value(payload.get("domain_code")))
    if "memory_note" in payload:
        assignments.append("memory_note = ?")
        params.append(_normalize_goods_mapping_text(payload.get("memory_note")) or None)
    if "image_urls" in payload:
        image_urls = [str(url or "").strip() for url in payload.get("image_urls") or [] if str(url or "").strip()]
        assignments.append("image_urls_json = ?")
        params.append(json.dumps(image_urls, ensure_ascii=True))
    if "primary_image_url" in payload:
        assignments.append("primary_image_url = ?")
        params.append(str(payload.get("primary_image_url") or "").strip() or None)
    if "poster_storage_spec" in payload:
        assignments.append("poster_storage_spec = ?")
        params.append(_normalize_goods_mapping_text(payload.get("poster_storage_spec")) or None)
    if "tshirt_size" in payload:
        assignments.append("tshirt_size = ?")
        params.append(_normalize_goods_mapping_text(payload.get("tshirt_size")) or None)
    if "cup_material" in payload:
        assignments.append("cup_material = ?")
        params.append(_normalize_goods_mapping_text(payload.get("cup_material")) or None)
    if "hat_size" in payload:
        assignments.append("hat_size = ?")
        params.append(_normalize_goods_mapping_text(payload.get("hat_size")) or None)
    if "linked_owned_item_id" in payload:
        raw_linked = payload.get("linked_owned_item_id")
        assignments.append("linked_owned_item_id = ?")
        params.append(int(raw_linked) if raw_linked not in (None, "") else None)
    if not assignments:
        return get_goods_item(item_id)
    params.extend([utc_now_iso(), item_id])
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM goods_item WHERE id = ?", (item_id,)).fetchone()
        if existing is None:
            return None
        conn.execute(
            f"UPDATE goods_item SET {', '.join(assignments)}, updated_at = ? WHERE id = ?",
            tuple(params),
        )
        row = conn.execute(f"{_goods_item_select_query()} WHERE gi.id = ?", (item_id,)).fetchone()
        return _build_goods_item_with_mappings(conn, row)


def get_goods_item(goods_item_id: int) -> dict[str, Any] | None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        return None
    with get_conn() as conn:
        row = conn.execute(f"{_goods_item_select_query()} WHERE gi.id = ?", (item_id,)).fetchone()
        return _build_goods_item_with_mappings(conn, row)


def replace_goods_item_mappings(goods_item_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        raise ValueError("goods_item_id must be positive")
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM goods_item WHERE id = ?", (item_id,)).fetchone()
        if existing is None:
            return None
        _replace_goods_item_mappings_in_conn(
            conn,
            item_id,
            album_master_ids=[int(mid) for mid in payload.get("album_master_ids") or []],
            artist_names=[str(name or "") for name in payload.get("artist_names") or []],
            label_names=[str(name or "") for name in payload.get("label_names") or []],
        )
        row = conn.execute(f"{_goods_item_select_query()} WHERE gi.id = ?", (item_id,)).fetchone()
        return _build_goods_item_with_mappings(conn, row)


def replace_goods_item_collectible_relations(goods_item_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    item_id = int(goods_item_id or 0)
    if item_id <= 0:
        raise ValueError("goods_item_id must be positive")
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM goods_item WHERE id = ?", (item_id,)).fetchone()
        if existing is None:
            return None
        _replace_goods_item_collectible_relations_in_conn(
            conn,
            item_id,
            relations=[dict(row or {}) for row in payload.get("relations") or []],
        )
        row = conn.execute(f"{_goods_item_select_query()} WHERE gi.id = ?", (item_id,)).fetchone()
        return _build_goods_item_with_mappings(conn, row)


def search_goods_collectible_targets(
    *,
    query_text: str | None = None,
    goods_item_id: int | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    query = str(query_text or "").strip()
    exclude_id = int(goods_item_id or 0) if goods_item_id not in (None, "") else 0
    where_sql, params = _build_goods_search_where(query_text=query)
    clauses: list[str] = []
    if where_sql:
        clauses.append(where_sql.replace(" WHERE ", "", 1))
    if exclude_id > 0:
        clauses.append("gi.id <> ?")
        params.append(exclude_id)
    final_where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {_goods_item_select_query()}
            {final_where_sql}
            ORDER BY LOWER(COALESCE(gi.goods_name, '')) ASC, gi.id ASC
            LIMIT ?
            """,
            tuple(params) + (int(limit),),
        ).fetchall()
    return [_normalize_goods_item_row(dict(row)) for row in rows]


def _build_goods_search_where(
    *,
    query_text: str | None = None,
    category: str | None = None,
    status: str | None = None,
    domain_code: str | None = None,
    artist_name: str | None = None,
    album_master_id: int | None = None,
    owned_item_id: int | None = None,
    label_name: str | None = None,
    storage_slot_id: int | None = None,
    linked_state: str = "ANY",
    collectible_relation_state: str = "ANY",
    collectible_relation_type: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    query = str(query_text or "").strip()
    if query:
        clauses.append(
            "("
            "LOWER(COALESCE(gi.goods_name, '')) LIKE ? OR "
            "LOWER(COALESCE(gi.description, '')) LIKE ? OR "
            "LOWER(COALESCE(gi.memory_note, '')) LIKE ?"
            ")"
        )
        like = f"%{query.lower()}%"
        params.extend([like, like, like])
    category_code = str(category or "").strip().upper()
    if category_code:
        clauses.append("gi.category = ?")
        params.append(category_code)
    status_code = str(status or "").strip().upper()
    if status_code:
        clauses.append("gi.status = ?")
        params.append(status_code)
    domain_code_value = str(domain_code or "").strip().upper()
    if domain_code_value:
        clauses.append("gi.domain_code = ?")
        params.append(domain_code_value)
    if storage_slot_id is not None:
        clauses.append("gi.storage_slot_id = ?")
        params.append(int(storage_slot_id))
    if album_master_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM goods_item_album_master_map gam WHERE gam.goods_item_id = gi.id AND gam.album_master_id = ?)"
        )
        params.append(int(album_master_id))
    if owned_item_id is not None:
        clauses.append("gi.linked_owned_item_id = ?")
        params.append(int(owned_item_id))
    normalized_artist = _normalize_artist_sort_text(artist_name)
    if normalized_artist:
        clauses.append(
            "EXISTS (SELECT 1 FROM goods_item_artist_map gam WHERE gam.goods_item_id = gi.id AND gam.normalized_artist_name = ?)"
        )
        params.append(normalized_artist)
    normalized_label = _compact_search_text(label_name)
    if normalized_label:
        clauses.append(
            "EXISTS (SELECT 1 FROM goods_item_label_map glm WHERE glm.goods_item_id = gi.id AND glm.normalized_label_name = ?)"
        )
        params.append(normalized_label)
    linked_state_u = str(linked_state or "ANY").strip().upper() or "ANY"
    if linked_state_u == "LINKED":
        clauses.append(
            "("
            "EXISTS (SELECT 1 FROM goods_item_album_master_map gam WHERE gam.goods_item_id = gi.id) OR "
            "EXISTS (SELECT 1 FROM goods_item_artist_map gim WHERE gim.goods_item_id = gi.id) OR "
            "EXISTS (SELECT 1 FROM goods_item_label_map glm WHERE glm.goods_item_id = gi.id)"
            ")"
        )
    elif linked_state_u == "UNLINKED":
        clauses.append(
            "NOT ("
            "EXISTS (SELECT 1 FROM goods_item_album_master_map gam WHERE gam.goods_item_id = gi.id) OR "
            "EXISTS (SELECT 1 FROM goods_item_artist_map gim WHERE gim.goods_item_id = gi.id) OR "
            "EXISTS (SELECT 1 FROM goods_item_label_map glm WHERE glm.goods_item_id = gi.id)"
            ")"
        )
    relation_state_u = str(collectible_relation_state or "ANY").strip().upper() or "ANY"
    if relation_state_u == "LINKED":
        clauses.append(
            "EXISTS (SELECT 1 FROM goods_item_collectible_relation gcr WHERE gcr.goods_item_id = gi.id)"
        )
    elif relation_state_u == "UNLINKED":
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM goods_item_collectible_relation gcr WHERE gcr.goods_item_id = gi.id)"
        )
    relation_type_value = str(collectible_relation_type or "").strip().upper()
    if relation_type_value:
        clauses.append(
            "EXISTS (SELECT 1 FROM goods_item_collectible_relation gcr WHERE gcr.goods_item_id = gi.id AND gcr.relation_type = ?)"
        )
        params.append(_normalize_goods_relation_type_value(relation_type_value))
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def count_goods_items(
    *,
    query_text: str | None = None,
    category: str | None = None,
    status: str | None = None,
    domain_code: str | None = None,
    artist_name: str | None = None,
    album_master_id: int | None = None,
    owned_item_id: int | None = None,
    label_name: str | None = None,
    storage_slot_id: int | None = None,
    linked_state: str = "ANY",
    collectible_relation_state: str = "ANY",
    collectible_relation_type: str | None = None,
) -> int:
    where_sql, params = _build_goods_search_where(
        query_text=query_text,
        category=category,
        status=status,
        domain_code=domain_code,
        artist_name=artist_name,
        album_master_id=album_master_id,
        owned_item_id=owned_item_id,
        label_name=label_name,
        storage_slot_id=storage_slot_id,
        linked_state=linked_state,
        collectible_relation_state=collectible_relation_state,
        collectible_relation_type=collectible_relation_type,
    )
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM goods_item gi{where_sql}",
            tuple(params),
        ).fetchone()
    return int(row["cnt"] or 0) if row is not None else 0


def search_goods_items(
    *,
    query_text: str | None = None,
    query: str | None = None,
    category: str | None = None,
    status: str | None = None,
    domain_code: str | None = None,
    artist_name: str | None = None,
    album_master_id: int | None = None,
    owned_item_id: int | None = None,
    label_name: str | None = None,
    storage_slot_id: int | None = None,
    linked_state: str = "ANY",
    collectible_relation_state: str = "ANY",
    collectible_relation_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if query is not None:
        query_text = query
    where_sql, params = _build_goods_search_where(
        query_text=query_text,
        category=category,
        status=status,
        domain_code=domain_code,
        artist_name=artist_name,
        album_master_id=album_master_id,
        owned_item_id=owned_item_id,
        label_name=label_name,
        storage_slot_id=storage_slot_id,
        linked_state=linked_state,
        collectible_relation_state=collectible_relation_state,
        collectible_relation_type=collectible_relation_type,
    )
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {_goods_item_select_query()}
            {where_sql}
            ORDER BY LOWER(COALESCE(gi.goods_name, '')) ASC, gi.id ASC
            LIMIT ? OFFSET ?
            """,
            tuple(params) + (int(limit), int(offset)),
        ).fetchall()
        return [_build_goods_item_with_mappings(conn, row) for row in rows if row is not None]


def list_goods_artist_name_candidates(query_text: str, limit: int = 10) -> list[str]:
    query = str(query_text or "").strip().lower()
    if not query:
        return []
    like = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM (
              SELECT DISTINCT TRIM(COALESCE(artist_or_brand, '')) AS name
              FROM album_master
              WHERE TRIM(COALESCE(artist_or_brand, '')) <> ''
              UNION
              SELECT DISTINCT TRIM(COALESCE(linked_artist_name, '')) AS name
              FROM owned_item
              WHERE TRIM(COALESCE(linked_artist_name, '')) <> ''
              UNION
              SELECT DISTINCT TRIM(COALESCE(artist_name, '')) AS name
              FROM goods_item_artist_map
              WHERE TRIM(COALESCE(artist_name, '')) <> ''
            )
            WHERE LOWER(name) LIKE ?
            ORDER BY LOWER(name) ASC
            LIMIT ?
            """,
            (like, int(limit)),
        ).fetchall()
    return [str(row["name"] or "").strip() for row in rows if str(row["name"] or "").strip()]


def list_goods_label_name_candidates(query_text: str, limit: int = 10) -> list[str]:
    query = str(query_text or "").strip().lower()
    if not query:
        return []
    like = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM (
              SELECT DISTINCT TRIM(COALESCE(label_name, '')) AS name
              FROM music_item_detail
              WHERE TRIM(COALESCE(label_name, '')) <> ''
              UNION
              SELECT DISTINCT TRIM(COALESCE(label_name, '')) AS name
              FROM goods_item_label_map
              WHERE TRIM(COALESCE(label_name, '')) <> ''
            )
            WHERE LOWER(name) LIKE ?
            ORDER BY LOWER(name) ASC
            LIMIT ?
            """,
            (like, int(limit)),
        ).fetchall()
    return [str(row["name"] or "").strip() for row in rows if str(row["name"] or "").strip()]


def delete_goods_item(goods_item_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM goods_item WHERE id = ?", (int(goods_item_id),))
    return int(cur.rowcount or 0) > 0




__all__ = [
    "_goods_category_check_sql",
    "_goods_status_check_sql",
    "_goods_relation_type_check_sql",
    "_normalize_goods_category_value",
    "_normalize_goods_status_value",
    "_normalize_goods_relation_type_value",
    "_normalize_goods_mapping_text",
    "_goods_item_select_query",
    "_normalize_goods_item_row",
    "_list_goods_item_album_master_mappings_in_conn",
    "_list_goods_item_artist_mappings_in_conn",
    "_list_goods_item_label_mappings_in_conn",
    "_list_goods_item_collectible_relations_in_conn",
    "_build_goods_item_with_mappings",
    "_replace_goods_item_collectible_relations_in_conn",
    "_replace_goods_item_mappings_in_conn",
    "_build_goods_search_where",
    "create_goods_item",
    "update_goods_item",
    "get_goods_item",
    "replace_goods_item_mappings",
    "replace_goods_item_collectible_relations",
    "search_goods_collectible_targets",
    "count_goods_items",
    "search_goods_items",
    "list_goods_artist_name_candidates",
    "list_goods_label_name_candidates",
    "delete_goods_item",
]
