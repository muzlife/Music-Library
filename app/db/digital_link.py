"""Digital asset / digital link DB surface.

Seventeenth slice extracted from the legacy `app/db.py`. Owns the
`digital_asset` + `owned_item_digital_link` write path — given an
owned_item id and a link payload, INSERT a `digital_asset` row
(asset_type / file_path / file_hash / file_size_bytes /
duration_sec / metadata_json) and the `owned_item_digital_link`
row that binds it (link_type / track_no / note).

Reads against these two tables are inlined into other surfaces
(owned_item detail, album_master tracks, etc.) and are not part of
this slice — those joins stay where they live and continue using
the package-level `get_conn`.

Public exports
  * insert_digital_link — atomic two-row insert (asset + link)
    inside one connection. Returns
    `{"digital_asset_id": ..., "link_id": ...}`.

`app/db/__init__.py` re-exports the public function so existing
callers (`app/main.py` purchase-import / metadata-sync paths,
`app/api/owned_items.py` operator routes, the test suite) keep
working unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import get_conn, utc_now_iso  # noqa: E402  — package surface


def insert_digital_link(owned_item_id: int, payload: dict[str, Any]) -> dict[str, int]:
    now = utc_now_iso()
    with get_conn() as conn:
        asset_cur = conn.execute(
            """
            INSERT INTO digital_asset
              (asset_type, file_path, file_hash, file_size_bytes, duration_sec, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["asset_type"],
                payload["file_path"],
                payload.get("file_hash"),
                payload.get("file_size_bytes"),
                payload.get("duration_sec"),
                json.dumps(payload.get("metadata_json", {}), ensure_ascii=True),
                now,
                now,
            ),
        )
        asset_id = int(asset_cur.lastrowid)

        link_cur = conn.execute(
            """
            INSERT INTO owned_item_digital_link
              (owned_item_id, digital_asset_id, link_type, track_no, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                owned_item_id,
                asset_id,
                payload["link_type"],
                payload.get("track_no"),
                payload.get("note"),
                now,
            ),
        )
        link_id = int(link_cur.lastrowid)

    return {"digital_asset_id": asset_id, "link_id": link_id}


__all__ = [
    "insert_digital_link",
]
