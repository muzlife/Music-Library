"""Album master merge-history DB surface.

Eleventh slice extracted from the legacy `app/db.py`. Owns the
`album_master_merge_history` table reads — the operator-facing
audit log that powers the "최근 병합" panel and the
"마지막 병합 되돌리기" button on the album-master admin screen.

Public exports
  * list_album_master_merge_history — recent N audit rows with each
    row's rollback eligibility computed against the live
    album_master / album_master_member / album_master_external_ref
    state.
  * rollback_latest_album_master_merge — restores the most recent
    not-yet-rolled-back merge, transactionally.

Module-private helpers
  * _json_loads_or_default — defensive JSON parse used to decode the
    `*_json` snapshot columns. Only used inside this slice.
  * _album_master_merge_history_record — row-shape builder shared by
    list/rollback. Computes the rollback_available flag.
  * _latest_open_album_master_merge_history_id — find-the-rollback-
    candidate query used by both list (to mark it rollback-able) and
    rollback (to lock onto the same row).

Cross-package dependencies kept on the package surface
  * `_normalize_domain_code_value` and `_snapshot_album_master_record`
    are NOT moved — `_snapshot_album_master_record` is also called by
    `merge_album_masters` (still in app/db/__init__.py), and
    `_normalize_domain_code_value` is used 25+ times across the
    package. Both stay in `__init__.py` and the rollback function
    here imports them via the `app.db` package surface.

`app/db/__init__.py` re-exports both public functions so existing
callers (the `/admin/album-masters/...` routes in
`app/api/album_masters.py`, the test suite) keep working unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_domain_code_value,
    get_conn,
    get_write_conn,
    utc_now_iso,
)


def _json_loads_or_default(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    try:
        import json

        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return default
    return parsed


def _album_master_merge_history_record(
    conn: sqlite3.Connection,
    row: sqlite3.Row | dict[str, Any],
    latest_open_history_id: int | None = None,
) -> dict[str, Any]:
    data = dict(row)
    source_snapshot = _json_loads_or_default(data.get("source_master_snapshot_json"), {})
    target_snapshot = _json_loads_or_default(data.get("target_master_snapshot_json"), {})
    source_member_links = _json_loads_or_default(data.get("source_member_links_json"), [])
    source_external_refs = _json_loads_or_default(data.get("source_external_refs_json"), [])
    overlap_owned_item_ids = [int(v) for v in _json_loads_or_default(data.get("overlap_owned_item_ids_json"), []) if int(v) > 0]

    history_id = int(data.get("id") or 0)
    source_id = int(data.get("source_album_master_id") or 0)
    target_id = int(data.get("target_album_master_id") or 0)
    moved_owned_item_ids = [int(item.get("owned_item_id") or 0) for item in source_member_links if int(item.get("owned_item_id") or 0) > 0]
    rolled_back_at = str(data.get("rolled_back_at") or "").strip() or None
    rollback_available = False
    rollback_blocked_reason = None

    if rolled_back_at:
        rollback_blocked_reason = "already rolled back"
    elif latest_open_history_id is not None and history_id != latest_open_history_id:
        rollback_blocked_reason = "only the latest merge can be rolled back"
    else:
        target_row = conn.execute(
            """
            SELECT id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        if target_row is None:
            rollback_blocked_reason = "rollback unavailable: target master is missing"
        else:
            target_updated_at_after_merge = str(data.get("target_updated_at_after_merge") or "").strip() or None
            current_target_updated_at = str(target_row["updated_at"] or "").strip() or None
            if target_updated_at_after_merge and current_target_updated_at != target_updated_at_after_merge:
                rollback_blocked_reason = "rollback unavailable: target master changed after merge"
            elif conn.execute("SELECT id FROM album_master WHERE id = ? LIMIT 1", (source_id,)).fetchone() is not None:
                rollback_blocked_reason = "rollback unavailable: source master id is already in use"
            elif conn.execute(
                """
                SELECT id
                FROM album_master
                WHERE source_code = ? AND source_master_id = ?
                LIMIT 1
                """,
                (
                    str(source_snapshot.get("source_code") or "").strip(),
                    str(source_snapshot.get("source_master_id") or "").strip(),
                ),
            ).fetchone() is not None:
                rollback_blocked_reason = "rollback unavailable: source master key is already reused"
            else:
                placeholders = ",".join("?" for _ in moved_owned_item_ids)
                if moved_owned_item_ids and placeholders:
                    current_owned_rows = conn.execute(
                        f"""
                        SELECT id, linked_album_master_id
                        FROM owned_item
                        WHERE id IN ({placeholders})
                        """,
                        moved_owned_item_ids,
                    ).fetchall()
                    current_owned_map = {int(item["id"]): int(item["linked_album_master_id"] or 0) for item in current_owned_rows}
                    if sorted(current_owned_map.keys()) != sorted(moved_owned_item_ids):
                        rollback_blocked_reason = "rollback unavailable: moved items are missing"
                    elif any(current_owned_map.get(item_id) != target_id for item_id in moved_owned_item_ids):
                        rollback_blocked_reason = "rollback unavailable: moved items changed after merge"
                if rollback_blocked_reason is None and source_external_refs:
                    ref_ids = [int(item.get("id") or 0) for item in source_external_refs if int(item.get("id") or 0) > 0]
                    if ref_ids:
                        placeholders = ",".join("?" for _ in ref_ids)
                        current_ref_rows = conn.execute(
                            f"""
                            SELECT id, album_master_id
                            FROM album_master_external_ref
                            WHERE id IN ({placeholders})
                            """,
                            ref_ids,
                        ).fetchall()
                        current_ref_map = {int(item["id"]): int(item["album_master_id"] or 0) for item in current_ref_rows}
                        if sorted(current_ref_map.keys()) != sorted(ref_ids):
                            rollback_blocked_reason = "rollback unavailable: source refs changed after merge"
                        elif any(current_ref_map.get(ref_id) != target_id for ref_id in ref_ids):
                            rollback_blocked_reason = "rollback unavailable: source refs changed after merge"
                if rollback_blocked_reason is None:
                    rollback_available = True

    return {
        "id": history_id,
        "source_album_master_id": source_id,
        "target_album_master_id": target_id,
        "source_code": str(source_snapshot.get("source_code") or "").strip() or None,
        "source_master_id": str(source_snapshot.get("source_master_id") or "").strip() or None,
        "source_title": str(source_snapshot.get("title") or "").strip() or None,
        "source_artist_or_brand": str(source_snapshot.get("artist_or_brand") or "").strip() or None,
        "target_title": str(target_snapshot.get("title") or "").strip() or None,
        "target_artist_or_brand": str(target_snapshot.get("artist_or_brand") or "").strip() or None,
        "moved_member_count": int(data.get("moved_member_count") or 0),
        "target_member_count": int(data.get("target_member_count") or 0),
        "source_owned_item_ids": moved_owned_item_ids,
        "overlap_owned_item_ids": overlap_owned_item_ids,
        "merged_by": str(data.get("merged_by") or "").strip() or None,
        "created_at": str(data.get("created_at") or "").strip() or None,
        "rolled_back_at": rolled_back_at,
        "rolled_back_by": str(data.get("rolled_back_by") or "").strip() or None,
        "rollback_available": rollback_available,
        "rollback_blocked_reason": rollback_blocked_reason,
    }


