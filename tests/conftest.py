import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="hahahoho-tests-"))

os.environ["LIBRARY_DB_PATH"] = str(_TEST_DB_DIR / "library.db")
os.environ["LIBRARY_ADMIN_USERNAME"] = "admin"
os.environ["LIBRARY_ADMIN_PASSWORD"] = "admin-pass"
os.environ["LIBRARY_OPERATOR_USERNAME"] = "operator"
os.environ["LIBRARY_OPERATOR_PASSWORD"] = "operator-pass"
os.environ["LIBRARY_AUTH_SESSION_SECRET"] = "test-session-secret"
os.environ["LIBRARY_AUTH_COOKIE_SECURE"] = "0"
os.environ["METADATA_SYNC_INTERVAL_MINUTES"] = "0"

from app.config import get_settings

get_settings.cache_clear()

from app.main import app


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200
    session = client.get("/auth/session")
    assert session.status_code == 200
    payload = session.json()
    assert payload["authenticated"] is True
    assert payload["username"] == username


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client() -> TestClient:
    with TestClient(app) as test_client:
        _login(test_client, "admin", "admin-pass")
        yield test_client


@pytest.fixture
def operator_client() -> TestClient:
    with TestClient(app) as test_client:
        _login(test_client, "operator", "operator-pass")
        yield test_client
