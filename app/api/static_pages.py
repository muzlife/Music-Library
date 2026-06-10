"""Static page routes — 13th slice.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from .. import db
from .. import security
from ..schemas import DirectoryPickerRequest, DirectoryPickerResponse, UiImageUploadResponse
from datetime import datetime, timezone
from uuid import uuid4

router = APIRouter()
def _main():
    from app import main as main_module
    return main_module


def _index_file_hash() -> str:
    """md5 of index.html + all css/* + js/* files — changes whenever any static asset changes."""
    import hashlib
    static_dir = _main().STATIC_DIR
    h = hashlib.md5()
    h.update((static_dir / "index.html").read_bytes())
    for css_file in sorted((static_dir / "css").glob("*.css")) if (static_dir / "css").exists() else []:
        h.update(css_file.read_bytes())
    for js_file in sorted((static_dir / "js").glob("*.js")) if (static_dir / "js").exists() else []:
        h.update(js_file.read_bytes())
    return h.hexdigest()[:8]


def _ops_domain_host() -> str:
    """Hostname (no port) that should serve ops.html at '/'.  Set via OPS_DOMAIN env."""
    return os.getenv("OPS_DOMAIN", "").strip().lower()

def _request_is_ops_domain(request: Request) -> bool:
    ops_host = _ops_domain_host()
    if not ops_host:
        return False
    host = request.headers.get("host", "").split(":")[0].lower()
    return host == ops_host


@router.get("/", include_in_schema=False)
def root_entry(request: Request):
    if _main()._auth_enabled() and not _main()._is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    role = _main()._read_auth_role(request)
    if role == _main().AUTH_ROLE_OPERATOR:
        return RedirectResponse("/ops", status_code=303)
    if _request_is_ops_domain(request):
        import hashlib
        v = request.query_params.get("v")
        try:
            file_hash = hashlib.md5((_main().STATIC_DIR / "ops.html").read_bytes()).hexdigest()[:8]
        except Exception:
            file_hash = "0"
        if v != file_hash:
            from starlette.responses import Response as _Resp
            redirect_headers: dict[str, str] = {
                "Location": f"/?v={file_hash}",
                "Cache-Control": "no-store, no-cache, must-revalidate",
            }
            if _main()._is_qa_env():
                redirect_headers["Clear-Site-Data"] = '"cache"'
            return _Resp(status_code=302, headers=redirect_headers)
        serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
        return FileResponse(_main().STATIC_DIR / "ops.html", headers=serve_headers)
    # 비-ops 도메인(library.muzlife.com 등): 역할 무관 index.html 제공
    v = request.query_params.get("v")
    try:
        file_hash = _index_file_hash()
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(_main().STATIC_DIR / "index.html", headers=serve_headers)


@router.get("/ops", include_in_schema=False)
def ops_shell(request: Request):
    import hashlib
    v = request.query_params.get("v")
    try:
        file_hash = hashlib.md5((_main().STATIC_DIR / "ops.html").read_bytes()).hexdigest()[:8]
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(_main().STATIC_DIR / "ops.html", headers=serve_headers)


@router.get("/admin", include_in_schema=False)
def admin_shell(request: Request):
    # /admin은 더 이상 정식 경로가 아님 — 루트(/)로 리다이렉트
    return RedirectResponse("/", status_code=301)


@router.get("/ui", include_in_schema=False)
def ui_alias(request: Request) -> FileResponse:
    v = request.query_params.get("v")
    try:
        file_hash = _index_file_hash()
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ui?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _main()._is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**_main().HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _main()._is_qa_env() else _main().HTML_PROD_CACHE_HEADERS
    return FileResponse(_main().STATIC_DIR / "index.html", headers=serve_headers)


@router.post("/ui/pick-directory", response_model=DirectoryPickerResponse)
def ui_pick_directory(payload: DirectoryPickerRequest) -> DirectoryPickerResponse:
    initial_path = str(payload.initial_path or "").strip() or None
    title = str(payload.title or "음원 폴더 선택").strip() or "음원 폴더 선택"
    try:
        picked = _main()._pick_directory_interactive(title=title, initial_path=initial_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not picked:
        return DirectoryPickerResponse(directory_path=None, cancelled=True)
    return DirectoryPickerResponse(directory_path=picked, cancelled=False)


@router.post("/ui/upload-image", response_model=UiImageUploadResponse)
async def ui_upload_image(file: UploadFile = File(...)) -> UiImageUploadResponse:
    ext = _main()._resolve_image_upload_extension(file.filename, file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="image upload only supports common image formats")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image file")
    if len(raw) > _main().MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="image file is too large (max 20MB)")

    month_bucket = datetime.now(timezone.utc).strftime("%Y%m")
    target_dir = _main().IMAGE_UPLOAD_DIR / month_bucket
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{stamp}_{uuid4().hex[:10]}{ext}"
    target_path = target_dir / file_name
    target_path.write_bytes(raw)

    rel_path = target_path.relative_to(_main().STATIC_DIR).as_posix()
    return UiImageUploadResponse(
        url=f"/ui-static/{rel_path}",
        file_name=file_name,
        file_size_bytes=len(raw),
        content_type=str(file.content_type or "").strip() or None,
    )