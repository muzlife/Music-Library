"""Owned-item single-row read surface.

Twenty-sixth slice extracted from the legacy `app/db.py`. Owns two
tiny single-row read queries on `owned_item` that are used both
directly (`/owned-items/{id}` route, the operator detail screen)
and as the core of higher-level reads in OTHER slices that import
them at module-load time (customer_track_request, owned_item_order).

Public exports
  * get_owned_item — bare-row SELECT, returns None when missing.
  * get_owned_item_detail — joined SELECT (uses
    `_owned_item_select_query`) + normalisation pass; returns the
    same shape as a single row from `list_owned_items`.

Re-export ordering invariant
  owned_item_read MUST be re-exported BEFORE
  customer_track_request (Phase 4 — uses `get_owned_item_detail`
  at module-load time) AND BEFORE owned_item_order (Phase 24 —
  uses `get_owned_item` at module-load time).

Cross-package dependencies kept on the package surface
  * `_owned_item_select_query` and `_normalize_owned_item_row` —
    cross-cutting helpers used by every owned_item read; stay in
    `app/db/__init__.py`. The submodule pulls them via the package
    surface.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_owned_item_row,
    _owned_item_select_query,
    get_conn,
)


def get_owned_item(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_owned_item_detail(owned_item_id: int) -> dict[str, Any] | None:
    query = _owned_item_select_query() + " WHERE oi.id = ? LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(query, (owned_item_id,)).fetchone()
    if row is None:
        return None
    return _normalize_owned_item_row(dict(row))


__all__ = [
    "get_owned_item",
    "get_owned_item_detail",
]
