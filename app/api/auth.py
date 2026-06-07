"""Authentication routes (login page, login/logout/session endpoints).

These were the easiest-to-isolate slice of main.py — they only depend on
`app.security` (helpers) and `app.config` (settings), and they don't share
any module-level state with the rest of the app surface. Pulling them out
gives us a working APIRouter pattern to extend across the rest of the app
in subsequent passes (admin/auth-accounts, ops, owned_items, etc.).

The middleware in main.py keeps `/login`, `/auth/login`, `/auth/logout`,
`/auth/session` in its `allowed_paths` set so the order doesn't matter:
this router can be `include_router`'d before or after the middleware
declaration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from ..config import get_settings
from ..security import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    AUTH_ROLE_ADMIN,
    AUTH_ROLE_OPERATOR,
    AUTH_ROLE_VIEWER,
    _auth_accounts,
    _auth_cookie_value,
    _auth_enabled,
    _is_authenticated,
    _match_auth_account,
    _read_auth_session_data,
)


# Load templates from the same static directory main.py uses. We resolve
# the path lazily at module load — the directory exists at repo root and
# follows the same anchor as main.py's STATIC_DIR.
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_LOGIN_PAGE_PATH = _STATIC_DIR / "login.html"
_HTML_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "Cloudflare-CDN-Cache-Control": "no-store",
    "CDN-Cache-Control": "no-store",
    "Surrogate-Control": "no-store",
}


router = APIRouter(tags=["auth"])


@router.get("/login", include_in_schema=False)
def login_page(
    request: Request,
    site: str | None = Query(default=None),
    next: str | None = Query(default=None),
):
    if not _auth_enabled():
        return RedirectResponse(url="/", status_code=303)
    if _is_authenticated(request):
        session_data = _read_auth_session_data(request) or {}
        role = session_data.get("role", "").strip().upper()
        if role == AUTH_ROLE_OPERATOR:
            return RedirectResponse(url="/ops", status_code=303)
        return RedirectResponse(url="/", status_code=303)
        
    host = request.headers.get("host", "").lower()
    referer = request.headers.get("referer", "").lower()
    is_ops_domain = (
        "ops." in host
        or "ops." in referer
        or site == "ops"
        or (next is not None and next.startswith("/ops"))
    )
    
    if is_ops_domain:
        ops_login_path = _STATIC_DIR / "ops_login.html"
        content = ops_login_path.read_text(encoding="utf-8")
    else:
        content = _LOGIN_PAGE_PATH.read_text(encoding="utf-8")
        
    return HTMLResponse(content=content, headers=_HTML_NO_CACHE_HEADERS)


@router.post("/auth/login", include_in_schema=False)
def auth_login(
    username: str = Form(...),
    password: str = Form(...),
) -> dict[str, Any]:
    if not _auth_enabled():
        return {"authenticated": True, "username": None, "role": AUTH_ROLE_ADMIN, "enabled": False}

    matched_account = _match_auth_account(username=username, password=password)
    if matched_account is None:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    matched_username = str(matched_account["username"])
    matched_role = str(matched_account["role"])

    response = JSONResponse(
        {
            "authenticated": True,
            "username": matched_username,
            "role": matched_role,
            "enabled": True,
        }
    )
    settings = get_settings()
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _auth_cookie_value(matched_username, matched_role),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=bool(settings.auth_cookie_secure),
        samesite="lax",
        path="/",
    )
    return response


@router.post("/auth/logout", include_in_schema=False)
def auth_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


@router.get("/auth/session", include_in_schema=False)
def auth_session(request: Request) -> dict[str, Any]:
    session = _read_auth_session_data(request)
    username = str((session or {}).get("username") or "").strip() or None
    role = str((session or {}).get("role") or "").strip().upper() or None
    accounts = _auth_accounts()
    admin_available = any(
        str(account.get("role") or "").strip().upper() == AUTH_ROLE_ADMIN
        for account in accounts.values()
    )
    operator_available = any(
        str(account.get("role") or "").strip().upper() == AUTH_ROLE_OPERATOR
        for account in accounts.values()
    )
    viewer_available = any(
        str(account.get("role") or "").strip().upper() == AUTH_ROLE_VIEWER
        for account in accounts.values()
    )
    return {
        "enabled": _auth_enabled(),
        "authenticated": (not _auth_enabled()) or bool(username),
        "username": username if _auth_enabled() else None,
        "role": role if _auth_enabled() else AUTH_ROLE_ADMIN,
        "admin_available": admin_available,
        "operator_available": operator_available,
        "viewer_available": viewer_available,
    }
