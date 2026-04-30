"""Pin the first slice of the db.py → app/db/ package split.

  * `app.db` is now a package (app/db/__init__.py) instead of a single
    module. All existing import shapes (`from app import db`,
    `from app.db import list_auth_accounts`, `import app.db as db`)
    must continue to resolve to the same callables.
  * The auth-account surface lives in app.db.auth_account; the package
    __init__ re-exports it so call sites don't have to change.
  * The 5 moved functions are NOT redefined in app/db/__init__.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import db
from app.db import auth_account as auth_account_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_app_db_is_now_a_package() -> None:
    """db.py must have been replaced by app/db/__init__.py."""
    assert (REPO_ROOT / "app" / "db" / "__init__.py").is_file()
    assert not (REPO_ROOT / "app" / "db.py").exists(), (
        "app/db.py must not coexist with the package — stale module shadows it"
    )


def test_auth_account_submodule_exposes_expected_surface() -> None:
    expected = {
        "_ensure_auth_account_table",
        "list_auth_accounts",
        "get_auth_account_by_username",
        "upsert_auth_account",
        "delete_auth_account",
    }
    missing = [name for name in expected if not hasattr(auth_account_module, name)]
    assert not missing, f"app.db.auth_account missing: {missing}"


def test_db_package_reexports_auth_account_callables() -> None:
    """Existing call sites use `db.list_auth_accounts(...)` and friends.
    Make sure the package surface still resolves to the same callables
    that live in the auth_account submodule."""
    for name in (
        "_ensure_auth_account_table",
        "list_auth_accounts",
        "get_auth_account_by_username",
        "upsert_auth_account",
        "delete_auth_account",
    ):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(auth_account_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.auth_account.{name}"
        )


def test_init_py_no_longer_redefines_auth_account_callables() -> None:
    """Regression guard: bodies must live in auth_account.py, not be
    duplicated inside __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    forbidden = (
        "_ensure_auth_account_table",
        "list_auth_accounts",
        "get_auth_account_by_username",
        "upsert_auth_account",
        "delete_auth_account",
    )
    for name in forbidden:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/auth_account.py"
        )


def test_auth_account_round_trip_through_package_surface() -> None:
    """End-to-end: insert/list/get/delete via the package-level names."""
    db.ensure_startup_db_ready()
    username = "db-split-phase-1-probe"
    db.delete_auth_account(username)  # cleanup any leftover

    row = db.upsert_auth_account(
        username=username,
        password_hash="pbkdf2_sha256$1$x$y",
        role="OPERATOR",
        is_active=True,
    )
    assert row is not None
    assert row["username"] == username
    assert row["role"] == "OPERATOR"

    listed = {item["username"] for item in db.list_auth_accounts()}
    assert username in listed

    fetched = db.get_auth_account_by_username(username)
    assert fetched is not None
    assert fetched["username"] == username

    assert db.delete_auth_account(username) is True
    assert db.get_auth_account_by_username(username) is None


def test_legacy_import_paths_still_work() -> None:
    """`from app.db import ...` shape (used by app.security and the
    api/admin_auth_accounts router) must keep resolving."""
    from app.db import (  # noqa: F401
        delete_auth_account,
        get_auth_account_by_username,
        list_auth_accounts,
        upsert_auth_account,
    )
