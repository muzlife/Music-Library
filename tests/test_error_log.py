import os
import tempfile
import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("LIBRARY_DB_PATH", _tmp)
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

from app.db.error_log import (
    insert_error_log,
    list_error_log,
    get_unread_error_count,
    acknowledge_error_log,
)


def test_insert_and_list():
    row_id = insert_error_log(
        level="ERROR",
        source="app/main.py:handler",
        message="Test error",
        traceback="Traceback...",
        request_path="GET /test",
        request_body=None,
    )
    assert row_id > 0
    rows = list_error_log(limit=10, offset=0)
    assert any(r["id"] == row_id for r in rows)


def test_unread_count_and_acknowledge():
    insert_error_log(level="ERROR", source="x", message="err1", traceback=None, request_path=None, request_body=None)
    insert_error_log(level="ERROR", source="y", message="err2", traceback=None, request_path=None, request_body=None)
    count_before = get_unread_error_count()
    assert count_before >= 2
    acknowledge_error_log(ids=None)  # 전체 확인
    assert get_unread_error_count() == 0


def test_acknowledge_single():
    rid = insert_error_log(level="CRITICAL", source="z", message="crit", traceback=None, request_path=None, request_body=None)
    acknowledge_error_log(ids=[rid])
    rows = list_error_log(is_read=True, limit=10, offset=0)
    assert any(r["id"] == rid for r in rows)