def _latest_open_album_master_merge_history_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        """
        SELECT id
        FROM album_master_merge_history
        WHERE rolled_back_at IS NULL
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    history_id = int(row["id"] or 0) if row else 0
    return history_id or None


def list_album_master_merge_history(limit: int = 10) -> list[dict[str, Any]]:
    resolved_limit = max(1, min(int(limit or 10), 50))
    with get_conn() as conn:
        latest_open_history_id = _latest_open_album_master_merge_history_id(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM album_master_merge_history
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (resolved_limit,),
        ).fetchall()
        return [
            _album_master_merge_history_record(conn, row, latest_open_history_id=latest_open_history_id)
            for row in rows
        ]


def rollback_latest_album_master_merge(rolled_back_by: str | None = None) -> dict[str, Any]:
    normalized_actor = str(rolled_back_by or "").strip() or None
    with get_conn() as conn:
        history_row = conn.execute(
            """
            SELECT *
            FROM album_master_merge_history
            WHERE rolled_back_at IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if history_row is None:
            raise LookupError("album master merge history not found")

        history_id = int(history_row["id"] or 0)
        history_item = _album_master_merge_history_record(conn, history_row, latest_open_history_id=history_id)
        if not history_item["rollback_available"]:
            raise ValueError(str(history_item.get("rollback_blocked_reason") or "rollback unavailable"))

        source_snapshot = _json_loads_or_default(history_row["source_master_snapshot_json"], {})
        target_snapshot = _json_loads_or_default(history_row["target_master_snapshot_json"], {})
        source_member_links = _json_loads_or_default(history_row["source_member_links_json"], [])
        source_external_refs = _json_loads_or_default(history_row["source_external_refs_json"], [])
        overlap_owned_item_ids = {
            int(value)
            for value in _json_loads_or_default(history_row["overlap_owned_item_ids_json"], [])
            if int(value) > 0
        }

        source_id = int(history_row["source_album_master_id"] or 0)
        target_id = int(history_row["target_album_master_id"] or 0)
        source_owned_item_ids = [
            int(item.get("owned_item_id") or 0)
            for item in source_member_links
            if int(item.get("owned_item_id") or 0) > 0
        ]
        source_ref_ids = [
            int(item.get("id") or 0)
            for item in source_external_refs
            if int(item.get("id") or 0) > 0
        ]
        moved_non_overlap_ids = [item_id for item_id in source_owned_item_ids if item_id not in overlap_owned_item_ids]
        rolled_back_at = utc_now_iso()

        conn.execute(
            """
            INSERT INTO album_master
              (id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                str(source_snapshot.get("source_code") or "").strip(),
                str(source_snapshot.get("source_master_id") or "").strip(),
                str(source_snapshot.get("title") or "").strip(),
                str(source_snapshot.get("artist_or_brand") or "").strip() or None,
                str(source_snapshot.get("sort_artist_name") or "").strip() or None,
                _normalize_domain_code_value(source_snapshot.get("domain_code")),
                source_snapshot.get("release_year"),
                str(source_snapshot.get("raw_json") or "{}"),
                str(source_snapshot.get("created_at") or "").strip() or rolled_back_at,
                str(source_snapshot.get("updated_at") or "").strip() or rolled_back_at,
            ),
        )
        conn.execute(
            """
            UPDATE album_master
            SET source_code = ?,
                source_master_id = ?,
                title = ?,
                artist_or_brand = ?,
                sort_artist_name = ?,
                domain_code = ?,
                release_year = ?,
                raw_json = ?,
                created_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(target_snapshot.get("source_code") or "").strip(),
                str(target_snapshot.get("source_master_id") or "").strip(),
                str(target_snapshot.get("title") or "").strip(),
                str(target_snapshot.get("artist_or_brand") or "").strip() or None,
                str(target_snapshot.get("sort_artist_name") or "").strip() or None,
                _normalize_domain_code_value(target_snapshot.get("domain_code")),
                target_snapshot.get("release_year"),
                str(target_snapshot.get("raw_json") or "{}"),
                str(target_snapshot.get("created_at") or "").strip() or rolled_back_at,
                str(target_snapshot.get("updated_at") or "").strip() or rolled_back_at,
                target_id,
            ),
        )
        if moved_non_overlap_ids:
            placeholders = ",".join("?" for _ in moved_non_overlap_ids)
            conn.execute(
                f"""
                DELETE FROM album_master_member
                WHERE album_master_id = ? AND owned_item_id IN ({placeholders})
                """,
                [target_id, *moved_non_overlap_ids],
            )
        if source_member_links:
            conn.executemany(
                """
                INSERT INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        source_id,
                        int(item.get("owned_item_id") or 0),
                        str(item.get("created_at") or "").strip() or rolled_back_at,
                    )
                    for item in source_member_links
                    if int(item.get("owned_item_id") or 0) > 0
                ],
            )
        if source_member_links:
            conn.executemany(
                """
                UPDATE owned_item
                SET linked_album_master_id = ?, updated_at = ?
                WHERE id = ?
                """,
                [
                    (
                        int(item["linked_album_master_id"]) if item.get("linked_album_master_id") not in (None, "") else source_id,
                        rolled_back_at,
                        int(item.get("owned_item_id") or 0),
                    )
                    for item in source_member_links
                    if int(item.get("owned_item_id") or 0) > 0
                ],
            )
        if source_ref_ids:
            placeholders = ",".join("?" for _ in source_ref_ids)
            conn.execute(
                f"""
                UPDATE album_master_external_ref
                SET album_master_id = ?, updated_at = ?
                WHERE id IN ({placeholders})
                """,
                [source_id, rolled_back_at, *source_ref_ids],
            )
        conn.execute(
            """
            UPDATE album_master_merge_history
            SET rolled_back_at = ?, rolled_back_by = ?
            WHERE id = ?
            """,
            (rolled_back_at, normalized_actor, history_id),
        )

    return {
        "merge_history_id": history_id,
        "source_album_master_id": source_id,
        "target_album_master_id": target_id,
        "restored_member_count": len(source_owned_item_ids),
        "rolled_back": True,
    }


# `get_write_conn` is imported above for symmetry / future use, but
# the rollback intentionally currently reuses get_conn (which already
# wraps in a single transaction). The original surface used the same
# context manager — keep behaviour identical to avoid surprise.
__all__ = [
    "list_album_master_merge_history",
    "rollback_latest_album_master_merge",
]
