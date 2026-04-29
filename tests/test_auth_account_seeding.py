"""Regression coverage for ENV → auth_account seeding.

After 2026-04 the runtime auth flow is DB-only: ENV credentials are seeded
into auth_account on startup and become regular managed rows. Login then
verifies against the stored pbkdf2 hash, never against a plaintext ENV
value. These tests pin that contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, main


def test_startup_seeds_env_admin_and_operator_accounts() -> None:
    with TestClient(main.app):
        rows = {row["username"]: row for row in db.list_auth_accounts()}

    assert "admin" in rows, "ENV admin must be seeded into auth_account"
    assert rows["admin"]["role"] == "ADMIN"
    assert rows["admin"]["password_hash"].startswith("pbkdf2_sha256$"), (
        "seeded password must be hashed, not stored as plaintext"
    )

    assert "operator" in rows, "ENV operator must be seeded into auth_account"
    assert rows["operator"]["role"] == "OPERATOR"
    assert rows["operator"]["password_hash"].startswith("pbkdf2_sha256$")


def test_seed_is_idempotent_and_does_not_overwrite_db_password() -> None:
    with TestClient(main.app) as client:
        before = db.get_auth_account_by_username("admin")
        assert before is not None
        # Simulate an admin password change happening through the UI.
        rotated_hash = main._hash_auth_password("rotated-admin-pass")
        db.upsert_auth_account(
            username="admin",
            password_hash=rotated_hash,
            role="ADMIN",
            is_active=True,
        )

    # Re-enter the lifespan; seed must not clobber the rotated hash.
    with TestClient(main.app):
        after = db.get_auth_account_by_username("admin")
        assert after is not None
        assert after["password_hash"] == rotated_hash, (
            "seed should be idempotent and never overwrite an existing row"
        )

    # Restore default seed for downstream tests in the same session.
    db.delete_auth_account("admin")
    with TestClient(main.app):
        restored = db.get_auth_account_by_username("admin")
        assert restored is not None
        assert main._verify_auth_password("admin-pass", restored["password_hash"])


def test_login_verifies_against_db_hash_only() -> None:
    with TestClient(main.app) as client:
        ok = client.post("/auth/login", data={"username": "admin", "password": "admin-pass"})
        assert ok.status_code == 200, "ENV-seeded admin must be able to log in"

        # Sanity: wrong password is rejected.
        bad = client.post("/auth/login", data={"username": "admin", "password": "nope"})
        assert bad.status_code == 401


def test_match_auth_account_rejects_plaintext_only_entries() -> None:
    """Belt-and-suspenders: even if a caller injected a plaintext-only entry
    into the in-memory account map, _match_auth_account must refuse to
    accept it (no password_hash → no login)."""
    plaintext_only = {
        "ghost": {"password": "ghost-pass", "role": "ADMIN"},
    }
    original = main._auth_accounts
    main._auth_accounts = lambda: plaintext_only  # type: ignore[assignment]
    try:
        assert main._match_auth_account("ghost", "ghost-pass") is None
    finally:
        main._auth_accounts = original  # type: ignore[assignment]


def test_session_endpoint_reports_db_backed_availability() -> None:
    with TestClient(main.app) as client:
        payload = client.get("/auth/session").json()
        assert payload["enabled"] is True
        assert payload["admin_available"] is True
        assert payload["operator_available"] is True
