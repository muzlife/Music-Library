"""Owned-item write surface — insert / update / bulk_update / delete.

Twenty-seventh slice extracted from the legacy `app/db.py`. Owns
the heart of the operator owned-item write path:

  * insert_owned_item — single-row INSERT for a brand-new
    owned_item plus its music_item_detail / goods_item_detail
    sub-rows, classification (subtype/soundtrack) sync, and an
    optional storage_slot move + location_event log.
  * _sync_owned_item_classifications_in_conn — module-private
    helper that replaces an item's subtype/soundtrack tags inside
    one connection. Shared with update_owned_item below.
  * update_owned_item — single-row UPDATE, including optional
    storage_slot move + location_event log + classification sync.
  * bulk_update_owned_items — UPDATE many owned_items in one
    transaction (operator multi-edit).
  * delete_owned_item — single-row DELETE.

Cross-package dependencies kept on the package surface
  Many cross-cutting helpers stay in `app/db/__init__.py` because
  they are also used by other still-in-__init__.py paths:
  `_owned_item_select_query`, `_normalize_owned_item_row`,
  `_upsert_music_item_detail_in_conn`,
  `_upsert_goods_item_detail_in_conn`, `_backfill_order_keys`,
  `_next_order_key_in_conn`. The submodule pulls them via the
  package surface.

  Other dependencies live in OTHER submodules and are also pulled
  via the package surface:
    `_log_owned_item_location_event_in_conn` (owned_item_slot, Phase 23)
    `_sync_album_master_domain_code_in_conn` (album_master_core, Phase 19)
    `set_owned_item_copy_group` (owned_item_copy_group, Phase 22)
    `get_owned_item_location_snapshot` (owned_item_track, Phase 25)

Re-export ordering invariant
  owned_item_write MUST be re-exported AFTER all of those
  dependent modules. The natural place is at the very END of the
  bottom-of-file re-export block.

`app/db/__init__.py` re-exports every public symbol so existing
callers (`/owned-items/...` write routes, the operator detail
form, the bulk-edit modal, the test suite) keep working unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _backfill_order_keys,
    _log_owned_item_location_event_in_conn,
    _next_order_key_in_conn,
    _normalize_owned_item_row,
    _owned_item_select_query,
    _sync_album_master_domain_code_in_conn,
    _upsert_goods_item_detail_in_conn,
    _upsert_music_item_detail_in_conn,
    get_conn,
    get_owned_item_location_snapshot,
    get_write_conn,
    set_owned_item_copy_group,
    utc_now_iso,
)


def insert_owned_item(payload: dict[str, Any]) -> int:
    now = utc_now_iso()
    status = str(payload.get("status") or "IN_COLLECTION")
    order_key = payload.get("order_key")
    initial_storage_slot_id = payload.get("storage_slot_id")
    with get_conn() as conn:
        if status == "IN_COLLECTION":
            if not str(order_key or "").strip():
                _backfill_order_keys(conn)
                order_key = _next_order_key_in_conn(conn)
            else:
                order_key = str(order_key).strip()
        else:
            order_key = None

        cur = conn.execute(
            """
            INSERT INTO owned_item (
              master_item_id, linked_album_master_id, linked_artist_name, copy_group_key, category, domain_code, release_type, item_name_override, quantity, is_second_hand, size_group, preferred_storage_size_group, status,
              condition_grade, signature_type, source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank, order_key,
              storage_slot_id, thickness_mm, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("master_item_id"),
                payload.get("linked_album_master_id"),
                payload.get("linked_artist_name"),
                payload.get("copy_group_key"),
                payload["category"],
                payload.get("domain_code"),
                payload.get("release_type"),
                payload.get("item_name_override"),
                payload["quantity"],
                1 if payload.get("is_second_hand") else 0,
                payload["size_group"],
                payload.get("preferred_storage_size_group") or payload["size_group"],
                payload.get("status", "IN_COLLECTION"),
                payload.get("condition_grade"),
                payload.get("signature_type", "NONE"),
                payload.get("source_code"),
                payload.get("source_external_id"),
                payload.get("signed_by"),
                payload.get("signed_at"),
                payload.get("acquisition_date"),
                payload.get("purchase_price"),
                payload.get("currency_code"),
                payload.get("purchase_source"),
                payload.get("memory_note"),
                payload.get("display_rank"),
                order_key,
                payload.get("storage_slot_id"),
                payload.get("thickness_mm"),
                payload.get("notes"),
                now,
                now,
            ),
        )
        owned_item_id = int(cur.lastrowid)

        _sync_owned_item_classifications_in_conn(
            conn,
            owned_item_id=owned_item_id,
            subtype_option_ids=payload.get("subtype_option_ids") or [],
            soundtrack_option_ids=payload.get("soundtrack_option_ids") or [],
            now=now,
        )

        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        goods_detail = payload.get("goods_detail")
        if goods_detail:
            _upsert_goods_item_detail_in_conn(conn, owned_item_id=owned_item_id, goods_detail=goods_detail, now=now)

        if initial_storage_slot_id is not None:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=None,
                to_storage_slot_id=int(initial_storage_slot_id),
                now=now,
                is_create=True,
            )

    return owned_item_id


