"""Pin the first slice of the main.py → APIRouter split.

  * `app.security` exists as a dedicated module and exposes the auth
    helpers main.py used to define inline.
  * `app.api.auth` exposes an `APIRouter` for /login, /auth/login,
    /auth/logout, /auth/session.
  * main.py imports the security helpers from `app.security` (not from a
    duplicated local definition).
  * Auth routes still respond identically: login returns 200, /auth/session
    reflects the cookie, /auth/logout clears the cookie.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import main as main_module
from app import security as security_module
from app.api import auth as auth_router_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_security_module_exports_required_helpers() -> None:
    expected = {
        "AUTH_COOKIE_NAME",
        "AUTH_COOKIE_MAX_AGE",
        "AUTH_ROLE_ADMIN",
        "AUTH_ROLE_OPERATOR",
        "_auth_accounts",
        "_auth_cookie_value",
        "_auth_enabled",
        "_hash_auth_password",
        "_match_auth_account",
        "_read_auth_session_data",
        "_require_admin_request",
        "_require_authenticated_request",
        "_seed_system_accounts",
        "_verify_auth_password",
    }
    missing = [name for name in expected if not hasattr(security_module, name)]
    assert not missing, f"app.security missing: {missing}"


def test_auth_router_module_exports_apirouter() -> None:
    assert isinstance(auth_router_module.router, APIRouter)
    paths = {route.path for route in auth_router_module.router.routes}
    assert paths == {"/login", "/auth/login", "/auth/logout", "/auth/session"}


def test_main_py_no_longer_redefines_auth_helpers() -> None:
    """Regression guard: helper bodies must live in app.security, not be
    duplicated inside main.py. We grep for `def <helper>(` at column 0 in
    main.py — an import (`from .security import ...`) does not match."""
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    forbidden_helpers = (
        "_auth_enabled",
        "_match_auth_account",
        "_read_auth_session_data",
        "_hash_auth_password",
        "_verify_auth_password",
        "_seed_system_accounts",
        "_require_admin_request",
        "_require_authenticated_request",
    )
    for name in forbidden_helpers:
        pattern = re.compile(rf"^def {re.escape(name)}\b", re.MULTILINE)
        assert not pattern.search(main_src), (
            f"main.py still defines {name}; it should live only in app.security"
        )


def test_main_py_no_longer_defines_auth_routes() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    for route_decorator in (
        '@app.get("/login"',
        '@app.post("/auth/login"',
        '@app.post("/auth/logout"',
        '@app.get("/auth/session"',
    ):
        assert route_decorator not in main_src, (
            f"{route_decorator} should now live in app/api/auth.py only"
        )


def test_login_session_logout_round_trip(client: TestClient) -> None:
    """End-to-end check that the moved router still works through the
    middleware exactly as before."""
    # Pre-login: session reports unauthenticated.
    pre = client.get("/auth/session").json()
    assert pre["enabled"] is True
    assert pre["authenticated"] is False
    assert pre["username"] is None

    # Login.
    login = client.post(
        "/auth/login", data={"username": "admin", "password": "admin-pass"}
    )
    assert login.status_code == 200
    body = login.json()
    assert body["authenticated"] is True
    assert body["username"] == "admin"

    # Session sees us.
    mid = client.get("/auth/session").json()
    assert mid["authenticated"] is True
    assert mid["username"] == "admin"

    # Logout clears cookie.
    out = client.post("/auth/logout")
    assert out.status_code == 200
    after = client.get("/auth/session").json()
    assert after["authenticated"] is False


def test_login_page_renders_login_html_for_unauthenticated_clients(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # The shipped login.html contains a login form.
    body_text = response.text.lower()
    assert "form" in body_text


def test_bad_password_returns_401_via_router(client: TestClient) -> None:
    response = client.post(
        "/auth/login", data={"username": "admin", "password": "definitely-wrong"}
    )
    assert response.status_code == 401
