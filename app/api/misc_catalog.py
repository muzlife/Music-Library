"""Misc catalog routes — 11th slice.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from .. import db
from .. import security
from ..schemas import (
    GoodsCategory,
    GoodsLinkedState,
    CabinetCameraConnectionTestResponse,
    CabinetCameraDeleteResponse,
    CabinetCameraDiscoveryItem,
    CabinetCameraItem,
    CabinetCameraUpsertRequest,
    GoodsItemCreateRequest,
    GoodsItemMappingUpdateRequest,
    GoodsItemRelationUpdateRequest,
    GoodsItemResponse,
    GoodsItemSearchResponse,
    GoodsItemUpdateRequest,
)

router = APIRouter()
def _main():
    from app import main as main_module
    return main_module
def _require_admin_request(request: Request) -> None:
    security._require_admin_request(request)
def _require_authenticated_request(request: Request) -> None:
    security._require_authenticated_request(request)



@router.get("/ops/cabinets", include_in_schema=False)
def ops_cabinets_shell(request: Request):
    import hashlib
    v = request.query_params.get("v")
    try:
        file_hash = hashlib.md5((STATIC_DIR / "index.html").read_bytes()).hexdigest()[:8]
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops/cabinets?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "index.html", headers=serve_headers)


@router.get("/goods-items", response_model=GoodsItemSearchResponse)
def get_goods_items(
    request: Request,
    q: str | None = Query(default=None),
    category: GoodsCategory | None = Query(default=None),
    status: GoodsStatus | None = Query(default=None),
    domain_code: DomainCode | None = Query(default=None),
    artist_name: str | None = Query(default=None),
    album_master_id: int | None = Query(default=None, ge=1),
    owned_item_id: int | None = Query(default=None, ge=1),
    label_name: str | None = Query(default=None),
    storage_slot_id: int | None = Query(default=None, ge=1),
    linked_state: GoodsLinkedState = Query(default="ANY"),
    collectible_relation_state: GoodsCollectibleRelationState = Query(default="ANY"),
    collectible_relation_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> GoodsItemSearchResponse:
    _require_admin_request(request)
    items = db.search_goods_items(
        query_text=q,
        category=category,
        status=status,
        domain_code=domain_code,
        artist_name=artist_name,
        album_master_id=album_master_id,
        owned_item_id=owned_item_id,
        label_name=label_name,
        storage_slot_id=storage_slot_id,
        linked_state=linked_state,
        collectible_relation_state=collectible_relation_state,
        collectible_relation_type=collectible_relation_type,
        limit=limit,
        offset=offset,
    )
    total_count = db.count_goods_items(
        query_text=q,
        category=category,
        status=status,
        domain_code=domain_code,
        artist_name=artist_name,
        album_master_id=album_master_id,
        owned_item_id=owned_item_id,
        label_name=label_name,
        storage_slot_id=storage_slot_id,
        linked_state=linked_state,
        collectible_relation_state=collectible_relation_state,
        collectible_relation_type=collectible_relation_type,
    )
    return GoodsItemSearchResponse(
        total_count=total_count,
        items=[_main()._goods_item_response_from_row(row) for row in items],
    )


@router.post("/goods-items", response_model=GoodsItemResponse)
def create_goods_item(payload: GoodsItemCreateRequest, request: Request) -> GoodsItemResponse:
    _require_admin_request(request)
    try:
        row = db.create_goods_item(payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return _main()._goods_item_response_from_row(row)


@router.get("/goods-items/{goods_item_id}", response_model=GoodsItemResponse)
def get_goods_item_detail(goods_item_id: int, request: Request) -> GoodsItemResponse:
    _require_admin_request(request)
    row = db.get_goods_item(goods_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _main()._goods_item_response_from_row(row)


@router.patch("/goods-items/{goods_item_id}", response_model=GoodsItemResponse)
def update_goods_item_detail(
    goods_item_id: int,
    payload: GoodsItemUpdateRequest,
    request: Request,
) -> GoodsItemResponse:
    _require_admin_request(request)
    try:
        row = db.update_goods_item(goods_item_id, payload.model_dump(exclude_unset=True))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _main()._goods_item_response_from_row(row)


@router.delete("/goods-items/{goods_item_id}")
def delete_goods_item_detail(goods_item_id: int, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    deleted = db.delete_goods_item(goods_item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="goods item not found")
    return {"deleted": True, "goods_item_id": goods_item_id}


@router.put("/goods-items/{goods_item_id}/mappings", response_model=GoodsItemResponse)
def replace_goods_item_mappings(
    goods_item_id: int,
    payload: GoodsItemMappingUpdateRequest,
    request: Request,
) -> GoodsItemResponse:
    _require_admin_request(request)
    try:
        row = db.replace_goods_item_mappings(goods_item_id, payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _main()._goods_item_response_from_row(row)


@router.put("/goods-items/{goods_item_id}/relations", response_model=GoodsItemResponse)
def replace_goods_item_collectible_relations(
    goods_item_id: int,
    payload: GoodsItemRelationUpdateRequest,
    request: Request,
) -> GoodsItemResponse:
    _require_admin_request(request)
    try:
        row = db.replace_goods_item_collectible_relations(goods_item_id, payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _main()._goods_item_response_from_row(row)


@router.get("/goods-targets")
def search_goods_mapping_targets(
    request: Request,
    kind: Literal["artist", "label", "album_master", "collectible"] = Query(...),
    q: str = Query(default=""),
    goods_item_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, list[dict[str, Any]]]:
    _require_admin_request(request)
    query = str(q or "").strip()
    if kind == "artist":
        return {
            "items": [
                {"value": name, "label": name}
                for name in db.list_goods_artist_name_candidates(query, limit=limit)
            ]
        }
    if kind == "label":
        return {
            "items": [
                {"value": name, "label": name}
                for name in db.list_goods_label_name_candidates(query, limit=limit)
            ]
        }
    if kind == "collectible":
        rows = db.search_goods_collectible_targets(
            query_text=query,
            goods_item_id=goods_item_id,
            limit=limit,
        )
        return {
            "items": [
                {
                    "value": int(row["id"]),
                    "goods_item_id": int(row["id"]),
                    "goods_name": str(row.get("goods_name") or "").strip(),
                    "category": str(row.get("category") or "").strip().upper() or None,
                }
                for row in rows
            ]
        }
    rows = db.list_album_masters(
        source_code=None,
        q=query,
        artist_or_brand=None,
        item_name=None,
        catalog_no=None,
        barcode=None,
        release_year=None,
        category=None,
        media_only=False,
        domain_code=None,
        release_type=None,
        limit=limit,
        offset=0,
    )
    return {
        "items": [
            {
                "value": int(row["id"]),
                "label": f'{str(row.get("artist_or_brand") or "").strip() or "-"} / {str(row.get("title") or "").strip() or "-"}',
                "album_master_id": int(row["id"]),
                "title": str(row.get("title") or "").strip(),
                "artist_or_brand": str(row.get("artist_or_brand") or "").strip() or None,
            }
            for row in rows
        ]
    }


@router.get("/cabinet-cameras", response_model=list[CabinetCameraItem])
def get_cabinet_cameras(
    request: Request,
    cabinet_name: str | None = Query(default=None),
) -> list[CabinetCameraItem]:
    _require_authenticated_request(request)
    rows = db.list_cabinet_cameras(cabinet_name=cabinet_name)
    return [_cabinet_camera_item_from_row(row) for row in rows]


@router.post("/cabinet-cameras", response_model=CabinetCameraItem)
def create_or_update_cabinet_camera(
    payload: CabinetCameraUpsertRequest,
    request: Request,
) -> CabinetCameraItem:
    _require_admin_request(request)
    try:
        row = db.upsert_cabinet_camera(
            camera_id=payload.camera_id,
            cabinet_name=payload.cabinet_name,
            camera_name=payload.camera_name,
            description=payload.description,
            onvif_device_url=payload.onvif_device_url,
            snapshot_url=payload.snapshot_url,
            stream_url=payload.stream_url,
            username=payload.username,
            password=payload.password,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=500, detail="cabinet camera save failed")
    return _cabinet_camera_item_from_row(row)


@router.get("/cabinet-cameras/discover", response_model=list[CabinetCameraDiscoveryItem])
def discover_cabinet_cameras(
    request: Request,
    timeout_ms: int = Query(default=2500, ge=500, le=10000),
) -> list[CabinetCameraDiscoveryItem]:
    _require_admin_request(request)
    rows = _discover_onvif_devices(timeout_seconds=float(timeout_ms) / 1000.0)
    return [CabinetCameraDiscoveryItem(**row) for row in rows]


@router.post("/cabinet-cameras/test-onvif", response_model=CabinetCameraConnectionTestResponse)
def test_cabinet_camera_connection(
    payload: CabinetCameraConnectionTestRequest,
    request: Request,
) -> CabinetCameraConnectionTestResponse:
    _require_admin_request(request)
    username = str(payload.username or "").strip() or None
    password = payload.password
    if payload.camera_id and (not username or password is None):
        existing = db.get_cabinet_camera(payload.camera_id)
        if existing is not None:
            if not username:
                username = str(existing.get("username") or "").strip() or None
            if password is None:
                password = str(existing.get("password") or "") or None
    try:
        result = _test_onvif_camera_connection(
            payload.onvif_device_url,
            username=username,
            password=password,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except httpx.HTTPStatusError as err:
        raise HTTPException(status_code=502, detail=f"ONVIF 응답 오류: {err.response.status_code}") from err
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"ONVIF 연결 테스트 실패: {err}") from err
    return CabinetCameraConnectionTestResponse(**result)


@router.delete("/cabinet-cameras/{camera_id}", response_model=CabinetCameraDeleteResponse)
def remove_cabinet_camera(camera_id: int, request: Request) -> CabinetCameraDeleteResponse:
    _require_admin_request(request)
    existing = db.get_cabinet_camera(camera_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="cabinet camera not found")
    deleted = db.delete_cabinet_camera(camera_id)
    return CabinetCameraDeleteResponse(
        camera_id=int(camera_id),
        cabinet_name=str(existing.get("cabinet_name") or "").strip(),
        deleted=bool(deleted),
    )


@router.get("/cabinet-cameras/{camera_id}/snapshot")
def get_cabinet_camera_snapshot(camera_id: int, request: Request) -> Response:
    _require_authenticated_request(request)
    row = db.get_cabinet_camera(camera_id)
    if row is None:
        raise HTTPException(status_code=404, detail="cabinet camera not found")
    if not bool(row.get("is_active")):
        raise HTTPException(status_code=400, detail="cabinet camera inactive")
    snapshot_url = _camera_http_url_or_none(row.get("snapshot_url"))
    stream_url = _camera_rtsp_url_or_none(row.get("stream_url"))
    username = str(row.get("username") or "").strip()
    password = str(row.get("password") or "")
    snapshot_bytes: bytes | None = None
    last_error: str | None = None
    if snapshot_url is not None:
        auth = (username, password) if username else None
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True, verify=False) as client:
                upstream = client.get(snapshot_url, auth=auth)
            if upstream.status_code < 400:
                media_type = str(upstream.headers.get("content-type") or "image/jpeg").split(";", 1)[0].strip() or "image/jpeg"
                return Response(
                    content=upstream.content,
                    media_type=media_type,
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
                )
            last_error = f"camera snapshot upstream returned {upstream.status_code}"
        except Exception as err:
            last_error = f"camera snapshot fetch failed: {err}"
    if stream_url is not None:
        try:
            snapshot_bytes = _camera_snapshot_bytes_from_stream(stream_url, username=username or None, password=password or None)
        except Exception as err:
            last_error = f"camera stream snapshot failed: {err}"
        else:
            return Response(
                content=snapshot_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
    if snapshot_url is None:
        raise HTTPException(status_code=400, detail="snapshot_url or rtsp stream not configured")
    raise HTTPException(status_code=502, detail=last_error or "camera snapshot unavailable")