"""Purchase-import queue DB surface.

Third slice extracted from the legacy `app/db.py`. Owns the
`purchase_import_queue` table — schema, migration, dedupe, and CRUD.

Public exports
  * insert_purchase_import_rows
  * find_purchase_import_duplicate_row
  * list_purchase_import_rows
  * count_purchase_import_rows
  * has_purchase_import_for_source_ref
  * get_purchase_import_row
  * update_purchase_import_row

Module-private exports (re-exported from `app.db.__init__` so the
legacy migration helpers continue to find them by bare name)
  * _purchase_import_vendor_check_sql
  * _ensure_purchase_import_queue_table
  * _migrate_purchase_import_queue_allow_file_upload
  * _purchase_import_queue_allows_file_upload
  * _purchase_import_queue_allows_extended_vendors
  * _purchase_import_cmp_text
  * _purchase_import_cmp_float
  * _purchase_import_row_matches_duplicate
  * _find_purchase_import_duplicate_in_conn

`app/db/__init__.py` re-exports every public symbol so existing
callers (`db.insert_purchase_import_rows(...)`, the webhook router, the
test suite) keep working.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from app.db import _UNSET, get_conn, get_write_conn, utc_now_iso  # noqa: E402


# --------------------------------------------------------------------------- #
# Schema / migration
# --------------------------------------------------------------------------- #
def _purchase_import_vendor_check_sql() -> str:
    return "', '".join(("SAILMUSIC", "AMAZON", "EBAY", "ALADIN", "YES24", "OTHER"))


def _ensure_purchase_import_queue_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS purchase_import_queue (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vendor_code TEXT NOT NULL CHECK (vendor_code IN ('{_purchase_import_vendor_check_sql()}')),
          source_type TEXT NOT NULL CHECK (source_type IN ('EMAIL_HTML', 'EMAIL_TEXT', 'FILE_UPLOAD', 'MANUAL')),
          source_ref TEXT,
          email_from TEXT,
          email_subject TEXT,
          artist_name TEXT,
          item_name TEXT NOT NULL,
          media_format TEXT,
          quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
          unit_price REAL,
          line_total REAL,
          currency_code TEXT,
          purchase_date TEXT,
          seller_name TEXT,
          item_url TEXT,
          image_url TEXT,
          raw_line TEXT,
          raw_payload_json TEXT NOT NULL DEFAULT '{{}}',
          queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
          linked_owned_item_id INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC)"
    )
    # Webhook-level dedupe lookup (vendor_code + source_ref). Partial index
    # because most rows have NULL source_ref and we only care about webhook
    # deliveries that carry one.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_source_ref "
        "ON purchase_import_queue (vendor_code, source_ref) "
        "WHERE source_ref IS NOT NULL"
    )


def _purchase_import_queue_allows_file_upload(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "SOURCE_TYPE" in table_sql and "'FILE_UPLOAD'" in table_sql


def _purchase_import_queue_allows_extended_vendors(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "VENDOR_CODE" in table_sql and "'ALADIN'" in table_sql and "'YES24'" in table_sql


def _migrate_purchase_import_queue_allow_file_upload(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
    ).fetchone()
    if not row or (
        _purchase_import_queue_allows_file_upload(conn)
        and _purchase_import_queue_allows_extended_vendors(conn)
    ):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            f"""
            BEGIN;
            DROP TABLE IF EXISTS purchase_import_queue_new;
            CREATE TABLE purchase_import_queue_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vendor_code TEXT NOT NULL CHECK (vendor_code IN ('{_purchase_import_vendor_check_sql()}')),
              source_type TEXT NOT NULL CHECK (source_type IN ('EMAIL_HTML', 'EMAIL_TEXT', 'FILE_UPLOAD', 'MANUAL')),
              source_ref TEXT,
              email_from TEXT,
              email_subject TEXT,
              artist_name TEXT,
              item_name TEXT NOT NULL,
              media_format TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              unit_price REAL,
              line_total REAL,
              currency_code TEXT,
              purchase_date TEXT,
              seller_name TEXT,
              item_url TEXT,
              image_url TEXT,
              raw_line TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{{}}',
              queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
              linked_owned_item_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
            );
            INSERT INTO purchase_import_queue_new (
              id, vendor_code, source_type, source_ref, email_from, email_subject,
              artist_name, item_name, media_format, quantity, unit_price, line_total,
              currency_code, purchase_date, seller_name, item_url, image_url,
              raw_line, raw_payload_json, queue_status, linked_owned_item_id, created_at, updated_at
            )
            SELECT
              id, vendor_code, source_type, source_ref, email_from, email_subject,
              artist_name, item_name, media_format, quantity, unit_price, line_total,
              currency_code, purchase_date, seller_name, item_url, image_url,
              raw_line, raw_payload_json, queue_status, linked_owned_item_id, created_at, updated_at
            FROM purchase_import_queue;
            DROP TABLE purchase_import_queue;
            ALTER TABLE purchase_import_queue_new RENAME TO purchase_import_queue;
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC);
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# --------------------------------------------------------------------------- #
# Dedupe helpers
# --------------------------------------------------------------------------- #
def _purchase_import_cmp_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _purchase_import_cmp_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _purchase_import_row_matches_duplicate(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source_ref: str | None = None,
    email_subject: str | None = None,
) -> bool:
    existing_item_name = _purchase_import_cmp_text(existing.get("item_name"))
    incoming_item_name = _purchase_import_cmp_text(incoming.get("item_name"))
    if not existing_item_name or existing_item_name != incoming_item_name:
        return False

    existing_media = _purchase_import_cmp_text(existing.get("media_format")).upper()
    incoming_media = _purchase_import_cmp_text(incoming.get("media_format")).upper()
    if existing_media != incoming_media:
        return False

    existing_quantity = int(existing.get("quantity") or 1)
    incoming_quantity = max(1, int(incoming.get("quantity") or 1))
    if existing_quantity != incoming_quantity:
        return False

    existing_source_ref = _purchase_import_cmp_text(existing.get("source_ref"))
    incoming_source_ref = _purchase_import_cmp_text(source_ref)
    existing_email_subject = _purchase_import_cmp_text(existing.get("email_subject"))
    incoming_email_subject = _purchase_import_cmp_text(email_subject)
    existing_item_url = _purchase_import_cmp_text(existing.get("item_url"))
    incoming_item_url = _purchase_import_cmp_text(incoming.get("item_url"))
    existing_purchase_date = _purchase_import_cmp_text(existing.get("purchase_date"))
    incoming_purchase_date = _purchase_import_cmp_text(incoming.get("purchase_date"))
    existing_raw_line = _purchase_import_cmp_text(existing.get("raw_line"))
    incoming_raw_line = _purchase_import_cmp_text(incoming.get("raw_line"))

    by_source_ref = bool(existing_source_ref and incoming_source_ref and existing_source_ref == incoming_source_ref and (not existing_raw_line or not incoming_raw_line or existing_raw_line == incoming_raw_line))
    by_item_url = bool(existing_item_url and incoming_item_url and existing_item_url == incoming_item_url and existing_purchase_date and incoming_purchase_date and existing_purchase_date == incoming_purchase_date)
    by_email_subject = bool(existing_email_subject and incoming_email_subject and existing_email_subject == incoming_email_subject and existing_raw_line and incoming_raw_line and existing_raw_line == incoming_raw_line)
    by_raw_line = bool(existing_raw_line and incoming_raw_line and existing_raw_line == incoming_raw_line and existing_purchase_date and incoming_purchase_date and existing_purchase_date == incoming_purchase_date)
    if not (by_source_ref or by_item_url or by_email_subject or by_raw_line):
        return False

    existing_unit_price = _purchase_import_cmp_float(existing.get("unit_price"))
    incoming_unit_price = _purchase_import_cmp_float(incoming.get("unit_price"))
    if existing_unit_price is not None and incoming_unit_price is not None and existing_unit_price != incoming_unit_price:
        return False

    existing_line_total = _purchase_import_cmp_float(existing.get("line_total"))
    incoming_line_total = _purchase_import_cmp_float(incoming.get("line_total"))
    if existing_line_total is not None and incoming_line_total is not None and existing_line_total != incoming_line_total:
        return False

    return True


