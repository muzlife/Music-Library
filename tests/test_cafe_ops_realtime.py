from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app import db


def test_cafe_db_device_helpers() -> None:
    """Test table device CRUD database helpers."""
    db.ensure_startup_db_ready()
    # Register device
    dev = db.register_table_device(table_number="99", device_id="test-uuid-99", device_label="Test Device")
    assert dev
    assert dev["table_number"] == "99"
    assert dev["device_id"] == "test-uuid-99"
    assert dev["device_label"] == "Test Device"
    assert dev["is_active"] == 1

    # Get device
    fetched = db.get_table_by_device("test-uuid-99")
    assert fetched
    assert fetched["table_number"] == "99"

    # List devices
    devices = db.list_table_devices()
    assert any(d["device_id"] == "test-uuid-99" for d in devices)

    # Deactivate device
    ok = db.deactivate_table_device("test-uuid-99")
    assert ok is True
    
    # Verify deactivated
    fetched_inactive = db.get_table_by_device("test-uuid-99")
    assert fetched_inactive is None

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM table_device WHERE device_id = ?", ("test-uuid-99",))


def test_cafe_db_reaction_helpers() -> None:
    """Test track reaction database helpers."""
    db.ensure_startup_db_ready()
    # Create temp track request
    req = db.create_customer_track_request(
        requested_track="Reaction Song",
        requested_by="operator"
    )
    req_id = req["id"]

    # Insert reaction
    rx_id = db.insert_track_reaction(
        track_request_id=req_id,
        table_number="5",
        reaction_type="LOVE",
        free_text="Awesome!"
    )
    assert rx_id > 0

    # Retrieve reactions
    reactions = db.list_reactions_by_request(req_id)
    assert len(reactions) == 1
    assert reactions[0]["reaction_type"] == "LOVE"
    assert reactions[0]["free_text"] == "Awesome!"
    assert reactions[0]["table_number"] == "5"

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM track_reaction WHERE id = ?", (rx_id,))
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_cafe_db_rollback_helper() -> None:
    """Test status rollback DB helper."""
    db.ensure_startup_db_ready()
    req = db.create_customer_track_request(
        requested_track="Rollback Song",
        requested_by="operator"
    )
    req_id = req["id"]

    # Update to RETURNED
    db.update_customer_track_request(req_id, status="RETURNED")
    fetched_returned = db.get_customer_track_request(req_id)
    assert fetched_returned["status"] == "RETURNED"

    # Rollback
    rolled = db.rollback_customer_track_request(req_id)
    assert rolled
    assert rolled["status"] == "REQUESTED"
    assert rolled["played_at"] is None
    assert rolled["returned_at"] is None

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_cafe_admin_api_endpoints(operator_client: TestClient) -> None:
    """Test table device CRUD API endpoints and stats query."""
    # 1. Register device via POST
    reg_resp = operator_client.post(
        "/ops/cafe/devices",
        json={
            "table_number": "77",
            "device_id": "uuid-77-api",
            "device_label": "API Tablet"
        }
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["ok"] is True
    assert reg_data["device"]["table_number"] == "77"

    # 2. List devices via GET
    list_resp = operator_client.get("/ops/cafe/devices")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert any(d["device_id"] == "uuid-77-api" for d in list_data["items"])

    # 3. Query stats via GET
    stats_resp = operator_client.get("/ops/cafe/stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert "reactions_summary" in stats_data
    assert "table_reactions" in stats_data
    assert "recent_reactions" in stats_data

    # 4. Deactivate device via DELETE
    del_resp = operator_client.delete("/ops/cafe/devices/uuid-77-api")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM table_device WHERE device_id = ?", ("uuid-77-api",))


def test_cafe_staff_restore_api_endpoint(operator_client: TestClient) -> None:
    """Test completed request restore API endpoint."""
    req = db.create_customer_track_request(
        requested_track="API Rollback Song",
        requested_by="operator"
    )
    req_id = req["id"]
    db.update_customer_track_request(req_id, status="RETURNED")

    # Call restore endpoint
    resp = operator_client.post(f"/ops/cafe/restore/{req_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "REQUESTED"

    # Verify state in DB
    fetched = db.get_customer_track_request(req_id)
    assert fetched["status"] == "REQUESTED"

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM customer_track_request WHERE id = ?", (req_id,))


def test_cafe_websocket_tablet_and_staff(operator_client: TestClient) -> None:
    """Test WS connection with UUID lookup and reaction broadcasting."""
    # 1. Register a table device for the WS test
    with db.get_write_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO table_device (table_number, device_id, device_label, is_active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
            ("12", "ws-tablet-uuid-12", "WS Tablet", "2026-05-28", "2026-05-28")
        )

    client = operator_client  # TestClient wraps websocket too

    # 2. Staff websocket connection
    with client.websocket_connect("/ws/cafe?role=staff") as staff_ws:
        # 3. Tablet websocket connection
        with client.websocket_connect("/ws/cafe?role=tablet&device_id=ws-tablet-uuid-12") as tablet_ws:
            
            # Send reaction from tablet
            tablet_ws.send_json({
                "event": "reaction",
                "payload": {
                    "track_request_id": 999,
                    "reaction_type": "LOVE",
                    "free_text": "Nice WS!"
                }
            })
            
            # Staff should receive the reaction broadcast
            staff_msg = staff_ws.receive_json()
            assert staff_msg["event"] == "reaction"
            assert staff_msg["table_number"] == "12"
            assert staff_msg["reaction_type"] == "LOVE"
            assert staff_msg["free_text"] == "Nice WS!"

    # Cleanup
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM table_device WHERE device_id = ?", ("ws-tablet-uuid-12",))
