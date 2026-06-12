"""Static page routes — 13th slice.
"""
from __future__ import annotations
import os
import platform
import subprocess
from pathlib import Path
from typing import Any
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from .. import db
from .. import security
from ..security import _auth_enabled, _is_authenticated, _read_auth_role, AUTH_ROLE_OPERATOR
from ..schemas import DirectoryPickerRequest, DirectoryPickerResponse, UiImageUploadResponse
from ..services.site import (
    STATIC_DIR,
    IMAGE_UPLOAD_DIR,
    MAX_IMAGE_UPLOAD_BYTES,
    HTML_NO_CACHE_HEADERS,
    HTML_PROD_CACHE_HEADERS,
    _is_qa_env,
)
from ..services.discogs_mapper import ALLOWED_IMAGE_CONTENT_TYPES
from datetime import datetime, timezone
from uuid import uuid4

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".bmp", ".tif", ".tiff", ".heic", ".heif",
}

router = APIRouter()


def _pick_directory_via_osascript(title: str, initial_path: str | None = None) -> str | None:
    safe_title = str(title or "폴더 선택").replace('"', '\\"')
    script_lines: list[str] = []
    init = Path(initial_path).expanduser() if initial_path else None
    if init and init.exists() and init.is_dir():
        safe_init = str(init).replace('"', '\\"')
        script_lines.extend([
            f'set _defaultLocation to POSIX file "{safe_init}"',
            f'set _pickedFolder to choose folder with prompt "{safe_title}" default location _defaultLocation',
            "POSIX path of _pickedFolder",
        ])
    else:
        script_lines.extend([
            f'set _pickedFolder to choose folder with prompt "{safe_title}"',
            "POSIX path of _pickedFolder",
        ])
    cmd = ["osascript"]
    for line in script_lines:
        cmd.extend(["-e", line])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        picked = str(proc.stdout or "").strip()
        return picked or None
    err_text = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
    if "user canceled" in err_text or "-128" in err_text:
        return None
    raise RuntimeError(f"directory picker failed: {(proc.stderr or proc.stdout or 'unknown error').strip()}")


def _pick_directory_via_tk(title: str, initial_path: str | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("directory picker backend not available") from exc
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            parent=root,
            title=title or "폴더 선택",
            initialdir=str(Path(initial_path).expanduser()) if initial_path else None,
            mustexist=True,
        )
    finally:
        root.destroy()
    selected = str(selected or "").strip()
    return selected or None


def _pick_directory_interactive(title: str, initial_path: str | None = None) -> str | None:
    system_name = platform.system().lower()
    if system_name == "darwin":
        return _pick_directory_via_osascript(title=title, initial_path=initial_path)
    return _pick_directory_via_tk(title=title, initial_path=initial_path)


def _resolve_image_upload_extension(file_name: str | None, content_type: str | None) -> str | None:
    ext = Path(str(file_name or "")).suffix.lower().strip()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return ext
    normalized_content_type = str(content_type or "").strip().lower()
    return ALLOWED_IMAGE_CONTENT_TYPES.get(normalized_content_type)


_INDEX_HASH_CACHE: dict[tuple, str] = {}
_OPS_HASH_CACHE: dict[float, str] = {}
_OPS_REVAMP_HASH_CACHE: dict[float, str] = {}


def _collect_index_mtimes() -> tuple:
    mtimes: list[int] = []
    index_path = STATIC_DIR / "index.html"
    mtimes.append(index_path.stat().st_mtime_ns if index_path.exists() else 0)
    css_dir = STATIC_DIR / "css"
    if css_dir.exists():
        for f in sorted(css_dir.glob("*.css")):
            mtimes.append(f.stat().st_mtime_ns)
    js_dir = STATIC_DIR / "js"
    if js_dir.exists():
        for f in sorted(js_dir.glob("*.js")):
            mtimes.append(f.stat().st_mtime_ns)
    return tuple(mtimes)


def _index_file_hash() -> str:
    """md5 of index.html + all css/* + js/* files — changes whenever any static asset changes."""
    import hashlib
    mtime_key = _collect_index_mtimes()
    if mtime_key in _INDEX_HASH_CACHE:
        return _INDEX_HASH_CACHE[mtime_key]
    h = hashlib.md5()
    h.update((STATIC_DIR / "index.html").read_bytes())
    for css_file in sorted((STATIC_DIR / "css").glob("*.css")) if (STATIC_DIR / "css").exists() else []:
        h.update(css_file.read_bytes())
    for js_file in sorted((STATIC_DIR / "js").glob("*.js")) if (STATIC_DIR / "js").exists() else []:
        h.update(js_file.read_bytes())
    result = h.hexdigest()[:8]
    _INDEX_HASH_CACHE[mtime_key] = result
    return result