def _find_purchase_import_duplicate_in_conn(
    conn: sqlite3.Connection,
    vendor_code: str,
    row: dict[str, Any],
    *,
    source_ref: str | None = None,
    email_subject: str | None = None,
    exclude_queue_id: int | None = None,
    require_linked_owned_item: bool = False,
) -> dict[str, Any] | None:
    vendor = _purchase_import_cmp_text(vendor_code).upper()
    item_name = _purchase_import_cmp_text(row.get("item_name"))
    if not vendor or not item_name:
        return None
    params: list[Any] = [vendor, item_name]
    query = """
      SELECT id, vendor_code, source_ref, email_subject, artist_name, item_name, media_format,
             quantity, unit_price, line_total, currency_code, purchase_date, item_url, raw_line,
             queue_status, linked_owned_item_id
      FROM purchase_import_queue
      WHERE vendor_code = ?
        AND item_name = ?
    """
    if require_linked_owned_item:
        query += " AND linked_owned_item_id IS NOT NULL"
    if exclude_queue_id is not None:
        query += " AND id <> ?"
        params.append(int(exclude_queue_id))
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    incoming = dict(row)
    incoming["source_ref"] = source_ref
    incoming["email_subject"] = email_subject
    for existing in rows:
        existing_row = dict(existing)
        if _purchase_import_row_matches_duplicate(existing_row, incoming, source_ref=source_ref, email_subject=email_subject):
            return existing_row
    return None


