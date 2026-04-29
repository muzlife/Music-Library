"""Admin auth-account management routes.

This is the second slice of the main.py → APIRouter split. It owns the
account CRUD surface that the `8-4. 계정` admin screen drives:

  * list:    GET    /admin/auth-accounts
  * create:  POST   /admin/auth-accounts
  * update:  PATCH  /admin/auth-accounts/{username}
  * delete:  DELETE /admin/auth-accounts/{username}

Two legacy mirror prefixes — `/api/admin-auth-accounts` and
`/ops-auth-accounts` — are preserved for backwards compatibility with
existing UI / curl runbooks. Each operation registers its handler at all
three paths via `router.add_api_route`, so the implementation lives in
exactly one function instead of the three near-identical wrappers main.py
used to carry.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .. import db
from ..schemas import (
    AuthAccountCreateRequest,
    AuthAccountItem,
    AuthAccountListResponse,
    AuthAccountUpdateRequest,
)
from ..security import _hash_auth_password, _require_admin_request


router = APIRouter(tags=["admin", "auth"])


def _system_auth_account_items() -> list[AuthAccountItem]:
    """Backwards-compat shim.

    ENV-configured accounts are now seeded into auth_account at startup, so
    every active account is a managed DB row. There are no live SYSTEM-only
    entries to surface; this helper is kept so the admin list endpoint
    continues to compose without changes.
    """
    return []


def _system_auth_account_lookup(username: str) -> dict[str, str] | None:
    """Backwards-compat shim.

    Plaintext ENV passwords are no longer consulted at runtime. The admin
    update endpoint handles the "seed missing" case by treating the request
    as a normal upsert (the password is required when DB has no row yet).
    """
    return None


# --- Handlers ----------------------------------------------------------- #
def list_auth_accounts(request: Request) -> AuthAccountListResponse:
    _require_admin_request(request)
    item_map: dict[str, AuthAccountItem] = {
        item.username: item for item in _system_auth_account_items()
    }
    for row in db.list_auth_accounts():
        username = str(row.get("username") or "").strip()
        item_map[username] = AuthAccountItem(
            username=username,
            role=str(row.get("role") or "OPERATOR").strip().upper(),  # type: ignore[arg-type]
            source="MANAGED",
            editable=True,
            is_active=bool(row.get("is_active")),
            created_at=str(row.get("created_at") or "").strip() or None,
            updated_at=str(row.get("updated_at") or "").strip() or None,
        )
    items = list(item_map.values())
    items.sort(
        key=lambda item: (
            0 if item.role == "ADMIN" else 1,
            0 if item.source == "SYSTEM" else 1,
            item.username.lower(),
        )
    )
    return AuthAccountListResponse(total_count=len(items), items=items)


def create_auth_account(payload: AuthAccountCreateRequest, request: Request) -> AuthAccountItem:
    _require_admin_request(request)
    username = str(payload.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if db.get_auth_account_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="이미 존재하는 계정입니다.")
    row = db.upsert_auth_account(
        username=username,
        password_hash=_hash_auth_password(payload.password),
        role=str(payload.role or "OPERATOR").strip().upper(),
        is_active=True,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="계정 저장에 실패했습니다.")
    return AuthAccountItem(
        username=str(row.get("username") or "").strip(),
        role=str(row.get("role") or "OPERATOR").strip().upper(),  # type: ignore[arg-type]
        source="MANAGED",
        editable=True,
        is_active=bool(row.get("is_active")),
        created_at=str(row.get("created_at") or "").strip() or None,
        updated_at=str(row.get("updated_at") or "").strip() or None,
    )


def update_auth_account(
    username: str, payload: AuthAccountUpdateRequest, request: Request
) -> AuthAccountItem:
    _require_admin_request(request)
    existing = db.get_auth_account_by_username(username)
    system_account = _system_auth_account_lookup(username)
    if existing is None and system_account is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    next_hash = str(existing.get("password_hash") or "").strip() if existing else ""
    if not next_hash and system_account is not None:
        next_hash = _hash_auth_password(system_account["password"])
    if payload.password is not None:
        next_hash = _hash_auth_password(payload.password)
    base_role = str(
        (existing or {}).get("role")
        or (system_account or {}).get("role")
        or "OPERATOR"
    ).strip().upper()
    next_role = str(payload.role or base_role).strip().upper()
    next_active = bool(existing.get("is_active")) if existing is not None else True
    if payload.is_active is not None:
        next_active = bool(payload.is_active)
    row = db.upsert_auth_account(
        username=username,
        password_hash=next_hash,
        role=next_role,
        is_active=next_active,
    )
    if row is None:
        raise HTTPException(status_code=500, detail="계정 수정에 실패했습니다.")
    return AuthAccountItem(
        username=str(row.get("username") or "").strip(),
        role=str(row.get("role") or "OPERATOR").strip().upper(),  # type: ignore[arg-type]
        source="MANAGED",
        editable=True,
        is_active=bool(row.get("is_active")),
        created_at=str(row.get("created_at") or "").strip() or None,
        updated_at=str(row.get("updated_at") or "").strip() or None,
    )


def delete_auth_account(username: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    existing = db.get_auth_account_by_username(username)
    if existing is None:
        raise HTTPException(status_code=404, detail="관리 계정을 찾을 수 없습니다.")
    ok = db.delete_auth_account(username)
    if not ok:
        raise HTTPException(status_code=500, detail="계정 삭제에 실패했습니다.")
    return {"ok": True, "username": username}


# --- Route registration -------------------------------------------------- #
# Each operation is registered at the canonical `/admin/...` path plus two
# legacy mirror prefixes the existing UI/curl runbooks rely on. Registering
# via `add_api_route` lets the implementation live in exactly one function;
# main.py used to carry three near-identical wrapper functions per op.
_LIST_PATHS = ("/admin/auth-accounts", "/api/admin-auth-accounts", "/ops-auth-accounts")
_DETAIL_PATHS = (
    "/admin/auth-accounts/{username}",
    "/api/admin-auth-accounts/{username}",
    "/ops-auth-accounts/{username}",
)

for _path in _LIST_PATHS:
    router.add_api_route(
        _path,
        list_auth_accounts,
        methods=["GET"],
        response_model=AuthAccountListResponse,
    )
    router.add_api_route(
        _path,
        create_auth_account,
        methods=["POST"],
        response_model=AuthAccountItem,
    )

for _path in _DETAIL_PATHS:
    router.add_api_route(
        _path,
        update_auth_account,
        methods=["PATCH"],
        response_model=AuthAccountItem,
    )
    router.add_api_route(
        _path,
        delete_auth_account,
        methods=["DELETE"],
    )
