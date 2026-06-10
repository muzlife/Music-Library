"""Discogs integration routes — 12th slice.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from .. import db
from .. import security
from ..schemas import DiscogsIdentityResponse, DiscogsOwnedSyncResponse

router = APIRouter()
import threading
ALADIN_DISCOGS_BACKFILL_LOCK = threading.Lock()
ALADIN_DISCOGS_BACKFILL_THREAD = None

def _main():
    from app import main as main_module
    return main_module
def _require_admin(request: Request) -> None:
    security._require_operator_request(request)



@router.get("/aladin-discogs-backfill/status")
def get_aladin_discogs_backfill_status() -> dict[str, Any]:
    return {
        "running": ALADIN_DISCOGS_BACKFILL_LOCK.locked(),
        "last_result": ALADIN_DISCOGS_BACKFILL_LAST_RESULT,
        "last_error": ALADIN_DISCOGS_BACKFILL_LAST_ERROR,
    }


@router.post("/aladin-discogs-backfill/run")
def run_aladin_discogs_backfill_async(
    dry_run: bool = False,
    sleep_sec: float = 2.0,
) -> dict[str, Any]:
    global ALADIN_DISCOGS_BACKFILL_THREAD
    if ALADIN_DISCOGS_BACKFILL_LOCK.locked():
        raise HTTPException(status_code=409, detail="aladin discogs backfill already running")
    t = threading.Thread(
        target=_main()._aladin_discogs_backfill_thread_worker,
        kwargs={"dry_run": dry_run, "sleep_sec": sleep_sec},
        name="aladin-discogs-backfill",
        daemon=True,
    )
    ALADIN_DISCOGS_BACKFILL_THREAD = t
    t.start()
    return {"status": "started", "dry_run": dry_run, "sleep_sec": sleep_sec}


MANIADB_RELEASE_TYPE_BACKFILL_THREAD: threading.Thread | None = None

@router.get("/backfill/maniadb-release-type/status")
def get_maniadb_release_type_backfill_status() -> dict[str, Any]:
    m = _main()
    running = (
        MANIADB_RELEASE_TYPE_BACKFILL_THREAD is not None
        and MANIADB_RELEASE_TYPE_BACKFILL_THREAD.is_alive()
    )
    return {
        "running": running,
        "result": m.MANIADB_RELEASE_TYPE_BACKFILL_RESULT,
    }


@router.post("/backfill/maniadb-release-type/run")
def run_maniadb_release_type_backfill(
    limit: int = 200,
    sleep_sec: float = 0.3,
) -> dict[str, Any]:
    global MANIADB_RELEASE_TYPE_BACKFILL_THREAD
    m = _main()
    if m.MANIADB_RELEASE_TYPE_BACKFILL_LOCK.locked():
        raise HTTPException(status_code=409, detail="maniadb release_type backfill already running")
    t = threading.Thread(
        target=m._maniadb_release_type_backfill_worker,
        kwargs={"limit": limit, "sleep_sec": sleep_sec},
        name="maniadb-release-type-backfill",
        daemon=True,
    )
    MANIADB_RELEASE_TYPE_BACKFILL_THREAD = t
    t.start()
    return {"status": "started", "limit": limit, "sleep_sec": sleep_sec}


@router.get("/discogs-korean-backfill/status")
def get_discogs_korean_backfill_status() -> dict[str, Any]:
    running = (
        DISCOGS_KOREAN_BACKFILL_THREAD is not None
        and DISCOGS_KOREAN_BACKFILL_THREAD.is_alive()
    )
    return {
        "running": running,
        "result":  DISCOGS_KOREAN_BACKFILL_RESULT,
    }


@router.post("/discogs-korean-backfill/run")
def run_discogs_korean_backfill(limit: int | None = None) -> dict[str, Any]:
    global DISCOGS_KOREAN_BACKFILL_THREAD
    if DISCOGS_KOREAN_BACKFILL_LOCK.locked():
        raise HTTPException(status_code=409, detail="discogs korean backfill already running")
    t = threading.Thread(
        target=_discogs_korean_backfill_worker,
        kwargs={"limit": limit},
        name="discogs-korean-backfill",
        daemon=True,
    )
    DISCOGS_KOREAN_BACKFILL_THREAD = t
    t.start()
    return {"status": "started", "limit": limit}


@router.get("/discogs/identity", response_model=DiscogsIdentityResponse)
def get_discogs_identity() -> DiscogsIdentityResponse:
    ident = discogs_identity()
    if ident is None:
        raise HTTPException(status_code=400, detail="discogs identity unavailable. check DISCOGS_TOKEN.")
    return DiscogsIdentityResponse(**ident)


@router.get("/discogs/release/{release_id}/cover-preview")
def get_discogs_release_cover_preview(
    release_id: str,
    request: Request,
) -> FileResponse:
    _require_admin(request)
    cover_path, media_type = _main()._ensure_discogs_cover_preview(release_id)
    return FileResponse(
        cover_path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/discogs/release/{release_id}/collector-info")
def get_discogs_release_collector_info(
    release_id: str,
    compare_limit: int = 12,
) -> dict[str, Any]:
    snapshot = _main().get_source_release_snapshot(source="DISCOGS", external_id=release_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="discogs release snapshot not found")

    raw = snapshot.get("raw")
    raw_detail = raw if isinstance(raw, dict) else {}

    runout_matrix, other_identifiers, barcode_from_ident, identifier_items = _main()._discogs_identifiers(raw_detail)
    image_items = _main()._discogs_image_items(raw_detail)
    images = [str(item.get("uri") or "") for item in image_items if str(item.get("uri") or "").strip()]
    label_items = _main()._discogs_label_items(raw_detail)
    labels = _main()._discogs_labels(raw_detail)
    credit_items = _main()._discogs_credit_items(raw_detail)
    credits = _main()._discogs_credits(raw_detail)
    company_items = _main()._discogs_company_items(raw_detail)
    companies = _main()._discogs_companies(raw_detail)
    formats = _main()._discogs_format_values(raw_detail)
    format_items = _main()._discogs_format_items(raw_detail)
    track_items = _main()._discogs_track_items(raw_detail)
    track_list_snapshot = snapshot.get("track_list")
    track_list = track_list_snapshot if isinstance(track_list_snapshot, list) else []
    if not track_list and track_items:
        track_list = [str(item.get("display") or "").strip() for item in track_items]
        track_list = [v for v in track_list if v]
    genres = _main()._discogs_string_list(raw_detail.get("genres"))
    styles = _main()._discogs_string_list(raw_detail.get("styles"))
    series: list[str] = []
    series_rows = raw_detail.get("series")
    if isinstance(series_rows, list):
        for row in series_rows:
            if not isinstance(row, dict):
                continue
            name = _main()._discogs_text(row.get("name"))
            catno = _main()._discogs_catalog_no(row.get("catno"))
            if name and catno:
                series.append(f"{name} / {catno}")
            elif name:
                series.append(name)
    master_id = _main()._discogs_text(raw_detail.get("master_id"))
    disc_count_raw = snapshot.get("disc_count")
    speed_rpm_raw = snapshot.get("speed_rpm")
    has_obi_raw = snapshot.get("has_obi")
    try:
        disc_count = int(disc_count_raw) if disc_count_raw is not None else None
    except (TypeError, ValueError):
        disc_count = None
    try:
        speed_rpm = int(speed_rpm_raw) if speed_rpm_raw is not None else None
    except (TypeError, ValueError):
        speed_rpm = None
    has_obi = bool(has_obi_raw) if has_obi_raw is not None else None
    released_date = _main()._discogs_text(snapshot.get("released_date")) or _main()._discogs_text(raw_detail.get("released")) or _main()._discogs_text(raw_detail.get("released_formatted"))
    pressing_country = _main()._discogs_text(snapshot.get("pressing_country")) or _main()._discogs_text(raw_detail.get("country"))

    runout_sample = " | ".join(runout_matrix[:2]) if runout_matrix else None
    selected = {
        "format_name": _main()._discogs_primary_format(raw_detail),
        "label_name": _main()._discogs_text(snapshot.get("label_name")) or (labels[0] if labels else None),
        "catalog_no": _main()._discogs_catalog_no(snapshot.get("catalog_no")),
        "barcode": _main()._discogs_text(snapshot.get("barcode")) or barcode_from_ident,
        "country": _main()._discogs_text(raw_detail.get("country")),
        "release_year": _main()._discogs_release_year(raw_detail),
        "track_count": len(track_list),
        "runout_sample": runout_sample,
    }
    other_versions = _main()._discogs_compare_variants(
        release_id=release_id,
        master_id=master_id,
        selected=selected,
        compare_limit=compare_limit,
    )

    return {
        "release_id": str(release_id).strip(),
        "master_id": master_id,
        "title": _main()._discogs_text(raw_detail.get("title")),
        "artist_or_brand": _main()._discogs_artist_value(raw_detail),
        "release_year": _main()._discogs_release_year(raw_detail),
        "released_date": released_date,
        "country": _main()._discogs_text(raw_detail.get("country")),
        "pressing_country": pressing_country,
        "formats": formats,
        "format_items": format_items,
        "labels": labels,
        "label_items": label_items,
        "catalog_no": _main()._discogs_catalog_no(snapshot.get("catalog_no")),
        "barcode": _main()._discogs_text(snapshot.get("barcode")) or barcode_from_ident,
        "disc_count": disc_count,
        "speed_rpm": speed_rpm,
        "has_obi": has_obi,
        "track_list": track_list,
        "track_items": track_items,
        "credits": credits,
        "credit_items": credit_items,
        "runout_matrix": runout_matrix,
        "other_identifiers": other_identifiers,
        "identifier_items": identifier_items,
        "images": images,
        "image_items": image_items,
        "notes": _main()._discogs_text(raw_detail.get("notes")),
        "companies": companies,
        "company_items": company_items,
        "genres": genres,
        "styles": styles,
        "released": _main()._discogs_text(raw_detail.get("released")) or _main()._discogs_text(raw_detail.get("released_formatted")),
        "series": series,
        "other_versions": other_versions,
    }


@router.post("/discogs/owned-sync/{owned_item_id}", response_model=DiscogsOwnedSyncResponse)
def sync_discogs_owned(owned_item_id: int) -> DiscogsOwnedSyncResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    source_code = str(existing.get("source_code") or "").upper()
    source_external_id = str(existing.get("source_external_id") or "").strip()
    if source_code != "DISCOGS" or not source_external_id:
        raise HTTPException(status_code=400, detail="owned_item is not linked to a discogs release")

    if str(existing.get("status") or "") in {"SOLD", "LOST"}:
        raise HTTPException(status_code=400, detail="cannot sync SOLD/LOST item as owned")

    result = discogs_add_release_to_collection(release_id=source_external_id, folder_id=1)
    if result is None:
        raise HTTPException(status_code=400, detail="discogs collection sync failed")

    return DiscogsOwnedSyncResponse(
        owned_item_id=owned_item_id,
        source_external_id=source_external_id,
        username=str(result.get("username") or ""),
        synced=True,
    )