def _sync_owned_item_classifications_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    subtype_option_ids: list[int],
    soundtrack_option_ids: list[int],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    conn.execute("DELETE FROM owned_item_subtype WHERE owned_item_id = ?", (owned_item_id,))
    conn.execute("DELETE FROM owned_item_soundtrack WHERE owned_item_id = ?", (owned_item_id,))

    def _valid_option_ids(option_group: str, ids: list[int]) -> list[int]:
        unique_ids = sorted({int(v) for v in ids if int(v) > 0})
        if not unique_ids:
            return []
        placeholders = ",".join("?" for _ in unique_ids)
        rows = conn.execute(
            f"""
            SELECT id
            FROM classification_option
            WHERE option_group = ?
              AND id IN ({placeholders})
            """,
            [option_group, *unique_ids],
        ).fetchall()
        return [int(row["id"]) for row in rows]

    valid_subtypes = _valid_option_ids("SUBTYPE", subtype_option_ids)
    valid_soundtracks = _valid_option_ids("SOUNDTRACK", soundtrack_option_ids)

    if valid_subtypes:
        conn.executemany(
            """
            INSERT OR IGNORE INTO owned_item_subtype
              (owned_item_id, option_id, created_at)
            VALUES (?, ?, ?)
            """,
            [(owned_item_id, option_id, timestamp) for option_id in valid_subtypes],
        )
    if valid_soundtracks:
        conn.executemany(
            """
            INSERT OR IGNORE INTO owned_item_soundtrack
              (owned_item_id, option_id, created_at)
            VALUES (?, ?, ?)
            """,
            [(owned_item_id, option_id, timestamp) for option_id in valid_soundtracks],
        )


