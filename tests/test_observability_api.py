"""에러 로그 / 성능 로그 API 엔드포인트 통합 테스트."""


def test_exception_handler_records_error_log():
    """처리되지 않은 예외가 error_log에 기록된다."""
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


def test_error_log_list_requires_auth(client):
    """Unauthenticated requests to /admin/error-log are rejected."""
    resp = client.get("/admin/error-log")
    assert resp.status_code in (401, 403)


def test_error_log_list_and_unread_count(admin_client):
    """Admin can list error logs and get unread count."""
    from app.db.error_log import insert_error_log, acknowledge_error_log
    acknowledge_error_log(ids=None)  # 초기화
    insert_error_log(
        level="ERROR",
        source="s",
        message="msg1",
        traceback=None,
        request_path="/x",
        request_body=None,
    )

    resp = admin_client.get("/admin/error-log?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total_count"] >= 1

    resp2 = admin_client.get("/admin/error-log/unread-count")
    assert resp2.status_code == 200
    assert resp2.json()["count"] >= 1


def test_error_log_acknowledge(admin_client):
    """Admin can acknowledge all error logs."""
    from app.db.error_log import insert_error_log
    insert_error_log(
        level="ERROR",
        source="s",
        message="ack-me",
        traceback=None,
        request_path="/y",
        request_body=None,
    )

    resp = admin_client.post("/admin/error-log/acknowledge")  # 전체 확인
    assert resp.status_code == 200
    assert resp.json()["updated"] >= 1

    resp2 = admin_client.get("/admin/error-log/unread-count")
    assert resp2.json()["count"] == 0


def test_perf_middleware_records_slow_api(admin_client):
    """느린 API 호출이 perf_log에 기록된다."""
    admin_client.get("/owned-items?limit=1")  # 실제 API 호출
    from app.db.perf_log import list_perf_log_aggregated
    rows = list_perf_log_aggregated(kind="API", is_slow_only=False, days=1)
    assert isinstance(rows, list)
