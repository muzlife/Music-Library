"""Operator home routes — seventh slice of main.py -> APIRouter split.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import db
from .. import security
from ..schemas import (
    ArtistContextRequest,
    ArtistContextResponse,
    CustomerTrackRequestCreate,
    CustomerTrackRequestItem,
    CustomerTrackRequestListResponse,
    CustomerTrackRequestUpdate,
    OfficeClimateResponse,
    OperatorCatalogSearchResponse,
    OpsHomeFeedResponse,
    OpsHomeRecentItem,
    OpsHomeRecentSectionsResponse,
    OperatorCatalogSearchItem,
    RoonStatusResponse,
)

router = APIRouter()


class RoonStatusUpdateRequest(BaseModel):
    connected: bool | None = None
    active_zone: str | None = None
    volume: int | None = None
    now_playing_request_id: int | None = None


def _main():
    from app import main as main_module
    return main_module


def _require_auth(request: Request) -> None:
    security._require_authenticated_request(request)



@router.get("/operator/catalog-search", response_model=OperatorCatalogSearchResponse)
def operator_catalog_search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> OperatorCatalogSearchResponse:
    rows = db.search_operator_catalog(query_text=q, limit=limit)
    items: list[OperatorCatalogSearchItem] = []
    for row in rows:
        category_code = str(row.get("category") or "")
        owned_item_id = int(row.get("id") or 0)
        runout_values = [str(v or "").strip() for v in row.get("runout_matrix") or [] if str(v or "").strip()]
        _item_dc = str(row.get("item_domain_code") or "").strip() or None
        _master_dc = str(row.get("master_domain_code") or "").strip() or None
        _override_dc = str(row.get("override_domain_code") or "").strip() or None
        _effective_dc = _item_dc or _master_dc or None
        _am_id = int(row.get("linked_album_master_id") or 0) or None
        _sort_artist = str(row.get("master_sort_artist_name") or "").strip() or None
        items.append(
            OperatorCatalogSearchItem(
                owned_item_id=owned_item_id,
                label_id=_main()._build_label_id(category_code, owned_item_id),
                category=category_code,
                format_name=row.get("format_name"),
                item_title=row.get("item_title") or row.get("item_name_override"),
                artist_or_brand=row.get("artist_or_brand"),
                released_date=row.get("released_date"),
                pressing_country=row.get("pressing_country"),
                label_name=row.get("label_name"),
                catalog_no=_main()._discogs_catalog_no(row.get("catalog_no")),
                barcode=row.get("barcode"),
                format_items=row.get("format_items") or [],
                runout_sample=" | ".join(runout_values[:2]) if runout_values else None,
                cover_image_url=row.get("cover_image_url"),
                signature_type=str(row.get("signature_type") or "NONE"),
                status=str(row.get("status") or "IN_COLLECTION"),
                current_slot_code=row.get("current_slot_code"),
                current_slot_display_name=row.get("current_slot_display_name"),
                current_cabinet_name=row.get("current_cabinet_name"),
                current_column_code=row.get("current_column_code"),
                current_cell_code=row.get("current_cell_code"),
                previous_slot_code=row.get("previous_slot_code"),
                previous_slot_display_name=row.get("previous_slot_display_name"),
                created_at=str(row.get("created_at") or "").strip() or None,
                track_matches=row.get("track_matches") or [],
                matched_track_count=int(row.get("matched_track_count") or 0),
                track_items=row.get("track_items") or [],
                track_list=row.get("track_list") or [],
                album_master_id=_am_id,
                effective_domain_code=_effective_dc,
                master_domain_code=_master_dc,
                override_domain_code=_override_dc,
                sort_artist_name=_sort_artist,
            )
        )
    return OperatorCatalogSearchResponse(query=q, total_count=len(items), items=items)


@router.get("/operator/home/recent", response_model=OpsHomeRecentSectionsResponse)
def operator_home_recent_sections() -> OpsHomeRecentSectionsResponse:
    data = db.get_ops_home_recent_sections()
    return OpsHomeRecentSectionsResponse(
        recent_moved_items=[OpsHomeRecentItem(**row) for row in data.get("recent_moved_items") or []],
        recent_registered_items=[OpsHomeRecentItem(**row) for row in data.get("recent_registered_items") or []],
        recent_moved_total_count=int(data.get("recent_moved_total_count") or 0),
        recent_registered_total_count=int(data.get("recent_registered_total_count") or 0),
    )


@router.get("/operator/home/feed", response_model=OpsHomeFeedResponse)
def operator_home_feed(
    kind: Literal["registered", "moved", "purchased", "unslotted"] = Query("registered"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
) -> OpsHomeFeedResponse:
    data = db.get_ops_home_feed(kind=kind, page=page, limit=limit)
    return OpsHomeFeedResponse(
        kind=str(data.get("kind") or "registered"),
        page=int(data.get("page") or page),
        limit=int(data.get("limit") or limit),
        total_count=int(data.get("total_count") or 0),
        items=[OpsHomeRecentItem(**row) for row in data.get("items") or []],
    )


@router.get("/operator/office-climate", response_model=OfficeClimateResponse)
def operator_office_climate() -> OfficeClimateResponse:

    try:
        payload = _main()._load_operator_office_climate()
        if bool(payload.get("available")):
            _main()._OFFICE_CLIMATE_CACHE = dict(payload)
            return OfficeClimateResponse(**payload)
    except Exception:
        if _main()._OFFICE_CLIMATE_CACHE:
            return OfficeClimateResponse(**_main()._OFFICE_CLIMATE_CACHE)
    try:
        payload = _main()._load_operator_seoul_weather()
        if bool(payload.get("available")):
            _main()._SEOUL_WEATHER_CACHE = dict(payload)
            return OfficeClimateResponse(**payload)
    except Exception:
        if _main()._SEOUL_WEATHER_CACHE:
            return OfficeClimateResponse(**_main()._SEOUL_WEATHER_CACHE)
    return OfficeClimateResponse(
        available=False,
        source="seoul_weather",
        location_label="서울",
        description="",
    )


@router.get("/operator/customer-requests", response_model=CustomerTrackRequestListResponse)
def get_customer_track_requests(
    status: str | None = Query(default=None, pattern="^(REQUESTED|PLAYING|RETURNED|CANCELLED)$"),
    limit: int = Query(default=50, ge=1, le=300),
) -> CustomerTrackRequestListResponse:
    rows = db.list_customer_track_requests(status=status, limit=limit)
    items = [_main()._map_to_customer_track_request_item(row) for row in rows]
    return CustomerTrackRequestListResponse(total_count=db.count_customer_track_requests(status=status), items=items)


@router.get("/operator/roon/status", response_model=RoonStatusResponse)
def get_roon_status() -> RoonStatusResponse:

    return RoonStatusResponse(
        connected=_main()._ROON_CONNECTED,
        core_name=_main()._ROON_CORE_NAME,
        active_zone=_main()._ROON_ACTIVE_ZONE,
        volume=_main()._ROON_VOLUME,
        now_playing_request_id=_main()._ROON_NOW_PLAYING_REQUEST_ID,
    )


@router.post("/operator/roon/status/update", response_model=RoonStatusResponse)
def update_roon_status(payload: RoonStatusUpdateRequest) -> RoonStatusResponse:

    if payload.connected is not None:
        _main()._ROON_CONNECTED = payload.connected
    if payload.active_zone is not None:
        _main()._ROON_ACTIVE_ZONE = payload.active_zone
    if payload.volume is not None:
        _main()._ROON_VOLUME = payload.volume
    if payload.now_playing_request_id is not None:
        _main()._ROON_NOW_PLAYING_REQUEST_ID = payload.now_playing_request_id
    return get_roon_status()


@router.post("/operator/roon/play/{request_id}", response_model=CustomerTrackRequestItem)
def play_track_via_roon(request_id: int) -> CustomerTrackRequestItem:

    row = db.get_customer_track_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Track request not found")
    
    updated = db.update_customer_track_request(
        request_id,
        status="PLAYING",
        playback_deck="Roon (Stream)"
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update track request")
    
    _main()._ROON_NOW_PLAYING_REQUEST_ID = request_id
    return _main()._map_to_customer_track_request_item(updated)


@router.get("/operator/customer-requests/now-playing", response_model=list[CustomerTrackRequestItem])
def get_now_playing_requests() -> list[CustomerTrackRequestItem]:
    rows = db.list_customer_track_requests(status="PLAYING", limit=10)
    return [_main()._map_to_customer_track_request_item(row) for row in rows]


@router.post("/operator/customer-requests", response_model=CustomerTrackRequestItem)
def create_customer_track_request(
    payload: CustomerTrackRequestCreate,
    request: Request,
) -> CustomerTrackRequestItem:
    session = _main()._read_auth_session_data(request) or {}

    weather_temp_c = None
    weather_desc = None
    w_code = None

    w_data = None
    if _main()._SEOUL_WEATHER_CACHE and _SEOUL_WEATHER_CACHE.get("available"):
        w_data = _main()._SEOUL_WEATHER_CACHE
    elif _main()._OFFICE_CLIMATE_CACHE and _OFFICE_CLIMATE_CACHE.get("available"):
        w_data = _main()._OFFICE_CLIMATE_CACHE
    else:
        try:
            w_data = _main()._load_operator_seoul_weather()
        except Exception:
            w_data = None

    if w_data and w_data.get("available"):
        weather_temp_c = w_data.get("temperature_c")
        w_code = w_data.get("weather_code")
        weather_desc = _main()._wmo_weather_code_to_desc(w_code)

    row = db.create_customer_track_request(
        requested_track=payload.requested_track,
        requested_by=str(session.get("username") or "").strip() or None,
        owned_item_id=payload.owned_item_id,
        matched_track_title=payload.matched_track_title,
        matched_track_no=payload.matched_track_no,
        customer_note=payload.customer_note,
        weather_temp_c=weather_temp_c,
        weather_description=weather_desc,
        weather_code=w_code,
    )
    if not row:
        raise HTTPException(status_code=500, detail="customer request create failed")
    return _main()._map_to_customer_track_request_item(row)


@router.patch("/operator/customer-requests/{request_id}", response_model=CustomerTrackRequestItem)
def patch_customer_track_request(
    request_id: int,
    payload: CustomerTrackRequestUpdate,
    request: Request,
) -> CustomerTrackRequestItem:
    session = _main()._read_auth_session_data(request) or {}
    row = db.update_customer_track_request(
        request_id=request_id,
        status=payload.status,
        response_note=payload.response_note,
        handled_by=str(session.get("username") or "").strip() or None,
        playback_deck=payload.playback_deck,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="customer request not found")
    return _main()._map_to_customer_track_request_item(row)

# ═══════════════════════════════════════════════════════════════════
# Phase N-1: operator_artist_context + ops_cafe_shell
# ═══════════════════════════════════════════════════════════════════

@router.post("/ops/artist-context", response_model=ArtistContextResponse)
def operator_artist_context(
    payload: ArtistContextRequest,
    request: Request,
) -> ArtistContextResponse:
    _require_auth(request)
    result = _main().artist_context_service.build_artist_context(
        payload.artist_name,
        category=payload.category,
        locale=payload.locale,
    )
    return ArtistContextResponse(**result)


@router.get("/ops/cafe", include_in_schema=False)
def ops_cafe_shell(request: Request):
    import hashlib
    v = request.query_params.get("v")
    STATIC_DIR = _main().STATIC_DIR
    try:
        file_hash = hashlib.md5((STATIC_DIR / "ops_cafe.html").read_bytes()).hexdigest()[:8]
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops/cafe?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "ops_cafe.html", headers=serve_headers)