# --------------------------------------------------------------------------- #
# Public CRUD
# --------------------------------------------------------------------------- #
def insert_purchase_import_rows(
    vendor_code: str,
    source_type: str,
    rows: list[dict[str, Any]],
    *,
    source_ref: str | None = None,
    email_from: str | None = None,
    email_subject: str | None = None,
    purchase_date: str | None = None,
) -> list[int]:
    now = utc_now_iso()
    created_ids: list[int] = []
    # Multi-row INSERT path with row-level dedupe — wrap in IMMEDIATE so a
    # concurrent worker (metadata sync, auto-backup) cannot squeeze a write
    # between dedupe SELECT and INSERT and produce a duplicate.
    with get_write_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        for row in rows:
            duplicate = _find_purchase_import_duplicate_in_conn(
                conn,
                vendor_code=vendor_code,
                row=row,
                source_ref=source_ref,
                email_subject=email_subject,
            )
            if duplicate is not None:
                continue
            cur = conn.execute(
                """
                INSERT INTO purchase_import_queue (
                  vendor_code, source_type, source_ref, email_from, email_subject,
                  artist_name, item_name, media_format, quantity, unit_price, line_total,
                  currency_code, purchase_date, seller_name, item_url, image_url,
                  raw_line, raw_payload_json, queue_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    vendor_code,
                    source_type,
                    source_ref,
                    email_from,
                    email_subject,
                    row.get("artist_name"),
                    row.get("item_name"),
                    row.get("media_format"),
                    max(1, int(row.get("quantity") or 1)),
                    row.get("unit_price"),
                    row.get("line_total"),
                    row.get("currency_code"),
                    row.get("purchase_date") or purchase_date,
                    row.get("seller_name"),
                    row.get("item_url"),
                    row.get("image_url"),
                    row.get("raw_line"),
                    json.dumps(row.get("raw_payload") or {}, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            created_ids.append(int(cur.lastrowid))
    return created_ids


def find_purchase_import_duplicate_row(
    row: dict[str, Any],
    *,
    exclude_queue_id: int | None = None,
    require_linked_owned_item: bool = False,
) -> dict[str, Any] | None:
    vendor_code = _purchase_import_cmp_text(row.get("vendor_code")).upper()
    if not vendor_code:
        return None
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        return _find_purchase_import_duplicate_in_conn(
            conn,
            vendor_code=vendor_code,
            row=row,
            source_ref=row.get("source_ref"),
            email_subject=row.get("email_subject"),
            exclude_queue_id=exclude_queue_id,
            require_linked_owned_item=require_linked_owned_item,
        )


def list_purchase_import_rows(
    *,
    queue_status: str | None = "PENDING",
    vendor_code: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = """
      SELECT id, vendor_code, source_type, source_ref, email_from, email_subject,
             artist_name, item_name, media_format, quantity, unit_price, line_total,
             currency_code, purchase_date, seller_name, item_url, image_url,
             raw_line, raw_payload_json, queue_status, linked_owned_item_id,
             created_at, updated_at
      FROM purchase_import_queue
      WHERE 1=1
    """
    params: list[Any] = []
    if queue_status:
        query += " AND queue_status = ?"
        params.append(queue_status)
    if vendor_code:
        query += " AND vendor_code = ?"
        params.append(vendor_code)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        rows = conn.execute(query, params).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_payload = item.pop("raw_payload_json", None)
        item["raw_payload"] = json.loads(raw_payload) if raw_payload else {}
        items.append(item)
    return items


def has_purchase_import_for_source_ref(vendor_code: str, source_ref: str) -> bool:
    """Cheap webhook-level dedupe: returns True if a row with the same
    (vendor_code, source_ref) has already been queued.

    Gmail (and most webhook senders) re-deliver on transient delivery
    failures. The row-level dedupe in `_find_purchase_import_duplicate_in_conn`
    eventually catches duplicates, but it does so AFTER we've parsed HTML,
    resolved vendor codes and looped over each row. This pre-check lets the
    handler short-circuit a retry before any of that work runs.
    """
    vendor = str(vendor_code or "").strip().upper()
    ref = str(source_ref or "").strip()
    if not vendor or not ref:
        return False
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        row = conn.execute(
            """
            SELECT 1
            FROM purchase_import_queue
            WHERE vendor_code = ?
              AND source_ref = ?
            LIMIT 1
            """,
            (vendor, ref),
        ).fetchone()
    return row is not None


def count_purchase_import_rows(
    *, queue_status: str | None = "PENDING", vendor_code: str | None = None
) -> int:
    query = "SELECT COUNT(*) AS cnt FROM purchase_import_queue WHERE 1=1"
    params: list[Any] = []
    if queue_status:
        query += " AND queue_status = ?"
        params.append(queue_status)
    if vendor_code:
        query += " AND vendor_code = ?"
        params.append(vendor_code)
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        row = conn.execute(query, params).fetchone()
    return int(row["cnt"] or 0) if row else 0


def get_purchase_import_row(queue_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        row = conn.execute(
            """
            SELECT id, vendor_code, source_type, source_ref, email_from, email_subject,
                   artist_name, item_name, media_format, quantity, unit_price, line_total,
                   currency_code, purchase_date, seller_name, item_url, image_url,
                   raw_line, raw_payload_json, queue_status, linked_owned_item_id,
                   created_at, updated_at
            FROM purchase_import_queue
            WHERE id = ?
            LIMIT 1
            """,
            (int(queue_id),),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    raw_payload = item.pop("raw_payload_json", None)
    item["raw_payload"] = json.loads(raw_payload) if raw_payload else {}
    return item


def update_purchase_import_row(
    queue_id: int,
    *,
    queue_status: str | None = None,
    linked_owned_item_id: int | None = None,
    artist_name: Any = _UNSET,
    item_name: Any = _UNSET,
    seller_name: Any = _UNSET,
    item_url: Any = _UNSET,
    image_url: Any = _UNSET,
    raw_payload: Any = _UNSET,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    if queue_status is not None:
        assignments.append("queue_status = ?")
        params.append(queue_status)
    if linked_owned_item_id is not None:
        assignments.append("linked_owned_item_id = ?")
        params.append(int(linked_owned_item_id))
    elif queue_status == "IGNORED":
        assignments.append("linked_owned_item_id = NULL")
    if artist_name is not _UNSET:
        assignments.append("artist_name = ?")
        params.append(artist_name)
    if item_name is not _UNSET:
        assignments.append("item_name = ?")
        params.append(item_name)
    if seller_name is not _UNSET:
        assignments.append("seller_name = ?")
        params.append(seller_name)
    if item_url is not _UNSET:
        assignments.append("item_url = ?")
        params.append(item_url)
    if image_url is not _UNSET:
        assignments.append("image_url = ?")
        params.append(image_url)
    if raw_payload is not _UNSET:
        assignments.append("raw_payload_json = ?")
        params.append(json.dumps(raw_payload or {}, ensure_ascii=True))
    if not assignments:
        return get_purchase_import_row(queue_id)
    assignments.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(int(queue_id))
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        conn.execute(
            f"UPDATE purchase_import_queue SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
    return get_purchase_import_row(queue_id)


__all__ = [
    "_purchase_import_vendor_check_sql",
    "_ensure_purchase_import_queue_table",
    "_purchase_import_queue_allows_file_upload",
    "_purchase_import_queue_allows_extended_vendors",
    "_migrate_purchase_import_queue_allow_file_upload",
    "_purchase_import_cmp_text",
    "_purchase_import_cmp_float",
    "_purchase_import_row_matches_duplicate",
    "_find_purchase_import_duplicate_in_conn",
    "insert_purchase_import_rows",
    "find_purchase_import_duplicate_row",
    "list_purchase_import_rows",
    "has_purchase_import_for_source_ref",
    "count_purchase_import_rows",
    "get_purchase_import_row",
    "update_purchase_import_row",
]
