"""Storage routes — tenth slice of main.py -> APIRouter split.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request
from .. import db
from .. import security
from ..security import _read_auth_username
from ..schemas import (
    ClassificationOptionCreate,
    ClassificationOptionItem,
    CollectionDashboardResponse,
    OwnedItemListItem,
    SlotOrderMoveResponse,
    StorageCabinetDeleteResponse,
    StorageCabinetRegisterRequest,
    StorageCabinetRegisterResponse,
    StorageSlotItem,
    StorageSlotUpsertRequest,
    OrderMoveRequest,
)

def _audit(request: Request, entity_type: str, entity_id: int, action: str, changed_fields: list[str] | None = None, snapshot: dict | None = None) -> None:
    try:
        username = _read_auth_username(request)
        db.log_audit_event(entity_type=entity_type, entity_id=entity_id, action=action, changed_by=username, changed_fields=changed_fields, snapshot=snapshot)
    except Exception:
        pass


router = APIRouter()

def _main():
    from app import main as main_module
    return main_module

def _require_admin(request: Request) -> None:
    security._require_operator_request(request)



@router.get("/storage-slots", response_model=list[StorageSlotItem])
def get_storage_slots() -> list[StorageSlotItem]:
    rows = db.list_storage_slots()
    return [
        StorageSlotItem(
            id=row["id"],
            slot_code=row["slot_code"],
            cabinet_name=row.get("cabinet_name"),
            cabinet_domain_code=row.get("cabinet_domain_code"),
            cabinet_group_name=row.get("cabinet_group_name"),
            cabinet_group_order=row.get("cabinet_group_order"),
            column_code=row.get("column_code"),
            cell_code=row.get("cell_code"),
            display_name=row.get("display_name"),
            allowed_size_group=row["allowed_size_group"],
            cabinet_sort_policy=str(row.get("cabinet_sort_policy") or "ARTIST_RELEASE_TITLE"),
            max_thickness_mm=row.get("max_thickness_mm"),
            is_overflow_zone=bool(row["is_overflow_zone"]),
        )
        for row in rows
    ]


@router.get("/storage-slots/{storage_slot_id}/owned-items", response_model=list[OwnedItemListItem])
def get_storage_slot_owned_items(
    storage_slot_id: int,
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[OwnedItemListItem]:
    slot = db.get_storage_slot(storage_slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="storage_slot not found")
    rows = db.list_owned_items_for_storage_slot(storage_slot_id=storage_slot_id, limit=limit, offset=offset)
    return [_main()._to_owned_item_list_item(row) for row in rows]


@router.post("/storage-slots", response_model=StorageSlotItem)
def create_or_update_storage_slot(payload: StorageSlotUpsertRequest, request: Request) -> StorageSlotItem:
    try:
        row = db.upsert_storage_slot(
            slot_id=payload.slot_id,
            cabinet_name=payload.cabinet_name,
            column_code=payload.column_code,
            cell_code=payload.cell_code,
            cabinet_domain_code=payload.cabinet_domain_code,
            allowed_size_group=str(payload.allowed_size_group),
            cabinet_sort_policy=str(payload.cabinet_sort_policy),
            max_thickness_mm=payload.max_thickness_mm,
            is_overflow_zone=bool(payload.is_overflow_zone),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    return StorageSlotItem(
        id=row["id"],
        slot_code=row["slot_code"],
        cabinet_name=row.get("cabinet_name"),
        cabinet_domain_code=row.get("cabinet_domain_code"),
        cabinet_group_name=row.get("cabinet_group_name"),
        cabinet_group_order=row.get("cabinet_group_order"),
        column_code=row.get("column_code"),
        cell_code=row.get("cell_code"),
        display_name=row.get("display_name"),
        allowed_size_group=row["allowed_size_group"],
        cabinet_sort_policy=str(row.get("cabinet_sort_policy") or "ARTIST_RELEASE_TITLE"),
        max_thickness_mm=row.get("max_thickness_mm"),
        is_overflow_zone=bool(row["is_overflow_zone"]),
    )


@router.post("/storage-cabinets/register", response_model=StorageCabinetRegisterResponse)
def register_storage_cabinet(payload: StorageCabinetRegisterRequest, request: Request) -> StorageCabinetRegisterResponse:
    try:
        result = db.register_storage_cabinet_slots(
            cabinet_name=payload.cabinet_name,
            cabinet_domain_code=payload.cabinet_domain_code,
            cabinet_group_name=payload.cabinet_group_name,
            cabinet_group_order=payload.cabinet_group_order,
            floor_count=int(payload.floor_count),
            cell_count=int(payload.cell_count),
            floor_start=int(payload.floor_start),
            cell_start=int(payload.cell_start),
            allowed_size_group=str(payload.allowed_size_group),
            cabinet_sort_policy=str(payload.cabinet_sort_policy),
            max_thickness_mm=payload.max_thickness_mm,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    _audit(request, "storage_cabinet", result.get("id", 0), "CREATE", snapshot=payload.model_dump() if hasattr(payload, "model_dump") else None)
    return StorageCabinetRegisterResponse(**result)


@router.delete("/storage-cabinets", response_model=StorageCabinetDeleteResponse)
def delete_storage_cabinet(cabinet_name: str = Query(min_length=1, max_length=80), request: Request = None) -> StorageCabinetDeleteResponse:
    try:
        result = db.delete_storage_cabinet(cabinet_name=cabinet_name)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return StorageCabinetDeleteResponse(**result)


@router.get("/classification-options", response_model=list[ClassificationOptionItem])
def get_classification_options(
    option_group: str = Query(alias="group", pattern="^(SUBTYPE|SOUNDTRACK)$"),
    include_inactive: bool = Query(default=False),
) -> list[ClassificationOptionItem]:
    rows = db.list_classification_options(option_group=option_group, include_inactive=include_inactive)
    return [
        ClassificationOptionItem(
            id=int(row["id"]),
            option_group=str(row["option_group"]),
            label=str(row["label"]),
            sort_order=int(row.get("sort_order") or 0),
            is_active=bool(row.get("is_active")),
        )
        for row in rows
    ]


@router.post("/classification-options", response_model=ClassificationOptionItem)
def create_classification_option(payload: ClassificationOptionCreate) -> ClassificationOptionItem:
    row = db.upsert_classification_option(
        option_group=str(payload.option_group),
        label=payload.label.strip(),
        sort_order=int(payload.sort_order),
    )
    return ClassificationOptionItem(
        id=int(row["id"]),
        option_group=str(row["option_group"]),
        label=str(row["label"]),
        sort_order=int(row.get("sort_order") or 0),
        is_active=bool(row.get("is_active")),
    )


@router.get("/dashboard/collection", response_model=CollectionDashboardResponse)
def get_collection_dashboard() -> CollectionDashboardResponse:
    return CollectionDashboardResponse(**db.get_collection_dashboard())



@router.get("/random-album")
def random_album() -> dict[str, Any]:
    """Return a random Spotify-linked album from collection."""
    from ..db import get_conn
    with get_conn() as conn:
        conn.row_factory = __import__("sqlite3").Row
        row = conn.execute(
            "SELECT COALESCE(NULLIF(oi.item_name_override,''), am.title) as title, "
            "oi.linked_artist_name as artist, "
            "am.release_year as release_year, "
            "am.cover_image_url as cover_url "
            "FROM owned_item oi "
            "LEFT JOIN album_master am ON oi.linked_album_master_id = am.id "
            "WHERE oi.status = 'IN_COLLECTION' "
            "AND oi.source_code = 'SPOTIFY' "
            "AND (oi.item_name_override IS NOT NULL OR am.title IS NOT NULL) "
            "ORDER BY RANDOM() LIMIT 1"
        ).fetchone() if True else None
    if row:
        year = ""
        if row["release_year"] is not None:
            y = str(row["release_year"])
            if y.isdigit(): year = y
        return {
            "title": str(row["title"] or ""),
            "artist": str(row["artist"] or ""),
            "year": year,
            "cover_url": str(row["cover_url"] or ""),
        }
    return {"title": None, "artist": None, "year": "", "cover_url": ""}

@router.patch("/storage-slots/{storage_slot_id}/owned-items/{owned_item_id}/order", response_model=SlotOrderMoveResponse)
def move_owned_item_slot_order(
    storage_slot_id: int,
    owned_item_id: int,
    payload: OrderMoveRequest,
) -> SlotOrderMoveResponse:
    slot = db.get_storage_slot(storage_slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="storage_slot not found")
    try:
        display_rank = db.move_owned_item_slot_display_rank(
            storage_slot_id=storage_slot_id,
            owned_item_id=owned_item_id,
            target_owned_item_id=payload.target_owned_item_id,
            position=payload.position,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SlotOrderMoveResponse(
        storage_slot_id=storage_slot_id,
        owned_item_id=owned_item_id,
        target_owned_item_id=payload.target_owned_item_id,
        position=payload.position,
        display_rank=display_rank,
    )