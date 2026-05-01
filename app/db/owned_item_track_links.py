"""Owned-item track / audio-directory link DB surface.

Twenty-first slice extracted from the legacy `app/db.py`. Owns the
read + delete surface on the two link tables that connect an
`owned_item` to its track-level digital assets:

  * `owned_item_track_link` — a track from a digital_asset is mapped
    to one or more owned_items (e.g., a single FLAC file maps to
    track 4 of an owned LP and track 4 of an owned CD).
  * `owned_item_audio_directory_link` — an entire directory of
    audio files is mapped to an owned_item (typical for "I dropped
    a folder of FLAC files into the watch directory").

Public exports
  * list_owned_item_track_links — read every track_link row plus
    the joined digital_asset/track metadata for one owned_item.
  * list_owned_item_audio_directory_links — read every directory
    link row plus its directory_path / status / file_count.
  * delete_owned_item_track_links — remove all track_links for one
    owned_item; cascades to dropping orphan digital_assets.
  * delete_owned_item_audio_directory_links — remove all directory
    links for one owned_item.

The dual write paths (insert track/dir links) live elsewhere — most
go through `digital_link.insert_digital_link` (Phase 17) and the
metadata-sync watch-directory paths in `app/main.py`. Only the
list/delete surface lives here.

`app/db/__init__.py` re-exports every public symbol so existing
callers (`/owned-items/{id}/links` routes, the test suite, the
delete-cascade path in the operator owned-item form) keep working
unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import get_conn  # noqa: E402  — package surface


def list_owned_item_track_links(owned_item_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              l.id AS link_id,
              l.track_no,
              l.note,
              l.created_at,
              a.id AS digital_asset_id,
              a.file_path,
              a.duration_sec
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ? AND l.link_type = 'TRACK'
            ORDER BY l.track_no ASC, l.id ASC
            """,
            (owned_item_id,),
        ).fetchall()

    return [dict(r) for r in rows]


def list_owned_item_audio_directory_links(owned_item_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              l.id AS link_id,
              l.note,
              l.created_at,
              a.id AS digital_asset_id,
              a.file_path,
              a.metadata_json
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ?
              AND l.link_type = 'FULL_ALBUM'
              AND a.asset_type = 'AUDIO'
            ORDER BY l.id DESC
            """,
            (owned_item_id,),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_meta = item.pop("metadata_json", None)
        if raw_meta:
            try:
                parsed = json.loads(str(raw_meta))
            except json.JSONDecodeError:
                parsed = {}
        else:
            parsed = {}
        item["metadata_json"] = parsed if isinstance(parsed, dict) else {}
        out.append(item)
    return out


def delete_owned_item_audio_directory_links(owned_item_id: int) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT l.digital_asset_id
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ?
              AND l.link_type = 'FULL_ALBUM'
              AND a.asset_type = 'AUDIO'
            """,
            (owned_item_id,),
        ).fetchall()
        asset_ids = sorted({int(r["digital_asset_id"]) for r in rows if r["digital_asset_id"] is not None})

        cur = conn.execute(
            """
            DELETE FROM owned_item_digital_link
            WHERE id IN (
                SELECT l.id
                FROM owned_item_digital_link l
                JOIN digital_asset a ON a.id = l.digital_asset_id
                WHERE l.owned_item_id = ?
                  AND l.link_type = 'FULL_ALBUM'
                  AND a.asset_type = 'AUDIO'
            )
            """,
            (owned_item_id,),
        )
        deleted = int(cur.rowcount or 0)

        if asset_ids:
            placeholders = ",".join("?" for _ in asset_ids)
            conn.execute(
                f"""
                DELETE FROM digital_asset
                WHERE id IN ({placeholders})
                  AND id NOT IN (SELECT DISTINCT digital_asset_id FROM owned_item_digital_link)
                """,
                asset_ids,
            )

    return deleted


def delete_owned_item_track_links(owned_item_id: int) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT digital_asset_id
            FROM owned_item_digital_link
            WHERE owned_item_id = ? AND link_type = 'TRACK'
            """,
            (owned_item_id,),
        ).fetchall()
        asset_ids = sorted({int(r["digital_asset_id"]) for r in rows if r["digital_asset_id"] is not None})

        cur = conn.execute(
            """
            DELETE FROM owned_item_digital_link
            WHERE owned_item_id = ? AND link_type = 'TRACK'
            """,
            (owned_item_id,),
        )
        deleted = int(cur.rowcount or 0)

        if asset_ids:
            placeholders = ",".join("?" for _ in asset_ids)
            conn.execute(
                f"""
                DELETE FROM digital_asset
                WHERE id IN ({placeholders})
                  AND id NOT IN (SELECT DISTINCT digital_asset_id FROM owned_item_digital_link)
                """,
                asset_ids,
            )

    return deleted


# `upsert_album_master` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `normalize_album_master_source_id` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `promote_album_master_source` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_album_master_record` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_member_link_records` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_external_ref_records` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `merge_album_masters` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `set_owned_item_linked_album_master` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_build_album_master_filter_sql` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_album_masters` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `count_album_masters` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.




__all__ = [
    "list_owned_item_track_links",
    "list_owned_item_audio_directory_links",
    "delete_owned_item_track_links",
    "delete_owned_item_audio_directory_links",
]
