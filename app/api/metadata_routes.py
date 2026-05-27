"""Metadata sync routes — ninth slice of main.py -> APIRouter split.
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Path as FastAPIPath, Request
from .. import db
from .. import security
from ..schemas import MetadataSyncRunRequest, MetadataSyncStatusResponse, MetadataSyncItemResult

router = APIRouter()

def _main():
    from app import main as main_module
    return main_module

def _require_admin(request: Request) -> None:
    security._require_admin_request(request)



@router.get("/metadata-sync/status", response_model=MetadataSyncStatusResponse)
def get_metadata_sync_status() -> MetadataSyncStatusResponse:
    running = METADATA_SYNC_LOCK.locked()
    return MetadataSyncStatusResponse(
        auto_enabled=int(settings.metadata_sync_interval_minutes) > 0,
        interval_minutes=int(settings.metadata_sync_interval_minutes),
        batch_limit=int(settings.metadata_sync_batch_limit),
        running=running,
        in_progress_items=list(METADATA_SYNC_IN_PROGRESS_ITEMS) if running else [],
        last_result=METADATA_SYNC_LAST_RESULT,
        last_error=METADATA_SYNC_LAST_ERROR,
    )


@router.post("/metadata-sync/run", status_code=202)
def run_metadata_sync(payload: MetadataSyncRunRequest) -> dict[str, Any]:
    """Start a metadata sync run in the background and return immediately (202).

    Cloudflare (and most proxies) enforce a ~100 s origin timeout, so we must
    not hold the HTTP connection open for the full sync duration.  Callers
    should poll ``GET /metadata-sync/status`` until ``running`` becomes
    ``false``, then read ``last_result`` for the outcome.
    """
    if METADATA_SYNC_LOCK.locked():
        raise HTTPException(status_code=409, detail="metadata sync already running")
    t = threading.Thread(
        target=_run_metadata_sync,
        kwargs={"payload": payload, "fail_when_running": True},
        daemon=True,
        name="metadata-sync-manual",
    )
    t.start()
    return {"started": True}


@router.post("/owned-items/{owned_item_id}/sync-metadata")
def sync_single_item_metadata(owned_item_id: int = FastAPIPath(ge=1)) -> MetadataSyncItemResult:
    """단건 상품 메타 동기화 – 즉시(동기) 실행 후 결과 반환."""
    return _main()._sync_one_item(owned_item_id)