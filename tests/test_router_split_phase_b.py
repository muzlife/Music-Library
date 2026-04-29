"""Pin the second slice of the main.py → APIRouter split.

  * `app.api.admin_auth_accounts` exposes an `APIRouter` for the auth-account
    CRUD surface — including the legacy `/api/admin-auth-accounts` and
    `/ops-auth-accounts` mirror prefixes.
  * main.py no longer defines those 12 routes nor the `_system_auth_account_*`
    helpers.
  * The endpoints still respond identically — list, create, update, delete
    round-trip works through the new router on all three path prefixes.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.api import admin_auth_accounts as admin_module


REPO_ROOT = Path(__file__).resolve().parents[1]
_LIST_PREFIXES = ("/admin/auth-accounts", "/api/admin-auth-accounts", "/ops-auth-accounts")
_DETAIL_PREFIXES = (
    "/admin/auth-accounts/{username}",
    "/api/admin-auth-accounts/{username}",
    "/ops-auth-accounts/{username}",
)


def test_router_module_exposes_apirouter() -> None:
    assert isinstance(admin_module.router, APIRouter)
    paths_methods: set[tuple[str, frozenset[str]]] = set()
    for route in admin_module.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path is None:
            continue
        paths_methods.add((path, frozenset(methods)))

    expected = set()
    for prefix in _LIST_PREFIXES:
        expected.add((prefix, frozenset({"GET"})))
        expected.add((prefix, frozenset({"POST"})))
    for prefix in _DETAIL_PREFIXES:
        expected.add((prefix, frozenset({"PATCH"})))
        expected.add((prefix, frozenset({"DELETE"})))

    assert expected.issubset(paths_methods), (
        f"missing routes: {sorted(expected - paths_methods)}"
    )


def test_main_py_no_longer_defines_admin_auth_account_routes() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    forbidden_decorators = (
        '@app.get("/admin/auth-accounts"',
        '@app.post("/admin/auth-accounts"',
        '@app.patch("/admin/auth-accounts/{username}"',
        '@app.delete("/admin/auth-accounts/{username}"',
        '@app.get("/api/admin-auth-accounts"',
        '@app.post("/api/admin-auth-accounts"',
        '@app.patch("/api/admin-auth-accounts/{username}"',
        '@app.delete("/api/admin-auth-accounts/{username}"',
        '@app.get("/ops-auth-accounts"',
        '@app.post("/ops-auth-accounts"',
        '@app.patch("/ops-auth-accounts/{username}"',
        '@app.delete("/ops-auth-accounts/{username}"',
    )
    for decorator in forbidden_decorators:
        assert decorator not in main_src, (
            f"{decorator} should now live in app/api/admin_auth_accounts.py"
        )


def test_main_py_no_longer_defines_system_auth_helpers() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    for helper in ("_system_auth_account_items", "_system_auth_account_lookup"):
        pattern = re.compile(rf"^def {re.escape(helper)}\b", re.MULTILINE)
        assert not pattern.search(main_src), (
            f"main.py still defines {helper}; it lives in app.api.admin_auth_accounts now"
        )


def _admin_creds() -> tuple[str, str]:
    return ("admin", "admin-pass")


def test_admin_auth_account_round_trip_through_router(admin_client: TestClient) -> None:
    """End-to-end check on the canonical /admin path: create → list → patch
    → delete. We do this on the router-served path to prove the moved code
    still works through the middleware."""
    username = "router-phase-b-probe"
    # Cleanup if a stale row from a prior failed test is sitting around.
    admin_client.delete(f"/admin/auth-accounts/{username}")

    created = admin_client.post(
        "/admin/auth-accounts",
        json={"username": username, "password": "init-pass-1!", "role": "OPERATOR"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["username"] == username
    assert body["role"] == "OPERATOR"
    assert body["is_active"] is True

    listed = admin_client.get("/admin/auth-accounts").json()
    usernames = {item["username"] for item in listed["items"]}
    assert username in usernames

    patched = admin_client.patch(
        f"/admin/auth-accounts/{username}",
        json={"is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    deleted = admin_client.delete(f"/admin/auth-accounts/{username}")
    assert deleted.status_code == 200


def test_admin_auth_account_mirror_prefixes_share_implementation(
    admin_client: TestClient,
) -> None:
    """Each legacy mirror prefix must expose the same list — confirms the
    `add_api_route` registration replicated the handler instead of producing
    three divergent implementations."""
    canonical = admin_client.get("/admin/auth-accounts").json()
    api_mirror = admin_client.get("/api/admin-auth-accounts").json()
    ops_mirror = admin_client.get("/ops-auth-accounts").json()

    canonical_names = sorted(item["username"] for item in canonical["items"])
    api_names = sorted(item["username"] for item in api_mirror["items"])
    ops_names = sorted(item["username"] for item in ops_mirror["items"])
    assert canonical_names == api_names == ops_names


def test_non_admin_caller_gets_403(operator_client: TestClient) -> None:
    """Operator role must not be able to list/create accounts."""
    response = operator_client.get("/admin/auth-accounts")
    assert response.status_code == 403


def test_main_py_imports_admin_auth_accounts_router() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    assert "from .api.admin_auth_accounts import router" in main_src
    assert "app.include_router(admin_auth_accounts_router)" in main_src
