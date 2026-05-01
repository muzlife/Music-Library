"""Owned-item copy-group / source-external-id lookup surface.

Twenty-second slice extracted from the legacy `app/db.py`. Owns a
trio of small but related queries on the `owned_item` table.

Public exports
  * set_owned_item_copy_group — single-column write to mark which
    `copy_group_key` an owned_item belongs to (operator manual
    grouping when one purchase shipped as multiple physical items).
  * list_owned_items_by_copy_group — read every owned_item that
    shares one copy_group_key. Used by the operator detail screen
    to display sibling items of the same purchase.
  * list_owned_items_by_source_external_ids — read every owned_item
    bound (via album_master_member → album_master_external_ref) to
    one of the given (source_code, source_master_id) keys. Powers
    the metadata-sync "skip already-linked items" optimisation.

Cross-package dependencies kept on the package surface
  * `_normalize_owned_item_row` and `_owned_item_select_query` are
    cross-cutting helpers used by every owned_item read; they stay
    in `app/db/__init__.py`. The submodule pulls them via the
    package surface.

`app/db/__init__.py` re-exports every public symbol so existing
callers (operator detail screen, metadata-sync providers, the test
suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_owned_item_row,
    _owned_item_select_query,
    get_conn,
    utc_now_iso,
)


def set_owned_item_copy_group(owned_item_id: int, copy_group_key: str | None) -> bool:
    now = utc_now_iso()
    key = str(copy_group_key or "").strip() or None
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE owned_item
            SET copy_group_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (key, now, owned_item_id),
        )
        return int(cur.rowcount or 0) > 0


def list_owned_items_by_copy_group(copy_group_key: str) -> list[dict[str, Any]]:
    key = str(copy_group_key or "").strip()
    if not key:
        return []

    query = (
        _owned_item_select_query()
        + """
        WHERE oi.copy_group_key = ?
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
        rows = conn.execute(query, (key,)).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


def list_owned_items_by_source_external_ids(source_code: str, source_external_ids: list[str]) -> list[dict[str, Any]]:
    cleaned = sorted({str(v).strip() for v in source_external_ids if str(v).strip()})
    if not source_code or not cleaned:
        return []

    placeholders = ",".join("?" for _ in cleaned)
    query = (
        _owned_item_select_query()
        + f"""
        WHERE oi.source_code = ?
          AND oi.source_external_id IN ({placeholders})
          AND oi.status IN ('IN_COLLECTION', 'LOANED', 'ARCHIVED')
        ORDER BY
          CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
          oi.order_key ASC,
          CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
          oi.display_rank ASC,
          oi.created_at DESC,
          oi.id DESC
        """
    )
    params: list[Any] = [source_code, *cleaned]
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


__all__ = [
    "set_owned_item_copy_group",
    "list_owned_items_by_copy_group",
    "list_owned_items_by_source_external_ids",
]
