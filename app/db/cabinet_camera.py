"""Cabinet-camera DB surface.

Seventh slice extracted from the legacy `app/db.py`. Owns the
`cabinet_camera` table CRUD — list / get / get_by_cabinet / upsert /
delete. The table itself is created by the init/migration script in
app/db/__init__.py (no migration helpers live here).

Public exports
  * list_cabinet_cameras
  * get_cabinet_camera
  * get_cabinet_camera_by_cabinet
  * upsert_cabinet_camera
  * delete_cabinet_camera

`app/db/__init__.py` re-exports every public symbol so existing
callers (the cabinet-camera routes, the dashboard snapshot URL helper,
the test suite) keep working unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import get_conn, utc_now_iso  # noqa: E402  — package surface


def list_cabinet_cameras(cabinet_name: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    query = """
        SELECT
          id,
          cabinet_name,
          camera_name,
          onvif_device_url,
          snapshot_url,
          stream_url,
          username,
          password,
          notes,
          is_active,
          created_at,
          updated_at
        FROM cabinet_camera
    """
    cabinet = str(cabinet_name or "").strip()
    if cabinet:
        query += " WHERE TRIM(COALESCE(cabinet_name, '')) = ?"
        params.append(cabinet)
    query += " ORDER BY is_active DESC, LOWER(COALESCE(camera_name, cabinet_name, '')) ASC, id ASC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_cabinet_camera(camera_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              cabinet_name,
              camera_name,
              onvif_device_url,
              snapshot_url,
              stream_url,
              username,
              password,
              notes,
              is_active,
              created_at,
              updated_at
            FROM cabinet_camera
            WHERE id = ?
            LIMIT 1
            """,
            (int(camera_id),),
        ).fetchone()
    return dict(row) if row is not None else None


def get_cabinet_camera_by_cabinet(cabinet_name: str) -> dict[str, Any] | None:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              cabinet_name,
              camera_name,
              onvif_device_url,
              snapshot_url,
              stream_url,
              username,
              password,
              notes,
              is_active,
              created_at,
              updated_at
            FROM cabinet_camera
            WHERE TRIM(COALESCE(cabinet_name, '')) = ?
            LIMIT 1
            """,
            (cabinet,),
        ).fetchone()
    return dict(row) if row is not None else None


def upsert_cabinet_camera(
    *,
    camera_id: int | None = None,
    cabinet_name: str | None = None,
    camera_name: str,
    description: str | None = None,
    onvif_device_url: str | None = None,
    snapshot_url: str | None = None,
    stream_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    notes: str | None = None,
    is_active: bool = True,
) -> dict[str, Any] | None:
    name = str(camera_name or "").strip()
    if not name:
        raise ValueError("camera_name required")
    cabinet = str(cabinet_name or "").strip() or name
    now = utc_now_iso()
    device_url = str(onvif_device_url or "").strip() or None
    snapshot = str(snapshot_url or "").strip() or None
    stream = str(stream_url or "").strip() or None
    user = str(username or "").strip() or None
    secret = str(password or "")
    secret_value = secret if secret.strip() else None
    memo = str(description or notes or "").strip() or None
    active_value = int(bool(is_active))

    with get_conn() as conn:
        existing = None
        if camera_id is not None:
            existing = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (int(camera_id),)).fetchone()
            if existing is None:
                raise ValueError("cabinet_camera not found")
        else:
            existing = conn.execute(
                "SELECT * FROM cabinet_camera WHERE TRIM(COALESCE(cabinet_name, '')) = ?",
                (cabinet,),
            ).fetchone()
        if existing is not None:
            existing_id = int(existing["id"])
            duplicate = conn.execute(
                "SELECT id FROM cabinet_camera WHERE TRIM(COALESCE(cabinet_name, '')) = ? AND id <> ?",
                (cabinet, existing_id),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("duplicate cabinet camera mapping")
            if secret_value is None:
                secret_value = str(existing["password"] or "").strip() or None
            conn.execute(
                """
                UPDATE cabinet_camera
                SET cabinet_name = ?, camera_name = ?, onvif_device_url = ?, snapshot_url = ?, stream_url = ?,
                    username = ?, password = ?, notes = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (cabinet, name, device_url, snapshot, stream, user, secret_value, memo, active_value, now, existing_id),
            )
            row = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (existing_id,)).fetchone()
        else:
            cur = conn.execute(
                """
                INSERT INTO cabinet_camera
                  (cabinet_name, camera_name, onvif_device_url, snapshot_url, stream_url, username, password, notes, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cabinet, name, device_url, snapshot, stream, user, secret_value, memo, active_value, now, now),
            )
            row = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return dict(row) if row is not None else None


def delete_cabinet_camera(camera_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cabinet_camera WHERE id = ?", (int(camera_id),))
    return int(cur.rowcount or 0) > 0


__all__ = [
    "list_cabinet_cameras",
    "get_cabinet_camera",
    "get_cabinet_camera_by_cabinet",
    "upsert_cabinet_camera",
    "delete_cabinet_camera",
]
