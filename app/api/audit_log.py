"""Audit log read API — operator-facing change history endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from .. import db
from .. import security

router = APIRouter(tags=["audit"])


@router.get("/ops/audit-log")
def get_audit_log(
    request: Request,
    entity_type: str | None = Query(default=None, description="owned_item, storage_slot, auth_account"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    security._require_authenticated_request(request)
    result = db.list_audit_log(entity_type=entity_type, limit=limit)
    return {"total_count": result["total_count"], "items": result["items"]}


@router.get("/ops/audit-log/shell", include_in_schema=False)
def audit_log_shell(request: Request):
    security._require_authenticated_request(request)
    import hashlib
    from pathlib import Path
    from fastapi.responses import FileResponse

    def _main():
        from app import main as main_module
        return main_module

    STATIC_DIR = _main().STATIC_DIR
    page_path = STATIC_DIR / "ops_audit_log.html"
    try:
        file_hash = hashlib.md5(page_path.read_bytes()).hexdigest()[:8]
    except Exception:
        file_hash = "0"
    v = request.query_params.get("v")
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops/audit-log/shell?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(page_path, headers=serve_headers)
