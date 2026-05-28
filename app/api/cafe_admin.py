"""Cafe admin API — tag and table-device management.

ADMIN-only for device registration; ADMIN+OPERATOR for tag CRUD.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..security import _require_admin_request, _require_operator_request

router = APIRouter(tags=["cafe-admin"])


# ── Request models ──────────────────────────────────────────────

class TrackTagCreateRequest(BaseModel):
    tag_type: str = Field(min_length=1, max_length=20)
    tag_value: str = Field(min_length=1, max_length=100)
    owned_item_id: int | None = None
    spotify_track_id: str | None = None


class TableDeviceRegisterRequest(BaseModel):
    table_number: str = Field(min_length=1, max_length=20)
    device_id: str = Field(min_length=1, max_length=100)
    device_label: str = ""


# ── Tag endpoints ───────────────────────────────────────────────

@router.get("/admin/cafe/tags")
def list_tags(
    request: Request,
    tag_type: str | None = None,
) -> dict[str, Any]:
    _require_operator_request(request)
    rows = db.list_track_tags(tag_type=tag_type)
    return {"total_count": len(rows), "items": rows}


@router.post("/admin/cafe/tags")
def create_tag(payload: TrackTagCreateRequest, request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    tag_id = db.insert_track_tag(
        tag_type=payload.tag_type,
        tag_value=payload.tag_value,
        owned_item_id=payload.owned_item_id,
        spotify_track_id=payload.spotify_track_id,
        created_by="admin",
    )
    if not tag_id:
        raise HTTPException(status_code=500, detail="태그 생성 실패")
    return {"id": tag_id, "ok": True}


@router.delete("/admin/cafe/tags/{tag_id}")
def delete_tag(tag_id: int, request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    ok = db.delete_track_tag(tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다")
    return {"ok": True}


@router.post("/admin/cafe/rebuild-index")
def rebuild_music_index(request: Request) -> dict[str, Any]:
    """Rebuild local music file index. ADMIN only."""
    _require_admin_request(request)
    result = db.rebuild_index()
    return result

@router.get("/admin/cafe/index-stats")
def music_index_stats(request: Request) -> dict[str, Any]:
    """Get music index statistics. OPERATOR+"""
    _require_operator_request(request)
    return db.get_index_stats()

# ── Table device endpoints ─────────────────────────────────────

@router.get("/admin/cafe/tables")
def list_tables(request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    rows = db.list_table_devices()
    return {"total_count": len(rows), "items": rows}


@router.post("/admin/cafe/tables")
def register_table(payload: TableDeviceRegisterRequest, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    result = db.register_table_device(
        table_number=payload.table_number,
        device_id=payload.device_id,
        device_label=payload.device_label,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="테이블 등록 실패")
    return result


@router.delete("/admin/cafe/tables/{device_id}")
def deactivate_table(device_id: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    ok = db.deactivate_table_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다")
    return {"ok": True}
