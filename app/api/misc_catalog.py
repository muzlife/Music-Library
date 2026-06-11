"""Misc catalog routes — 11th slice.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from .. import db
from .. import security
from .discogs_integration import get_discogs_release_collector_info
from ..schemas import (
    DomainCode,
    GoodsCategory,
    GoodsCollectibleRelationState,
    GoodsLinkedState,
    GoodsStatus,
    OpsCollectorInfoResponse,
    ProductGroupCreateRequest,
    CabinetCameraConnectionTestRequest,
    CabinetCameraConnectionTestResponse,
    CabinetCameraDeleteResponse,
    CabinetCameraDiscoveryItem,
    CabinetCameraItem,
    CabinetCameraUpsertRequest,
    GoodsItemAlbumMasterMapping,
    GoodsItemCollectibleRelation,
    GoodsItemCreateRequest,
    GoodsItemMappingUpdateRequest,
    GoodsItemRelationUpdateRequest,
    GoodsItemResponse,
    GoodsItemSearchResponse,
    GoodsItemUpdateRequest,
)

from ..services import camera as _camera

router = APIRouter()
def _main():
    from app import main as main_module
    return main_module
def _require_admin_request(request: Request) -> None:
    security._require_admin_request(request)
def _require_operator_request(request: Request) -> None:
    security._require_operator_request(request)


def _goods_item_response_from_row(row: dict[str, Any]) -> GoodsItemResponse:
    return GoodsItemResponse(
        id=int(row["id"]),
        category=str(row.get("category") or "").strip().upper(),  # type: ignore[arg-type]
        goods_name=str(row.get("goods_name") or "").strip(),
        description=str(row.get("description") or "").strip() or None,
        quantity=int(row.get("quantity") or 0),
        size_group=str(row.get("size_group") or "GOODS").strip().upper(),  # type: ignore[arg-type]
        storage_slot_id=int(row["storage_slot_id"]) if row.get("storage_slot_id") not in (None, "") else None,
        status=str(row.get("status") or "ACTIVE").strip().upper(),  # type: ignore[arg-type]
        domain_code=str(row.get("domain_code") or "").strip().upper() or None,  # type: ignore[arg-type]
        memory_note=str(row.get("memory_note") or "").strip() or None,
        image_urls=[str(url or "").strip() for url in row.get("image_urls") or [] if str(url or "").strip()],
        primary_image_url=str(row.get("primary_image_url") or "").strip() or None,
        poster_storage_spec=str(row.get("poster_storage_spec") or "").strip() or None,
        tshirt_size=str(row.get("tshirt_size") or "").strip() or None,
        cup_material=str(row.get("cup_material") or "").strip() or None,
        hat_size=str(row.get("hat_size") or "").strip() or None,
        slot_code=str(row.get("slot_code") or "").strip() or None,
        slot_display_name=str(row.get("slot_display_name") or "").strip() or None,
        album_master_mappings=[
            GoodsItemAlbumMasterMapping(
                album_master_id=int(mapping["album_master_id"]),
                title=str(mapping.get("title") or "").strip(),
                artist_or_brand=str(mapping.get("artist_or_brand") or "").strip() or None,
            )
            for mapping in row.get("album_master_mappings") or []
        ],
        artist_mappings=[str(name or "").strip() for name in row.get("artist_mappings") or [] if str(name or "").strip()],
        label_mappings=[str(name or "").strip() for name in row.get("label_mappings") or [] if str(name or "").strip()],
        collectible_relations=[
            GoodsItemCollectibleRelation(
                relation_type=str(relation.get("relation_type") or "").strip().upper(),  # type: ignore[arg-type]
                direction="OUTGOING",
                linked_goods_item_id=int(relation["linked_goods_item_id"]),
                linked_goods_name=str(relation.get("linked_goods_name") or "").strip(),
                linked_category=str(relation.get("linked_category") or "").strip().upper() or None,  # type: ignore[arg-type]
                note=str(relation.get("note") or "").strip() or None,
                display_order=int(relation.get("display_order") or 0),
            )
            for relation in row.get("collectible_relations") or []
        ],
        collectible_relation_count=int(row.get("collectible_relation_count") or 0),
        relation_badges=[str(relation_type or "").strip().upper() for relation_type in row.get("relation_badges") or [] if str(relation_type or "").strip()],
        collectible_relation_preview=[
            GoodsItemCollectibleRelation(
                relation_type=str(relation.get("relation_type") or "").strip().upper(),  # type: ignore[arg-type]
                direction="OUTGOING",
                linked_goods_item_id=int(relation["linked_goods_item_id"]),
                linked_goods_name=str(relation.get("linked_goods_name") or "").strip(),
                linked_category=str(relation.get("linked_category") or "").strip().upper() or None,  # type: ignore[arg-type]
                note=str(relation.get("note") or "").strip() or None,
                display_order=int(relation.get("display_order") or 0),
            )
            for relation in row.get("collectible_relation_preview") or []
        ],
        created_at=str(row.get("created_at") or "").strip(),
        updated_at=str(row.get("updated_at") or "").strip(),
    )


def _require_authenticated_request(request: Request) -> None:
    security._require_authenticated_request(request)


def _cabinet_camera_item_from_row(row: dict[str, Any]) -> CabinetCameraItem:
    description = str(row.get("notes") or "").strip() or None
    return CabinetCameraItem(
        id=int(row["id"]),
        cabinet_name=str(row.get("cabinet_name") or "").strip() or None,
        camera_name=str(row.get("camera_name") or "").strip(),
        description=description,
        onvif_device_url=str(row.get("onvif_device_url") or "").strip() or None,
        snapshot_url=str(row.get("snapshot_url") or "").strip() or None,
        stream_url=str(row.get("stream_url") or "").strip() or None,
        notes=description,
        is_active=bool(row.get("is_active")),
        has_credentials=bool(str(row.get("username") or "").strip() or str(row.get("password") or "").strip()),
        created_at=str(row.get("created_at") or "").strip() or None,
        updated_at=str(row.get("updated_at") or "").strip() or None,
    )



@router.get("/ops/cabinets", include_in_schema=False)
def ops_cabinets_shell(request: Request):
    import hashlib
    v = request.query_params.get("v")
    try:
        file_hash = hashlib.md5((_main().STATIC_DIR / "index.html").read_bytes()).hexdigest()[:8]
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
        return Response(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(_main().STATIC_DIR / "index.html", headers=serve_headers)


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
    _require_operator_request(request)
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
        items=[_goods_item_response_from_row(row) for row in items],
    )


@router.post("/goods-items", response_model=GoodsItemResponse)
def create_goods_item(payload: GoodsItemCreateRequest, request: Request) -> GoodsItemResponse:
    _require_operator_request(request)
    try:
        row = db.create_goods_item(payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return _goods_item_response_from_row(row)


@router.get("/goods-items/{goods_item_id}", response_model=GoodsItemResponse)
def get_goods_item_detail(goods_item_id: int, request: Request) -> GoodsItemResponse:
    _require_operator_request(request)
    row = db.get_goods_item(goods_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _goods_item_response_from_row(row)


@router.patch("/goods-items/{goods_item_id}", response_model=GoodsItemResponse)
def update_goods_item_detail(
    goods_item_id: int,
    payload: GoodsItemUpdateRequest,
    request: Request,
) -> GoodsItemResponse:
    _require_operator_request(request)
    try:
        row = db.update_goods_item(goods_item_id, payload.model_dump(exclude_unset=True))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _goods_item_response_from_row(row)


@router.delete("/goods-items/{goods_item_id}")
def delete_goods_item_detail(goods_item_id: int, request: Request) -> dict[str, Any]:
    _require_operator_request(request)
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
    _require_operator_request(request)
    try:
        row = db.replace_goods_item_mappings(goods_item_id, payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _goods_item_response_from_row(row)


@router.put("/goods-items/{goods_item_id}/relations", response_model=GoodsItemResponse)
def replace_goods_item_collectible_relations(
    goods_item_id: int,
    payload: GoodsItemRelationUpdateRequest,
    request: Request,
) -> GoodsItemResponse:
    _require_operator_request(request)
    try:
        row = db.replace_goods_item_collectible_relations(goods_item_id, payload.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail="goods item not found")
    return _goods_item_response_from_row(row)


@router.get("/goods-targets")
def search_goods_mapping_targets(
    request: Request,
    kind: Literal["artist", "label", "album_master", "collectible"] = Query(...),
    q: str = Query(default=""),
    goods_item_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, list[dict[str, Any]]]:
    _require_operator_request(request)
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
    _require_operator_request(request)
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
    _require_operator_request(request)
    rows = _camera._discover_onvif_devices(timeout_seconds=float(timeout_ms) / 1000.0)
    return [CabinetCameraDiscoveryItem(**row) for row in rows]


@router.post("/cabinet-cameras/test-onvif", response_model=CabinetCameraConnectionTestResponse)
def test_cabinet_camera_connection(
    payload: CabinetCameraConnectionTestRequest,
    request: Request,
) -> CabinetCameraConnectionTestResponse:
    _require_operator_request(request)
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
        result = _camera._test_onvif_camera_connection(
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
    _require_operator_request(request)
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
    snapshot_url = _camera._camera_http_url_or_none(row.get("snapshot_url"))
    stream_url = _camera._camera_rtsp_url_or_none(row.get("stream_url"))
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
            snapshot_bytes = _camera._camera_snapshot_bytes_from_stream(stream_url, username=username or None, password=password or None)
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

# ═══════════════════════════════════════════════════════════════════
# Phase N-3: Collector info + product groups
# ═══════════════════════════════════════════════════════════════════

@router.get("/ops/owned-items/{owned_item_id}/collector-info", response_model=OpsCollectorInfoResponse)
def get_ops_owned_item_collector_info(owned_item_id: int, request: Request) -> OpsCollectorInfoResponse:
    _require_authenticated_request(request)
    payload = _build_ops_owned_item_collector_info_payload(owned_item_id=owned_item_id)
    return OpsCollectorInfoResponse(**payload)


def _build_ops_owned_item_collector_info_payload(owned_item_id: int) -> dict[str, Any]:
    item_id = int(owned_item_id or 0)
    if item_id <= 0:
        return {
            "available": False,
            "owned_item_id": item_id,
            "source_code": None,
            "source_external_id": None,
            "fallback_reason": "INVALID_OWNED_ITEM",
            "fallback_message": "invalid owned_item_id",
            "release_title": None,
            "artist_or_brand": None,
            "country": None,
            "pressing_country": None,
            "label_name": None,
            "catalog_no": None,
            "barcode": None,
            "formats": [],
            "format_items": [],
            "disc_count": None,
            "speed_rpm": None,
            "runout_sample": None,
            "other_versions_count": 0,
            "external_links": [],
        }

    row = db.get_owned_item_detail(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned item not found")

    source_code = str(row.get("source_code") or "").strip().upper() or None
    source_external_id = str(row.get("source_external_id") or "").strip() or None
    if source_code != "DISCOGS" or not source_external_id:
        reason = "MISSING_LINK" if not source_external_id else "UNSUPPORTED_SOURCE"
        message = (
            "collector info is available only for Discogs-linked items."
            if reason == "UNSUPPORTED_SOURCE"
            else "collector info requires a linked Discogs release id."
        )
        return {
            "available": False,
            "owned_item_id": item_id,
            "source_code": source_code,
            "source_external_id": source_external_id,
            "fallback_reason": reason,
            "fallback_message": message,
            "release_title": None,
            "artist_or_brand": None,
            "country": None,
            "pressing_country": None,
            "label_name": None,
            "catalog_no": None,
            "barcode": None,
            "formats": [],
            "format_items": [],
            "disc_count": None,
            "speed_rpm": None,
            "runout_sample": None,
            "other_versions_count": 0,
            "external_links": [],
        }

    try:
        collector_data = get_discogs_release_collector_info(release_id=source_external_id)
    except HTTPException:
        return {
            "available": False,
            "owned_item_id": item_id,
            "source_code": source_code,
            "source_external_id": source_external_id,
            "fallback_reason": "SNAPSHOT_UNAVAILABLE",
            "fallback_message": "Discogs collector data is not available yet.",
            "release_title": None,
            "artist_or_brand": None,
            "country": None,
            "pressing_country": None,
            "label_name": None,
            "catalog_no": None,
            "barcode": None,
            "formats": [],
            "format_items": [],
            "disc_count": None,
            "speed_rpm": None,
            "runout_sample": None,
            "other_versions_count": 0,
            "external_links": [f"https://www.discogs.com/release/{source_external_id}"],
        }

    m = _main()
    raw_formats = collector_data.get("formats") or []
    formats = m._clean_string_list(raw_formats)
    format_items = collector_data.get("format_items")
    if not isinstance(format_items, list):
        format_items = []
    label_items = collector_data.get("label_items")
    if not isinstance(label_items, list):
        label_items = []
    label_name = None
    catalog_no = m._discogs_catalog_no(collector_data.get("catalog_no"))
    for label_row in label_items:
        if not isinstance(label_row, dict):
            continue
        if label_name is None:
            label_name = m._clean_text(label_row.get("name"))
        if catalog_no is None:
            catalog_no = m._discogs_catalog_no(label_row.get("catno"))
        if label_name and catalog_no:
            break
    runout_matrix = [str(v or "").strip() for v in collector_data.get("runout_matrix") or []]
    runout_sample_values = [v for v in runout_matrix if v]
    other_versions = collector_data.get("other_versions")
    other_versions_count = len(other_versions) if isinstance(other_versions, list) else 0
    return {
        "available": True,
        "owned_item_id": item_id,
        "source_code": source_code,
        "source_external_id": source_external_id,
        "release_title": m._clean_text(collector_data.get("title")),
        "artist_or_brand": m._clean_text(collector_data.get("artist_or_brand")),
        "country": m._clean_text(collector_data.get("country")),
        "pressing_country": m._clean_text(collector_data.get("pressing_country")),
        "label_name": label_name,
        "catalog_no": catalog_no,
        "barcode": m._clean_text(collector_data.get("barcode")),
        "formats": formats,
        "format_items": format_items,
        "disc_count": collector_data.get("disc_count"),
        "speed_rpm": collector_data.get("speed_rpm"),
        "runout_sample": " | ".join(runout_sample_values[:2]) if runout_sample_values else None,
        "other_versions_count": other_versions_count,
        "external_links": [f"https://www.discogs.com/release/{source_external_id}"],
        "fallback_reason": None,
        "fallback_message": None,
    }


@router.get("/product-groups")
def list_product_groups(
    request: Request,
    q: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=100),
) -> list[dict[str, Any]]:
    _require_operator_request(request)
    query_text = str(q or "").strip().lower()
    with db.get_conn() as conn:
        if query_text:
            like = f"%{query_text}%"
            rows = conn.execute(
                """
                SELECT id, group_type, group_name, status
                FROM product_group
                WHERE LOWER(group_name) LIKE ?
                  AND status = 'ACTIVE'
                ORDER BY group_name ASC, id ASC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, group_type, group_name, status
                FROM product_group
                WHERE status = 'ACTIVE'
                ORDER BY group_name ASC, id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


@router.post("/product-groups")
def create_product_group(payload: ProductGroupCreateRequest, request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    group_type = str(payload.group_type or "SERIES").strip().upper()
    group_name = str(payload.group_name or "").strip()
    if not group_name:
        raise HTTPException(status_code=400, detail="group_name is required")
    now = db.utc_now_iso()
    with db.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO product_group (
              group_type,
              group_name,
              description,
              status,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (group_type, group_name, payload.description, now, now),
        )
        group_id = cur.lastrowid
    return {"id": group_id, "group_type": group_type, "group_name": group_name}
