"""Album master member-management DB surface.

Fifteenth slice extracted from the legacy `app/db.py`. Owns the
operator-facing CRUD on the `album_master_member` join table —
which owned_items are bound to a given master — plus the related
single-master writes/reads (existence check, sort-artist tweak,
member listing, and outright deletion).

Public exports
  * bind_album_master_members — replaces (or appends to) the member
    list for one master, normalising/validating the owned_item_ids
    before insert. Also re-syncs the master's domain_code from its
    new member set.
  * album_master_exists — cheap "is this id a real master?" probe
    used by the admin route's 404 conversion path.
  * update_album_master_sort_artist_name — single-column update for
    the operator's manual sort-artist override.
  * list_album_master_members — read the owned_items currently
    bound to a master, joined with their music_item_detail format.
  * delete_album_master — DELETE the master plus optionally cascade
    its bound owned_items. Returns counts so the route can report
    how many rows were touched.

Cross-package dependencies kept on the package surface
  * `_sync_album_master_domain_code_in_conn` is shared with the
    promote/normalise/merge writers (still in __init__.py) and a
    legacy migration path. Stays in __init__.py; the bind path here
    pulls it from the package surface.

`app/db/__init__.py` re-exports every public symbol so existing
callers (the album-master admin routes in `app/api/album_masters.py`,
the test suite, the metadata sync that calls `bind_album_master_members`)
keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _sync_album_master_domain_code_in_conn,
    get_conn,
    utc_now_iso,
)


def bind_album_master_members(
    album_master_id: int,
    owned_item_ids: list[int],
    replace_existing: bool = True,
) -> int:
    unique_ids = sorted({int(v) for v in owned_item_ids if int(v) > 0})
    now = utc_now_iso()

    with get_conn() as conn:
        if replace_existing:
            conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (album_master_id,))

        valid_ids: list[int] = []
        if unique_ids:
            placeholders = ",".join("?" for _ in unique_ids)
            rows = conn.execute(
                f"SELECT id FROM owned_item WHERE id IN ({placeholders})",
                unique_ids,
            ).fetchall()
            valid_id_set = {int(r["id"]) for r in rows}
            valid_ids = [v for v in unique_ids if v in valid_id_set]

        if valid_ids:
            conn.executemany(
                """
                INSERT OR IGNORE INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                [(album_master_id, owned_item_id, now) for owned_item_id in valid_ids],
            )
        _sync_album_master_domain_code_in_conn(conn, album_master_id)

        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM album_master_member WHERE album_master_id = ?",
            (album_master_id,),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def album_master_exists(album_master_id: int) -> bool:
    mid = int(album_master_id or 0)
    if mid <= 0:
        return False
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM album_master WHERE id = ?", (mid,)).fetchone()
        return row is not None


def update_album_master_sort_artist_name(album_master_id: int, sort_artist_name: str | None) -> dict[str, Any] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None
    normalized_value = str(sort_artist_name or "").strip() or None
    now = utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE album_master
            SET sort_artist_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_value, now, master_id),
        )
        if int(cur.rowcount or 0) <= 0:
            return None
        row = conn.execute(
            """
            SELECT id, sort_artist_name
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
    return dict(row) if row else None


def list_album_master_members(album_master_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              oi.id AS owned_item_id,
              oi.category,
              oi.item_name_override,
              oi.quantity,
              oi.status,
              mid.format_name
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = ?
            ORDER BY oi.category ASC, oi.id ASC
            """,
            (album_master_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_album_master(album_master_id: int, cascade_items: bool = False) -> dict[str, int] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master WHERE id = ?",
            (master_id,),
        ).fetchone()
        if existing is None:
            return None

        member_rows = conn.execute(
            """
            SELECT DISTINCT owned_item_id
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (master_id,),
        ).fetchall()
        member_ids = [int(r["owned_item_id"]) for r in member_rows if r["owned_item_id"] is not None]
        removed_member_links = len(member_ids)

        deleted_owned_item_count = 0
        if cascade_items and member_ids:
            placeholders = ",".join("?" for _ in member_ids)
            cur_items = conn.execute(
                f"DELETE FROM owned_item WHERE id IN ({placeholders})",
                member_ids,
            )
            deleted_owned_item_count = int(cur_items.rowcount or 0)

        cur_master = conn.execute(
            "DELETE FROM album_master WHERE id = ?",
            (master_id,),
        )
        if int(cur_master.rowcount or 0) <= 0:
            return None

    return {
        "removed_member_links": removed_member_links,
        "deleted_owned_item_count": deleted_owned_item_count,
    }


__all__ = [
    "bind_album_master_members",
    "album_master_exists",
    "update_album_master_sort_artist_name",
    "list_album_master_members",
    "delete_album_master",
]
