"""Admin permission management routes.

Endpoints:
  GET    /admin/permissions                              — 권한 마스터 + 역할 기본값
  PUT    /admin/permissions/role/{role}                  — 역할 기본 권한 설정
  GET    /admin/permissions/account/{username}           — 계정 오버라이드 조회
  PUT    /admin/permissions/account/{username}/grant/{key} — 계정 권한 추가 부여
  PUT    /admin/permissions/account/{username}/deny/{key}  — 계정 권한 명시 차단
  DELETE /admin/permissions/account/{username}/{key}     — 오버라이드 제거 (역할 기본값 복원)
  DELETE /admin/permissions/account/{username}           — 계정 오버라이드 전체 초기화
  GET    /admin/permissions/account/{username}/effective — 실질 권한 (role + override 합산)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..security import (
    AUTH_ROLE_CAFE_STAFF,
    AUTH_ROLE_OPERATOR,
    _require_admin_request,
)

router = APIRouter(tags=["admin", "permissions"])

_MANAGEABLE_ROLES = {AUTH_ROLE_OPERATOR, AUTH_ROLE_CAFE_STAFF}


class _RolePermissionsBody(BaseModel):
    permission_keys: list[str]


@router.get("/admin/permissions", include_in_schema=False)
def get_permissions(request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    permissions = db.list_permissions()
    role_defaults = {
        AUTH_ROLE_OPERATOR: db.list_role_permissions(AUTH_ROLE_OPERATOR),
        AUTH_ROLE_CAFE_STAFF: db.list_role_permissions(AUTH_ROLE_CAFE_STAFF),
    }
    return {"permissions": permissions, "role_defaults": role_defaults}


@router.put("/admin/permissions/role/{role}", include_in_schema=False)
def put_role_permissions(role: str, body: _RolePermissionsBody, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    r = str(role or "").strip().upper()
    if r not in _MANAGEABLE_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(_MANAGEABLE_ROLES)}")
    db.set_role_permissions(r, body.permission_keys)
    return {"role": r, "permission_keys": body.permission_keys}


@router.get("/admin/permissions/account/{username}", include_in_schema=False)
def get_account_overrides(username: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    overrides = db.list_account_permissions(username)
    return {"username": username, "overrides": overrides}


@router.put("/admin/permissions/account/{username}/grant/{permission_key:path}", include_in_schema=False)
def grant_account_permission(username: str, permission_key: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    db.set_account_permission(username, permission_key, True)
    return {"username": username, "permission_key": permission_key, "granted": True}


@router.put("/admin/permissions/account/{username}/deny/{permission_key:path}", include_in_schema=False)
def deny_account_permission(username: str, permission_key: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    db.set_account_permission(username, permission_key, False)
    return {"username": username, "permission_key": permission_key, "granted": False}


@router.delete("/admin/permissions/account/{username}/{permission_key:path}", include_in_schema=False)
def delete_account_permission_override(username: str, permission_key: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    deleted = db.delete_account_permission(username, permission_key)
    return {"deleted": deleted}


@router.delete("/admin/permissions/account/{username}", include_in_schema=False)
def clear_account_permission_overrides(username: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    count = db.clear_account_permissions(username)
    return {"deleted_count": count}


@router.get("/admin/permissions/account/{username}/effective", include_in_schema=False)
def get_effective_permissions(username: str, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    account = db.get_auth_account_by_username(username)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    role = str(account.get("role") or "").strip().upper()
    effective = db.get_effective_permissions(username, role)
    return {"username": username, "role": role, "effective": effective}