def update_owned_item(owned_item_id: int, payload: dict[str, Any]) -> bool:
    now = utc_now_iso()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, storage_slot_id FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if existing is None:
            return False
        previous_storage_slot_id = existing["storage_slot_id"]

        conn.execute(
            """
            UPDATE owned_item
            SET
              master_item_id = ?,
              linked_album_master_id = ?,
              linked_artist_name = ?,
              copy_group_key = ?,
              category = ?,
              domain_code = ?,
              release_type = ?,
              item_name_override = ?,
              quantity = ?,
              is_second_hand = ?,
              size_group = ?,
              preferred_storage_size_group = ?,
              status = ?,
              condition_grade = ?,
              signature_type = ?,
              source_code = ?,
              source_external_id = ?,
              signed_by = ?,
              signed_at = ?,
              acquisition_date = ?,
              purchase_price = ?,
              currency_code = ?,
              purchase_source = ?,
              memory_note = ?,
              display_rank = ?,
              storage_slot_id = ?,
              thickness_mm = ?,
              notes = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (
                payload.get("master_item_id"),
                payload.get("linked_album_master_id"),
                payload.get("linked_artist_name"),
                payload.get("copy_group_key"),
                payload["category"],
                payload.get("domain_code"),
                payload.get("release_type"),
                payload.get("item_name_override"),
                payload["quantity"],
                1 if payload.get("is_second_hand") else 0,
                payload["size_group"],
                payload.get("preferred_storage_size_group") or payload["size_group"],
                payload.get("status", "IN_COLLECTION"),
                payload.get("condition_grade"),
                payload.get("signature_type", "NONE"),
                payload.get("source_code"),
                payload.get("source_external_id"),
                payload.get("signed_by"),
                payload.get("signed_at"),
                payload.get("acquisition_date"),
                payload.get("purchase_price"),
                payload.get("currency_code"),
                payload.get("purchase_source"),
                payload.get("memory_note"),
                payload.get("display_rank"),
                payload.get("storage_slot_id"),
                payload.get("thickness_mm"),
                payload.get("notes"),
                now,
                owned_item_id,
            ),
        )

        _sync_owned_item_classifications_in_conn(
            conn,
            owned_item_id=owned_item_id,
            subtype_option_ids=payload.get("subtype_option_ids") or [],
            soundtrack_option_ids=payload.get("soundtrack_option_ids") or [],
            now=now,
        )

        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        else:
            conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
        goods_detail = payload.get("goods_detail")
        if goods_detail:
            _upsert_goods_item_detail_in_conn(conn, owned_item_id=owned_item_id, goods_detail=goods_detail, now=now)
        else:
            conn.execute("DELETE FROM goods_item_detail WHERE owned_item_id = ?", (owned_item_id,))

        next_storage_slot_id = payload.get("storage_slot_id")
        if previous_storage_slot_id != next_storage_slot_id:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=int(previous_storage_slot_id) if previous_storage_slot_id is not None else None,
                to_storage_slot_id=int(next_storage_slot_id) if next_storage_slot_id is not None else None,
                now=now,
            )

    return True


def bulk_update_owned_items(
    owned_item_ids: list[int],
    *,
    status: str | None = None,
    domain_code: str | None = None,
    release_type: str | None = None,
    is_second_hand: bool | None = None,
    purchase_source: str | None = None,
    append_memory_note: str | None = None,
    preferred_storage_size_group: str | None = None,
) -> list[int]:
    ids = sorted({int(v) for v in owned_item_ids if int(v) > 0})
    if not ids:
        return []

    now = utc_now_iso()
    note_text = str(append_memory_note or "").strip()
    # Bulk update touches every row in `ids` for status/domain/release_type
    # and may append memory notes. IMMEDIATE keeps the batch atomic from a
    # reader's perspective (the dashboard / export endpoints).
    with get_write_conn() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"""
            SELECT id, status, domain_code, release_type, is_second_hand, purchase_source, memory_note, preferred_storage_size_group, linked_album_master_id
            FROM owned_item
            WHERE id IN ({placeholders})
            """,
            ids,
        ).fetchall()
        existing_by_id = {int(row["id"]): dict(row) for row in rows}
        updates = []
        updated_ids = []
        master_ids_to_sync: set[int] = set()
        for owned_item_id in ids:
            row = existing_by_id.get(owned_item_id)
            if not row:
                continue
            next_status = status if status is not None else row.get("status")
            next_domain_code = domain_code if domain_code is not None else row.get("domain_code")
            next_release_type = release_type if release_type is not None else row.get("release_type")
            next_is_second_hand = int(bool(is_second_hand)) if is_second_hand is not None else int(bool(row.get("is_second_hand")))
            next_purchase_source = purchase_source if purchase_source is not None else row.get("purchase_source")
            next_preferred_size_group = (
                preferred_storage_size_group if preferred_storage_size_group is not None else row.get("preferred_storage_size_group")
            )
            next_memory_note = row.get("memory_note")
            if note_text:
                existing_note = str(next_memory_note or "").strip()
                next_memory_note = f"{existing_note}\n{note_text}".strip() if existing_note else note_text
            if (
                next_status == row.get("status")
                and next_domain_code == row.get("domain_code")
                and next_release_type == row.get("release_type")
                and next_is_second_hand == int(bool(row.get("is_second_hand")))
                and next_purchase_source == row.get("purchase_source")
                and next_preferred_size_group == row.get("preferred_storage_size_group")
                and next_memory_note == row.get("memory_note")
            ):
                continue
            updates.append(
                (
                    next_status,
                    next_domain_code,
                    next_release_type,
                    next_is_second_hand,
                    next_purchase_source,
                    next_memory_note,
                    next_preferred_size_group,
                    now,
                    owned_item_id,
                )
            )
            updated_ids.append(owned_item_id)
            linked_album_master_id = int(row.get("linked_album_master_id") or 0)
            if linked_album_master_id > 0:
                master_ids_to_sync.add(linked_album_master_id)
        if updates:
            conn.executemany(
                """
                UPDATE owned_item
                SET
                  status = ?,
                  domain_code = ?,
                  release_type = ?,
                  is_second_hand = ?,
                  purchase_source = ?,
                  memory_note = ?,
                  preferred_storage_size_group = ?,
                  updated_at = ?
                WHERE id = ?
                """,
                updates,
            )
            if domain_code is not None:
                for album_master_id in sorted(master_ids_to_sync):
                    _sync_album_master_domain_code_in_conn(conn, album_master_id)
    return updated_ids


# `set_owned_item_copy_group` lives in app/db/owned_item_copy_group.py and is
# re-exported from this package's __init__ at the bottom of the file.


def delete_owned_item(owned_item_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
        return int(cur.rowcount or 0) > 0


# `get_owned_item` and `get_owned_item_detail` live in
# app/db/owned_item_read.py and are re-exported from this package's
# __init__ at the bottom of the file.


# `get_owned_item_location_snapshot` lives in app/db/owned_item_track.py and is
# re-exported from this package's __init__ at the bottom of the file.


__all__ = [
    "insert_owned_item",
    "_sync_owned_item_classifications_in_conn",
    "update_owned_item",
    "bulk_update_owned_items",
    "delete_owned_item",
]
