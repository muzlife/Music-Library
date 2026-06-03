"""Auth/session helpers extracted from main.py.

Holds:
  * Constants: AUTH_COOKIE_NAME, AUTH_COOKIE_MAX_AGE, AUTH_ROLE_*
  * Password hashing/verifying (PBKDF2-SHA256)
  * Cookie signing/verifying (HMAC-SHA256 over the JSON payload)
  * Session reading helpers (`_read_auth_session_data`, role/role-check)
  * Account discovery (`_db_auth_accounts`, `_auth_accounts`,
    `_match_auth_account`)
  * ENV → DB seeding (`_seed_system_accounts`)
  * Request guards (`_require_admin_request`, `_require_authenticated_request`)

The main.py middleware (`auth_guard`) and the upcoming `app/api/auth.py`
router both import from this module. Centralising the helpers here means
adding a new auth-related route or CLI script doesn't have to fish through
an 11k-line main.py for the right private function.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request

from . import db
from .config import get_settings


logger = logging.getLogger(__name__)


# --- Constants ----------------------------------------------------------- #
AUTH_COOKIE_NAME = "__PROJECT_SLUG___session"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 14  # 14 days
AUTH_ROLE_ADMIN = "ADMIN"
AUTH_ROLE_OPERATOR = "OPERATOR"
AUTH_ROLE_VIEWER = "VIEWER"


# --- Password hashing ---------------------------------------------------- #
def _hash_auth_password(password: str) -> str:
    iterations = 200_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def _verify_auth_password(password: str, encoded: str) -> bool:
    raw = str(encoded or "").strip()
    if not raw:
        return False
    if not raw.startswith("pbkdf2_sha256$"):
        # Backwards-compat with any pre-existing plaintext rows; new rows
        # always go through `_hash_auth_password`.
        return secrets.compare_digest(str(password or ""), raw)
    try:
        _, iterations_text, salt_text, digest_text = raw.split("$", 3)
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
    return secrets.compare_digest(actual, expected)


# --- Account discovery --------------------------------------------------- #
def _extra_operator_accounts() -> list[tuple[str, str]]:
    settings = get_settings()
    raw = str(settings.auth_operator_accounts_raw or "").strip()
    if not raw:
        return []
    accounts: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        text = str(chunk or "").strip()
        if not text or ":" not in text:
            continue
        username, password = text.split(":", 1)
        username = username.strip()
        password = password.strip()
        if username and password:
            accounts.append((username, password))
    return accounts


def _db_auth_accounts() -> list[dict[str, str]]:
    rows = db.list_auth_accounts()
    out: list[dict[str, str]] = []
    for row in rows:
        if not bool(row.get("is_active")):
            continue
        username = str(row.get("username") or "").strip()
        password_hash = str(row.get("password_hash") or "").strip()
        role = str(row.get("role") or "").strip().upper()
        if username and password_hash and role in {AUTH_ROLE_ADMIN, AUTH_ROLE_OPERATOR, AUTH_ROLE_VIEWER}:
            out.append({"username": username, "password_hash": password_hash, "role": role})
    return out


def _env_seed_account_candidates() -> list[tuple[str, str, str]]:
    """ENV-configured admin/operator accounts that should be seeded into DB.

    These ENV variables are bootstrap-only: once seeded into auth_account,
    they are NOT consulted at login time. Rotate and remove them from
    .env.local after the first successful boot.
    """
    settings = get_settings()
    candidates: list[tuple[str, str, str]] = []
    admin_username = str(settings.auth_admin_username or "").strip()
    admin_password = str(settings.auth_admin_password or "")
    if admin_username and admin_password:
        candidates.append((admin_username, admin_password, AUTH_ROLE_ADMIN))

    operator_username = str(settings.auth_operator_username or "").strip()
    operator_password = str(settings.auth_operator_password or "")
    if operator_username and operator_password:
        candidates.append((operator_username, operator_password, AUTH_ROLE_OPERATOR))

    for username, password in _extra_operator_accounts():
        candidates.append((username, password, AUTH_ROLE_OPERATOR))

    return candidates


def _seed_system_accounts() -> list[tuple[str, str]]:
    """Seed ENV-configured accounts into auth_account on first boot.

    Idempotent: only inserts usernames that don't already exist in DB.
    Returns the list of (username, role) pairs that were freshly seeded.
    """
    seeded: list[tuple[str, str]] = []
    for username, password, role in _env_seed_account_candidates():
        if db.get_auth_account_by_username(username) is not None:
            continue
        try:
            password_hash = _hash_auth_password(password)
        except Exception:
            logger.exception("failed to hash bootstrap password for %s", username)
            continue
        row = db.upsert_auth_account(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        if row is not None:
            seeded.append((username, role))

    if seeded:
        names = ", ".join(f"{username}({role})" for username, role in seeded)
        logger.info(
            "Seeded %d auth account(s) from ENV: %s. ENV credentials are bootstrap-only; "
            "rotate the secrets in .env.local and manage future changes via /admin/auth-accounts.",
            len(seeded),
            names,
        )
    return seeded


def _auth_accounts() -> dict[str, dict[str, str]]:
    """Active auth accounts keyed by username.

    Source-of-truth is the auth_account table. ENV variables are no longer
    consulted at login time; they are seeded into DB at startup via
    `_seed_system_accounts` and become regular managed accounts.
    """
    accounts: dict[str, dict[str, str]] = {}
    for account in _db_auth_accounts():
        accounts[str(account["username"])] = {
            "password_hash": str(account["password_hash"]),
            "role": str(account["role"]),
        }
    return accounts


def _match_auth_account(username: str, password: str) -> dict[str, str] | None:
    provided_username = str(username or "").strip()
    provided_password = str(password or "")
    for account_username, account in _auth_accounts().items():
        if not secrets.compare_digest(provided_username, account_username):
            continue
        account_hash = str(account.get("password_hash") or "").strip()
        if not account_hash:
            continue
        if not _verify_auth_password(provided_password, account_hash):
            continue
        return {"username": account_username, "role": str(account.get("role") or AUTH_ROLE_ADMIN)}
    return None


def _auth_enabled() -> bool:
    return bool(_auth_accounts())


# --- Cookie signing/verification ---------------------------------------- #
def _auth_cookie_signature(payload_text: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.auth_session_secret.encode("utf-8"),
        payload_text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _auth_cookie_value(username: str, role: str) -> str:
    payload = json.dumps(
        {"u": username, "r": role, "ts": int(time.time())},
        separators=(",", ":"),
        ensure_ascii=True,
    )
    payload_text = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{payload_text}.{_auth_cookie_signature(payload_text)}"


# --- Session reading ---------------------------------------------------- #
def _read_auth_session_data(request: Request) -> dict[str, str] | None:
    raw_value = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if not raw_value or "." not in raw_value:
        return None
    payload_text, signature = raw_value.rsplit(".", 1)
    expected = _auth_cookie_signature(payload_text)
    if not secrets.compare_digest(signature, expected):
        return None
    try:
        padded = payload_text + "=" * (-len(payload_text) % 4)
        payload_raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        payload = json.loads(payload_raw)
    except Exception:
        return None
    username = str(payload.get("u") or "").strip()
    role = str(payload.get("r") or "").strip().upper()
    issued_at = int(payload.get("ts") or 0)
    if not username or issued_at <= 0:
        return None
    if int(time.time()) - issued_at > AUTH_COOKIE_MAX_AGE:
        return None
    if role not in {AUTH_ROLE_ADMIN, AUTH_ROLE_OPERATOR, AUTH_ROLE_VIEWER}:
        matched = _auth_accounts().get(username)
        role = str((matched or {}).get("role") or "").strip().upper()
    if role not in {AUTH_ROLE_ADMIN, AUTH_ROLE_OPERATOR, AUTH_ROLE_VIEWER}:
        return None
    return {"username": username, "role": role}


def _read_auth_username(request: Request) -> str | None:
    session = _read_auth_session_data(request)
    if session is None:
        return None
    return str(session.get("username") or "").strip() or None


def _read_auth_role(request: Request) -> str | None:
    session = _read_auth_session_data(request)
    if session is None:
        return None
    role = str(session.get("role") or "").strip().upper()
    return role if role in {AUTH_ROLE_ADMIN, AUTH_ROLE_OPERATOR, AUTH_ROLE_VIEWER} else None


def _is_authenticated(request: Request) -> bool:
    return _read_auth_session_data(request) is not None


def _is_admin_role(role: str | None) -> bool:
    return str(role or "").strip().upper() == AUTH_ROLE_ADMIN


def _is_operator_role(role: str | None) -> bool:
    return str(role or "").strip().upper() == AUTH_ROLE_OPERATOR


def _is_operator_or_admin_role(role: str | None) -> bool:
    return _is_admin_role(role) or _is_operator_role(role)


def _require_admin_request(request: Request) -> None:
    role = _read_auth_role(request)
    if not _is_admin_role(role):
        raise HTTPException(status_code=403, detail="admin access required")


def _require_operator_request(request: Request) -> None:
    role = _read_auth_role(request)
    if not _is_operator_or_admin_role(role):
        raise HTTPException(status_code=403, detail="operator access required")


def _require_authenticated_request(request: Request) -> None:
    if _read_auth_session_data(request) is None:
        raise HTTPException(status_code=403, detail="authentication required")


def _is_html_request(request: Request) -> bool:
    accept = str(request.headers.get("accept", "")).lower()
    return "text/html" in accept


# --- Public re-exports for downstream callers --------------------------- #
__all__ = [
    "AUTH_COOKIE_NAME",
    "AUTH_COOKIE_MAX_AGE",
    "AUTH_ROLE_ADMIN",
    "AUTH_ROLE_OPERATOR",
    "AUTH_ROLE_VIEWER",
    "_auth_accounts",
    "_auth_cookie_signature",
    "_auth_cookie_value",
    "_auth_enabled",
    "_db_auth_accounts",
    "_env_seed_account_candidates",
    "_extra_operator_accounts",
    "_hash_auth_password",
    "_is_admin_role",
    "_is_authenticated",
    "_is_html_request",
    "_is_operator_role",
    "_is_operator_or_admin_role",
    "_match_auth_account",
    "_read_auth_role",
    "_read_auth_session_data",
    "_read_auth_username",
    "_require_admin_request",
    "_require_operator_request",
    "_require_authenticated_request",
    "_seed_system_accounts",
    "_verify_auth_password",
]
