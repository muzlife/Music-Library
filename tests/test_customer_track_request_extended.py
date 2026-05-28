from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app, _SEOUL_WEATHER_CACHE


def test_db_create_customer_track_request_with_weather_and_season() -> None:
    db.ensure_startup_db_ready()
    # Create request with explicit weather parameters
    created = db.create_customer_track_request(
        requested_track="Winter Sonata Theme",
        requested_by="operator",
        weather_temp_c=-5.2,
        weather_description="눈",
        weather_code=71,
        season="WINTER"
    )
    assert created
    req_id = created["id"]
    assert created["weather_temp_c"] == -5.2
    assert created["weather_description"] == "눈"
    assert created["weather_code"] == 71
    assert created["season"] == "WINTER"

    # Fetch from DB
    fetched = db.get_customer_track_request(req_id)
    assert fetched
    assert fetched["weather_temp_c"] == -5.2
    assert fetched["season"] == "WINTER"

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_db_create_customer_track_request_season_autodetect() -> None:
    db.ensure_startup_db_ready()
    # Create request with no weather parameters
    created = db.create_customer_track_request(
        requested_track="Spring Breeze",
        requested_by="operator"
    )
    assert created
    req_id = created["id"]
    
    # Season should be computed based on current month (May in test metadata, or current real month)
    # We just verify it is one of the valid seasons and weather is None
    assert created["season"] in {"SPRING", "SUMMER", "AUTUMN", "WINTER"}
    assert created["weather_temp_c"] is None

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_db_update_customer_track_request_playback_deck_and_timestamps() -> None:
    db.ensure_startup_db_ready()
    created = db.create_customer_track_request(
        requested_track="Autumn Leaves",
        requested_by="operator"
    )
    assert created
    req_id = created["id"]
    assert created["playback_deck"] is None
    assert created["played_at"] is None
    assert created["returned_at"] is None

    # Transition to PLAYING with Deck A
    updated = db.update_customer_track_request(
        req_id,
        status="PLAYING",
        playback_deck="Turntable A"
    )
    assert updated
    assert updated["status"] == "PLAYING"
    assert updated["playback_deck"] == "Turntable A"
    assert updated["played_at"] is not None
    assert updated["returned_at"] is None

    # Transition to RETURNED
    returned = db.update_customer_track_request(
        req_id,
        status="RETURNED"
    )
    assert returned
    assert returned["status"] == "RETURNED"
    assert returned["playback_deck"] == "Turntable A"
    assert returned["played_at"] is not None
    assert returned["returned_at"] is not None

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_api_endpoints_for_cafe_operations(operator_client: TestClient) -> None:
    # 1. Mock weather cache
    import app.main
    if app.main._SEOUL_WEATHER_CACHE is None:
        app.main._SEOUL_WEATHER_CACHE = {}
    app.main._SEOUL_WEATHER_CACHE.clear()
    app.main._SEOUL_WEATHER_CACHE.update({
        "available": True,
        "temperature_c": 18.5,
        "weather_code": 0,
        "description": ""
    })

    # 2. Create track request via POST
    response = operator_client.post(
        "/operator/customer-requests",
        json={
            "requested_track": "Let It Be",
            "customer_note": "Acoustic version"
        }
    )
    assert response.status_code == 200
    data = response.json()
    req_id = data["id"]
    assert data["weather_temp_c"] == 18.5
    assert data["weather_description"] == "맑음"
    assert data["weather_code"] == 0

    # 3. Verify /ops/cafe page loading
    cafe_resp = operator_client.get("/ops/cafe")
    assert cafe_resp.status_code in {200, 302}

    # 4. Patch request to PLAYING with Turntable B
    patch_resp = operator_client.patch(
        f"/operator/customer-requests/{req_id}",
        json={
            "status": "PLAYING",
            "playback_deck": "Turntable B"
        }
    )
    assert patch_resp.status_code == 200
    p_data = patch_resp.json()
    assert p_data["status"] == "PLAYING"
    assert p_data["playback_deck"] == "Turntable B"
    assert p_data["played_at"] is not None

    # 5. Query /operator/customer-requests/now-playing
    np_resp = operator_client.get("/operator/customer-requests/now-playing")
    assert np_resp.status_code == 200
    np_list = np_resp.json()
    assert len(np_list) >= 1
    assert any(item["id"] == req_id and item["playback_deck"] == "Turntable B" for item in np_list)

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_api_roon_endpoints(operator_client: TestClient) -> None:
    # 1. Get initial status
    resp = operator_client.get("/operator/roon/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "connected" in data
    assert "core_name" in data
    assert "active_zone" in data
    assert "volume" in data
    assert "now_playing_request_id" in data

    # 2. Update status via POST
    update_resp = operator_client.post(
        "/operator/roon/status/update",
        json={
            "connected": True,
            "active_zone": "Main Zone",
            "volume": 45,
            "now_playing_request_id": 9999
        }
    )
    assert update_resp.status_code == 200
    u_data = update_resp.json()
    assert u_data["connected"] is True
    assert u_data["active_zone"] == "Main Zone"
    assert u_data["volume"] == 45
    assert u_data["now_playing_request_id"] == 9999

    # 3. Create a track request to play via Roon
    create_resp = operator_client.post(
        "/operator/customer-requests",
        json={
            "requested_track": "Roon Song",
            "customer_note": "Via Roon"
        }
    )
    assert create_resp.status_code == 200
    req_id = create_resp.json()["id"]

    # 4. Play track via Roon endpoint
    play_resp = operator_client.post(f"/operator/roon/play/{req_id}")
    assert play_resp.status_code == 200
    p_data = play_resp.json()
    assert p_data["id"] == req_id
    assert p_data["status"] == "PLAYING"
    assert p_data["playback_deck"] == "Roon (Stream)"

    # Verify Roon status is updated with now playing ID
    status_resp = operator_client.get("/operator/roon/status")
    assert status_resp.json()["now_playing_request_id"] == req_id

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))

