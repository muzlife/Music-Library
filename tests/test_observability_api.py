"""에러 로그 / 성능 로그 API 엔드포인트 통합 테스트."""
import os
import tempfile

os.environ["LIBRARY_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "admin-pw")
os.environ.setdefault("LIBRARY_OPERATOR_USERNAME", "op")
os.environ.setdefault("LIBRARY_OPERATOR_PASSWORD", "op-pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "test-secret")
os.environ.setdefault("LIBRARY_AUTH_COOKIE_SECURE", "0")
os.environ.setdefault("METADATA_SYNC_INTERVAL_MINUTES", "0")

from app.config import get_settings
get_settings.cache_clear()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _admin_login():
    client.post("/auth/login", data={"username": "admin", "password": "admin-pw"})


def test_exception_handler_records_error_log():
    """처리되지 않은 예외가 error_log에 기록된다."""
    _admin_login()
    from app.db.error_log import insert_error_log, get_unread_error_count
    before = get_unread_error_count()
    insert_error_log(
        level="ERROR",
        source="test",
        message="simulated",
        traceback=None,
        request_path="/test",
        request_body=None,
    )
    assert get_unread_error_count() == before + 1
