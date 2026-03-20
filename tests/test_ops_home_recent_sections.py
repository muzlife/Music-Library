from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings
from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def insert_music_owned_item(
    *,
    item_name: str,
    artist: str,
    label: str,
    catalog_no: str,
    barcode: str,
    track_list: list[str],
    track_items: list[dict[str, str]],
    storage_slot_id: int | None = None,
) -> int:
    return db.insert_owned_item(
        {
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "item_name_override": item_name,
            "storage_slot_id": storage_slot_id,
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": artist,
                "label_name": label,
                "catalog_no": catalog_no,
                "barcode": barcode,
                "track_list": track_list,
                "track_items": track_items,
            },
        }
    )


def login_operator(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "operator", "password": "operator-pass"})
    assert response.status_code == 200
    session = client.get("/auth/session")
    assert session.status_code == 200
    payload = session.json()
    assert payload["authenticated"] is True
    assert payload["role"] == "OPERATOR"


@pytest.fixture
def isolated_ops_home_recent_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARY_DB_PATH", str(tmp_path / "ops-home-recent.db"))
    get_settings.cache_clear()
    db.init_db()
    yield
    get_settings.cache_clear()


@pytest.fixture
def ops_home_recent_client(isolated_ops_home_recent_db) -> TestClient:
    with TestClient(app) as test_client:
        login_operator(test_client)
        yield test_client


def test_operator_home_recent_endpoint_returns_recent_moves_and_newest_registrations(
    ops_home_recent_client,
):
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name")]
    first_slot = slots[0]
    second_slot = slots[1]

    recent_move_id = insert_music_owned_item(
        item_name="최근 이동 상품",
        artist="현장 밴드",
        label="Recent Label",
        catalog_no="RECENT-001",
        barcode="8800000001001",
        track_list=["Move"],
        track_items=[{"display": "1. Move", "title": "Move"}],
    )
    db.update_owned_item_slot(recent_move_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(recent_move_id, int(second_slot["id"]), movement_note="recent move")

    stale_move_id = insert_music_owned_item(
        item_name="오래된 이동 상품",
        artist="현장 밴드",
        label="Recent Label",
        catalog_no="STALE-001",
        barcode="8800000001002",
        track_list=["Old Move"],
        track_items=[{"display": "1. Old Move", "title": "Old Move"}],
    )
    db.update_owned_item_slot(stale_move_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(stale_move_id, int(second_slot["id"]), movement_note="stale move")

    older_registered_id = insert_music_owned_item(
        item_name="먼저 등록된 상품",
        artist="등록 팀",
        label="Register Label",
        catalog_no="REG-001",
        barcode="8800000001003",
        track_list=["Older"],
        track_items=[{"display": "1. Older", "title": "Older"}],
        storage_slot_id=int(first_slot["id"]),
    )
    newer_registered_id = insert_music_owned_item(
        item_name="나중 등록된 상품",
        artist="등록 팀",
        label="Register Label",
        catalog_no="REG-002",
        barcode="8800000001004",
        track_list=["Newer"],
        track_items=[{"display": "1. Newer", "title": "Newer"}],
        storage_slot_id=int(second_slot["id"]),
    )

    with db.get_conn() as conn:
        recent_at = (datetime.now(timezone.utc) - timedelta(hours=23)).isoformat()
        stale_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        recent_move_created_at = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
        stale_move_created_at = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
        older_created_at = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        newer_created_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id
              FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id ASC
              LIMIT 1
            )
            """,
            ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(), recent_move_id),
        )
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id
              FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC
              LIMIT 1
            )
            """,
            (recent_at, recent_move_id),
        )
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id
              FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id ASC
              LIMIT 1
            )
            """,
            ((datetime.now(timezone.utc) - timedelta(hours=26)).isoformat(), stale_move_id),
        )
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id
              FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC
              LIMIT 1
            )
            """,
            (stale_at, stale_move_id),
        )
        conn.execute(
            "UPDATE owned_item SET created_at = ?, updated_at = ? WHERE id = ?",
            (recent_move_created_at, recent_move_created_at, recent_move_id),
        )
        conn.execute(
            "UPDATE owned_item SET created_at = ?, updated_at = ? WHERE id = ?",
            (stale_move_created_at, stale_move_created_at, stale_move_id),
        )
        conn.execute(
            "UPDATE owned_item SET created_at = ?, updated_at = ? WHERE id = ?",
            (older_created_at, older_created_at, older_registered_id),
        )
        conn.execute(
            "UPDATE owned_item SET created_at = ?, updated_at = ? WHERE id = ?",
            (newer_created_at, newer_created_at, newer_registered_id),
        )

    response = ops_home_recent_client.get("/operator/home/recent")
    assert response.status_code == 200
    payload = response.json()

    moved_items = payload["recent_moved_items"]
    assert len(moved_items) == 1
    assert moved_items[0]["owned_item_id"] == recent_move_id
    assert moved_items[0]["item_title"] == "최근 이동 상품"
    assert moved_items[0]["current_cabinet_name"] == second_slot["cabinet_name"]
    assert moved_items[0]["current_column_code"] == second_slot["column_code"]
    assert moved_items[0]["current_cell_code"] == second_slot["cell_code"]
    assert moved_items[0]["previous_slot_display_name"] == first_slot["display_name"]

    registered_items = payload["recent_registered_items"]
    assert [row["owned_item_id"] for row in registered_items[:2]] == [newer_registered_id, older_registered_id]
    assert registered_items[0]["current_cabinet_name"] == second_slot["cabinet_name"]
    assert registered_items[0]["current_column_code"] == second_slot["column_code"]
    assert registered_items[0]["current_cell_code"] == second_slot["cell_code"]


def test_index_defines_ops_home_recent_sections_markup_and_loader():
    html = read_static_html("index.html")
    assert 'id="operatorRecentSections"' in html
    assert "최근 배치 이동 상품" in html
    assert "최근 등록 상품" in html
    assert 'id="operatorRecentMovedList"' in html
    assert 'id="operatorRecentRegisteredList"' in html
    assert "async function loadOperatorHomeRecentSections()" in html
    assert 'const res = await fetch("/operator/home/recent");' in html
    assert "function renderOperatorHomeRecentSections()" in html
    assert "if (!recentMovedItems.length && !recentRegisteredItems.length)" in html
