"""Operator home routes — seventh slice of main.py -> APIRouter split.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services import home_env as _home_env
from .. import db
from .. import security
from ..security import _require_operator_request
from ..schemas import (
    ClimateCompareResponse,
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
    security._require_operator_request(request)


def apply_music_detail_fallbacks(
    detail: dict[str, Any],
    owned_item_id: int,
    album_master_id: int | None,
    source_code: str | None,
    source_external_id: str | None
) -> dict[str, Any]:
    snapshot = None
    if source_code and source_external_id:
        try:
            from app.services.providers import get_source_release_snapshot
            snapshot = get_source_release_snapshot(source_code, source_external_id)
        except Exception:
            pass

    if snapshot:
        if not detail.get("barcode"):
            detail["barcode"] = snapshot.get("barcode")
        if not detail.get("catalog_no"):
            from app.main import _discogs_catalog_no
            detail["catalog_no"] = _discogs_catalog_no(snapshot.get("catalog_no"))
        if not detail.get("label_name"):
            detail["label_name"] = snapshot.get("label_name")
        if not detail.get("released_date"):
            detail["released_date"] = snapshot.get("released_date")
        if not detail.get("pressing_country"):
            detail["pressing_country"] = snapshot.get("pressing_country")
        if not detail.get("cover_image_url"):
            detail["cover_image_url"] = snapshot.get("cover_image_url")
        if not detail.get("track_list"):
            detail["track_list"] = snapshot.get("track_list") or []
        if not detail.get("track_items"):
            detail["track_items"] = snapshot.get("track_items") or []

    if not detail.get("track_list") and album_master_id:
        try:
            from app.db import get_sibling_tracklist
            sibling = get_sibling_tracklist(album_master_id, owned_item_id)
            if sibling:
                import json
                track_list = []
                if sibling.get("track_list_json"):
                    try:
                        t_list = json.loads(sibling["track_list_json"])
                        if isinstance(t_list, list):
                            track_list = t_list
                    except Exception:
                        pass
                track_items = []
                if sibling.get("track_items_json"):
                    try:
                        t_items = json.loads(sibling["track_items_json"])
                        if isinstance(t_items, list):
                            track_items = t_items
                    except Exception:
                        pass
                detail["track_list"] = track_list
                detail["track_items"] = track_items
        except Exception:
            pass

    return detail


def _map_ops_home_recent_item(row: dict[str, Any]) -> OpsHomeRecentItem:
    category_code = str(row.get("category") or "")
    owned_item_id = int(row.get("owned_item_id") or row.get("id") or 0)
    
    if category_code in ("LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"):
        m_detail = {
            "barcode": row.get("barcode"),
            "catalog_no": row.get("catalog_no"),
            "label_name": row.get("label_name"),
            "released_date": row.get("released_date"),
            "pressing_country": row.get("pressing_country"),
            "cover_image_url": row.get("cover_image_url"),
            "track_list": row.get("track_list") or [],
            "track_items": row.get("track_items") or [],
        }
        m_detail = apply_music_detail_fallbacks(
            detail=m_detail,
            owned_item_id=owned_item_id,
            album_master_id=row.get("linked_album_master_id"),
            source_code=row.get("source_code"),
            source_external_id=row.get("source_external_id"),
        )
        row["barcode"] = m_detail["barcode"]
        row["catalog_no"] = m_detail["catalog_no"]
        row["label_name"] = m_detail["label_name"]
        row["released_date"] = m_detail["released_date"]
        row["pressing_country"] = m_detail["pressing_country"]
        row["cover_image_url"] = m_detail["cover_image_url"]
        row["track_list"] = m_detail["track_list"]
        row["track_items"] = m_detail["track_items"]
        
    return OpsHomeRecentItem(**row)


@router.get("/operator/catalog-search", response_model=OperatorCatalogSearchResponse)
def operator_catalog_search(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> OperatorCatalogSearchResponse:
    security._require_authenticated_request(request)
    rows = db.search_operator_catalog(query_text=q, limit=limit)
    items: list[OperatorCatalogSearchItem] = []
    for row in rows:
        row_dict = dict(row)
        category_code = str(row_dict.get("category") or "")
        owned_item_id = int(row_dict.get("id") or 0)
        
        if category_code in ("LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"):
            m_detail = {
                "barcode": row_dict.get("barcode"),
                "catalog_no": row_dict.get("catalog_no"),
                "label_name": row_dict.get("label_name"),
                "released_date": row_dict.get("released_date"),
                "pressing_country": row_dict.get("pressing_country"),
                "cover_image_url": row_dict.get("cover_image_url"),
                "track_list": row_dict.get("track_list") or [],
                "track_items": row_dict.get("track_items") or [],
            }
            m_detail = apply_music_detail_fallbacks(
                detail=m_detail,
                owned_item_id=owned_item_id,
                album_master_id=row_dict.get("linked_album_master_id"),
                source_code=row_dict.get("source_code"),
                source_external_id=row_dict.get("source_external_id"),
            )
            row_dict["barcode"] = m_detail["barcode"]
            row_dict["catalog_no"] = m_detail["catalog_no"]
            row_dict["label_name"] = m_detail["label_name"]
            row_dict["released_date"] = m_detail["released_date"]
            row_dict["pressing_country"] = m_detail["pressing_country"]
            row_dict["cover_image_url"] = m_detail["cover_image_url"]
            row_dict["track_list"] = m_detail["track_list"]
            row_dict["track_items"] = m_detail["track_items"]

        runout_values = [str(v or "").strip() for v in row_dict.get("runout_matrix") or [] if str(v or "").strip()]
        _item_dc = str(row_dict.get("item_domain_code") or "").strip() or None
        _master_dc = str(row_dict.get("master_domain_code") or "").strip() or None
        _override_dc = str(row_dict.get("override_domain_code") or "").strip() or None
        _effective_dc = _item_dc or _master_dc or None
        _am_id = int(row_dict.get("linked_album_master_id") or 0) or None
        _sort_artist = str(row_dict.get("master_sort_artist_name") or "").strip() or None
        items.append(
            OperatorCatalogSearchItem(
                owned_item_id=owned_item_id,
                label_id=_main()._build_label_id(category_code, owned_item_id),
                category=category_code,
                format_name=row_dict.get("format_name"),
                item_title=row_dict.get("item_title") or row_dict.get("item_name_override"),
                product_title=row_dict.get("product_title"),
                artist_or_brand=row_dict.get("artist_or_brand"),
                released_date=row_dict.get("released_date"),
                pressing_country=row_dict.get("pressing_country"),
                label_name=row_dict.get("label_name"),
                catalog_no=_main()._discogs_catalog_no(row_dict.get("catalog_no")),
                barcode=row_dict.get("barcode"),
                format_items=row_dict.get("format_items") or [],
                runout_sample=" | ".join(runout_values[:2]) if runout_values else None,
                cover_image_url=row_dict.get("cover_image_url"),
                signature_type=str(row_dict.get("signature_type") or "NONE"),
                status=str(row_dict.get("status") or "IN_COLLECTION"),
                current_slot_code=row_dict.get("current_slot_code"),
                current_slot_display_name=row_dict.get("current_slot_display_name"),
                current_cabinet_name=row_dict.get("current_cabinet_name"),
                current_column_code=row_dict.get("current_column_code"),
                current_cell_code=row_dict.get("current_cell_code"),
                previous_slot_code=row_dict.get("previous_slot_code"),
                previous_slot_display_name=row_dict.get("previous_slot_display_name"),
                created_at=str(row_dict.get("created_at") or "").strip() or None,
                track_matches=row_dict.get("track_matches") or [],
                matched_track_count=int(row_dict.get("matched_track_count") or 0),
                track_items=row_dict.get("track_items") or [],
                track_list=row_dict.get("track_list") or [],
                album_master_id=_am_id,
                effective_domain_code=_effective_dc,
                master_domain_code=_master_dc,
                override_domain_code=_override_dc,
                sort_artist_name=_sort_artist,
                review_text=str(row_dict.get("review_text") or "").strip() or None,
                review_source=str(row_dict.get("review_source") or "").strip() or None,
                spotify_album_id=str(row_dict.get("spotify_album_id") or "").strip() or None,
                has_local_link=bool(row_dict.get("has_local_link")),
            )
        )
    return OperatorCatalogSearchResponse(query=q, total_count=len(items), items=items)


@router.get("/operator/home/recent", response_model=OpsHomeRecentSectionsResponse)
def operator_home_recent_sections(request: Request) -> OpsHomeRecentSectionsResponse:
    security._require_authenticated_request(request)
    data = db.get_ops_home_recent_sections()
    return OpsHomeRecentSectionsResponse(
        recent_moved_items=[_map_ops_home_recent_item(dict(row)) for row in data.get("recent_moved_items") or []],
        recent_registered_items=[_map_ops_home_recent_item(dict(row)) for row in data.get("recent_registered_items") or []],
        recent_moved_total_count=int(data.get("recent_moved_total_count") or 0),
        recent_registered_total_count=int(data.get("recent_registered_total_count") or 0),
    )


@router.get("/operator/home/feed", response_model=OpsHomeFeedResponse)
def operator_home_feed(
    request: Request,
    kind: Literal["registered", "moved", "purchased", "unslotted"] = Query("registered"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
) -> OpsHomeFeedResponse:
    security._require_authenticated_request(request)
    data = db.get_ops_home_feed(kind=kind, page=page, limit=limit)
    return OpsHomeFeedResponse(
        kind=str(data.get("kind") or "registered"),
        page=int(data.get("page") or page),
        limit=int(data.get("limit") or limit),
        total_count=int(data.get("total_count") or 0),
        items=[_map_ops_home_recent_item(dict(row)) for row in data.get("items") or []],
    )



@router.get("/operator/climate-compare", response_model=ClimateCompareResponse)
def operator_climate_compare(request: Request) -> ClimateCompareResponse:
    security._require_authenticated_request(request)
    indoor = None
    outdoor = None
    # Try indoor
    try:
        indoor = _home_env._load_operator_office_climate()
        if indoor.get("available"):
            _home_env._OFFICE_CLIMATE_CACHE = dict(indoor)
    except Exception:
        indoor = _home_env._OFFICE_CLIMATE_CACHE
    # Try outdoor
    try:
        outdoor = _home_env._load_operator_seoul_weather()
        if outdoor.get("available"):
            _home_env._SEOUL_WEATHER_CACHE = dict(outdoor)
    except Exception:
        outdoor = _home_env._SEOUL_WEATHER_CACHE

    indoor_t = indoor.get("temperature_c") if indoor else None
    indoor_h = indoor.get("humidity_percent") if indoor else None

    return ClimateCompareResponse(
        indoor_available=bool(indoor and indoor.get("available")),
        indoor_temperature_c=float(indoor_t) if indoor_t is not None else None,
        indoor_humidity_percent=float(indoor_h) if indoor_h is not None else None,
        indoor_comfort_label=str(indoor.get("comfort_label") or "") if indoor else None,
        outdoor_available=bool(outdoor and outdoor.get("available")),
        outdoor_temperature_c=float(outdoor.get("temperature_c")) if outdoor and outdoor.get("temperature_c") is not None else None,
        outdoor_humidity_percent=float(outdoor.get("humidity_percent")) if outdoor and outdoor.get("humidity_percent") is not None else None,
        outdoor_weather_desc=outdoor.get("description") if outdoor else None,
        outdoor_temperature_high_c=float(outdoor.get("temperature_high_c")) if outdoor and outdoor.get("temperature_high_c") is not None else None,
        outdoor_temperature_low_c=float(outdoor.get("temperature_low_c")) if outdoor and outdoor.get("temperature_low_c") is not None else None,
        updated_at=outdoor.get("updated_at") if outdoor else None,
    )


@router.get("/operator/office-climate", response_model=OfficeClimateResponse)
def operator_office_climate(request: Request) -> OfficeClimateResponse:
    security._require_authenticated_request(request)
    try:
        payload = _home_env._load_operator_office_climate()
        if bool(payload.get("available")):
            _home_env._OFFICE_CLIMATE_CACHE = dict(payload)
            return OfficeClimateResponse(**payload)
    except Exception:
        if _home_env._OFFICE_CLIMATE_CACHE:
            return OfficeClimateResponse(**_home_env._OFFICE_CLIMATE_CACHE)
    try:
        payload = _home_env._load_operator_seoul_weather()
        if bool(payload.get("available")):
            _home_env._SEOUL_WEATHER_CACHE = dict(payload)
            return OfficeClimateResponse(**payload)
    except Exception:
        if _home_env._SEOUL_WEATHER_CACHE:
            return OfficeClimateResponse(**_home_env._SEOUL_WEATHER_CACHE)
    return OfficeClimateResponse(
        available=False,
        source="seoul_weather",
        location_label="서울",
        description="",
    )


@router.get("/operator/customer-requests", response_model=CustomerTrackRequestListResponse)
def get_customer_track_requests(
    request: Request,
    status: str | None = Query(default=None, pattern="^(REQUESTED|PLAYING|RETURNED|CANCELLED)$"),
    limit: int = Query(default=50, ge=1, le=300),
) -> CustomerTrackRequestListResponse:
    security._require_authenticated_request(request)
    rows = db.list_customer_track_requests(status=status, limit=limit)
    items = [_main()._map_to_customer_track_request_item(row) for row in rows]
    return CustomerTrackRequestListResponse(total_count=db.count_customer_track_requests(status=status), items=items)


@router.get("/operator/roon/status", response_model=RoonStatusResponse)
def get_roon_status(request: Request) -> RoonStatusResponse:
    security._require_authenticated_request(request)
    return RoonStatusResponse(
        connected=_main()._ROON_CONNECTED,
        core_name=_main()._ROON_CORE_NAME,
        active_zone=_main()._ROON_ACTIVE_ZONE,
        volume=_main()._ROON_VOLUME,
        now_playing_request_id=_main()._ROON_NOW_PLAYING_REQUEST_ID,
    )


@router.post("/operator/roon/status/update", response_model=RoonStatusResponse)
def update_roon_status(payload: RoonStatusUpdateRequest, request: Request) -> RoonStatusResponse:
    _require_operator_request(request)
    if payload.connected is not None:
        _main()._ROON_CONNECTED = payload.connected
    if payload.active_zone is not None:
        _main()._ROON_ACTIVE_ZONE = payload.active_zone
    if payload.volume is not None:
        _main()._ROON_VOLUME = payload.volume
    if payload.now_playing_request_id is not None:
        _main()._ROON_NOW_PLAYING_REQUEST_ID = payload.now_playing_request_id
    return get_roon_status(request)


@router.post("/operator/roon/play/{request_id}", response_model=CustomerTrackRequestItem)
def play_track_via_roon(request_id: int, request: Request) -> CustomerTrackRequestItem:
    _require_operator_request(request)
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
def get_now_playing_requests(request: Request) -> list[CustomerTrackRequestItem]:
    security._require_authenticated_request(request)
    rows = db.list_customer_track_requests(status="PLAYING", limit=10)
    return [_main()._map_to_customer_track_request_item(row) for row in rows]


@router.post("/operator/customer-requests", response_model=CustomerTrackRequestItem)
def create_customer_track_request(
    payload: CustomerTrackRequestCreate,
    request: Request,
) -> CustomerTrackRequestItem:
    session = security._read_auth_session_data(request) or {}

    weather_temp_c = None
    weather_desc = None
    w_code = None

    w_data = None
    if _home_env._SEOUL_WEATHER_CACHE and _home_env._SEOUL_WEATHER_CACHE.get("available"):
        w_data = _home_env._SEOUL_WEATHER_CACHE
    elif _home_env._OFFICE_CLIMATE_CACHE and _home_env._OFFICE_CLIMATE_CACHE.get("available"):
        w_data = _home_env._OFFICE_CLIMATE_CACHE
    else:
        try:
            w_data = _home_env._load_operator_seoul_weather()
        except Exception:
            w_data = None

    if w_data and w_data.get("available"):
        weather_temp_c = w_data.get("temperature_c")
        w_code = w_data.get("weather_code")
        weather_desc = _home_env._wmo_weather_code_to_desc(w_code)

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
    session = security._read_auth_session_data(request) or {}
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
    _require_operator_request(request)
    result = _main().artist_context_service.build_artist_context(
        payload.artist_name,
        category=payload.category,
        locale=payload.locale,
    )
    return ArtistContextResponse(**result)


@router.get("/ops/cafe", include_in_schema=False)
@router.get("/ops/cafe/", include_in_schema=False)
def ops_cafe_shell(request: Request):
    security._require_authenticated_request(request)
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


class MetadataCorrectionSuggestion(BaseModel):
    item_title: str | None = None
    artist_or_brand: str | None = None
    barcode: str | None = None
    catalog_no: str | None = None
    label_name: str | None = None
    released_date: str | None = None
    track_list: list[str] | None = None
    reason: str | None = None


@router.post("/operator/suggest-correction/{owned_item_id}")
def suggest_metadata_correction(
    owned_item_id: int,
    payload: MetadataCorrectionSuggestion,
    request: Request,
):
    security._require_operator_request(request)
    row = db.get_owned_item_detail(owned_item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Owned item not found")

    username = security._read_auth_username(request) or "operator"
    
    batch_id = db.insert_batch(
        ingest_source="OPERATOR_CORRECTION",
        created_by=username,
        notes=f"Correction suggestion for Item #{owned_item_id} ({row.get('item_title')})",
    )
    
    import json
    payload_data = {
        "owned_item_id": owned_item_id,
        "suggested_changes": {
            k: v for k, v in payload.model_dump().items() if v is not None
        },
        "original_data": {
            "item_title": row.get("item_title") or row.get("item_name_override"),
            "artist_or_brand": row.get("artist_or_brand"),
            "barcode": row.get("barcode"),
            "catalog_no": row.get("catalog_no"),
            "label_name": row.get("label_name"),
            "released_date": row.get("released_date"),
            "track_list": row.get("track_list") or [],
        }
    }
    
    db.insert_review_queue(
        batch_id=batch_id,
        row_no=1,
        category=row.get("category"),
        payload=payload_data,
        candidate=None,
        confidence=0.5,
        review_status="NEEDS_REVIEW",
        review_note=payload.reason or "Operator requested metadata correction",
    )
    return {"ok": True, "batch_id": batch_id}