def _ops_file_hash() -> str:
    import hashlib
    ops_path = STATIC_DIR / "ops.html"
    mtime = ops_path.stat().st_mtime if ops_path.exists() else 0.0
    if mtime in _OPS_HASH_CACHE:
        return _OPS_HASH_CACHE[mtime]
    try:
        result = hashlib.md5(ops_path.read_bytes()).hexdigest()[:8]
    except Exception:
        result = "0"
    _OPS_HASH_CACHE[mtime] = result
    return result


def _ops_revamp_file_hash() -> str:
    import hashlib
    revamp_path = STATIC_DIR / "ops_revamp.html"
    mtime = revamp_path.stat().st_mtime if revamp_path.exists() else 0.0
    if mtime in _OPS_REVAMP_HASH_CACHE:
        return _OPS_REVAMP_HASH_CACHE[mtime]
    try:
        result = hashlib.md5(revamp_path.read_bytes()).hexdigest()[:8]
    except Exception:
        result = "0"
    _OPS_REVAMP_HASH_CACHE[mtime] = result
    return result


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
    if _auth_enabled() and not _is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    role = _read_auth_role(request)
    if role == AUTH_ROLE_OPERATOR:
        return RedirectResponse("/ops", status_code=303)
    if _request_is_ops_domain(request):
        v = request.query_params.get("v")
        try:
            file_hash = _ops_file_hash()
        except Exception:
            file_hash = "0"
        if v != file_hash:
            from starlette.responses import Response as _Resp
            redirect_headers: dict[str, str] = {
                "Location": f"/?v={file_hash}",
                "Cache-Control": "no-store, no-cache, must-revalidate",
            }
            if _is_qa_env():
                redirect_headers["Clear-Site-Data"] = '"cache"'
            return _Resp(status_code=302, headers=redirect_headers)
        serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _is_qa_env() else HTML_PROD_CACHE_HEADERS
        return FileResponse(STATIC_DIR / "ops.html", headers=serve_headers)
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
        if _is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _is_qa_env() else HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "index.html", headers=serve_headers)


@router.get("/ops", include_in_schema=False)
def ops_shell(request: Request):
    v = request.query_params.get("v")
    try:
        file_hash = _ops_file_hash()
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _is_qa_env() else HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "ops.html", headers=serve_headers)


@router.get("/ops_revamp", include_in_schema=False)
def ops_revamp_shell(request: Request):
    if _auth_enabled() and not _is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    v = request.query_params.get("v")
    try:
        file_hash = _ops_revamp_file_hash()
    except Exception:
        file_hash = "0"
    if v != file_hash:
        from starlette.responses import Response as _Resp
        redirect_headers: dict[str, str] = {
            "Location": f"/ops_revamp?v={file_hash}",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        if _is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _is_qa_env() else HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "ops_revamp.html", headers=serve_headers)


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
        if _is_qa_env():
            redirect_headers["Clear-Site-Data"] = '"cache"'
        return _Resp(status_code=302, headers=redirect_headers)
    serve_headers = {**HTML_NO_CACHE_HEADERS, "Clear-Site-Data": '"cache"'} if _is_qa_env() else HTML_PROD_CACHE_HEADERS
    return FileResponse(STATIC_DIR / "index.html", headers=serve_headers)


@router.post("/ui/pick-directory", response_model=DirectoryPickerResponse)
def ui_pick_directory(payload: DirectoryPickerRequest) -> DirectoryPickerResponse:
    initial_path = str(payload.initial_path or "").strip() or None
    title = str(payload.title or "음원 폴더 선택").strip() or "음원 폴더 선택"
    try:
        picked = _pick_directory_interactive(title=title, initial_path=initial_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not picked:
        return DirectoryPickerResponse(directory_path=None, cancelled=True)
    return DirectoryPickerResponse(directory_path=picked, cancelled=False)


@router.post("/ui/upload-image", response_model=UiImageUploadResponse)
async def ui_upload_image(file: UploadFile = File(...)) -> UiImageUploadResponse:
    ext = _resolve_image_upload_extension(file.filename, file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="image upload only supports common image formats")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image file")
    if len(raw) > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="image file is too large (max 20MB)")

    month_bucket = datetime.now(timezone.utc).strftime("%Y%m")
    target_dir = IMAGE_UPLOAD_DIR / month_bucket
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{stamp}_{uuid4().hex[:10]}{ext}"
    target_path = target_dir / file_name
    target_path.write_bytes(raw)

    rel_path = target_path.relative_to(STATIC_DIR).as_posix()
    return UiImageUploadResponse(
        url=f"/ui-static/{rel_path}",
        file_name=file_name,
        file_size_bytes=len(raw),
        content_type=str(file.content_type or "").strip() or None,
    )