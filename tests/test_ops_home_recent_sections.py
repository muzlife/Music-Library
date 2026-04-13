from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

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


def test_ensure_startup_db_ready_applies_recent_feed_indexes_to_existing_database(tmp_path, monkeypatch):
    db_path = tmp_path / "startup-existing.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    get_settings.cache_clear()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE owned_item (
          id INTEGER PRIMARY KEY,
          category TEXT,
          created_at TEXT,
          storage_slot_id INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE owned_item_location_event (
          id INTEGER PRIMARY KEY,
          owned_item_id INTEGER,
          movement_kind TEXT,
          from_slot_code TEXT,
          created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    db.ensure_startup_db_ready()

    conn = sqlite3.connect(db_path)
    try:
        index_names = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert "idx_owned_item_category_created_id" in index_names
    assert "idx_owned_item_location_event_move_created_owned" in index_names


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
    assert payload["recent_moved_total_count"] == 1
    assert moved_items[0]["owned_item_id"] == recent_move_id
    assert moved_items[0]["item_title"] == "최근 이동 상품"
    assert moved_items[0]["current_cabinet_name"] == second_slot["cabinet_name"]
    assert moved_items[0]["current_column_code"] == second_slot["column_code"]
    assert moved_items[0]["current_cell_code"] == second_slot["cell_code"]
    assert moved_items[0]["previous_slot_display_name"] == first_slot["display_name"]

    registered_items = payload["recent_registered_items"]
    assert payload["recent_registered_total_count"] >= 4
    assert [row["owned_item_id"] for row in registered_items[:2]] == [newer_registered_id, older_registered_id]
    assert registered_items[0]["current_cabinet_name"] == second_slot["cabinet_name"]
    assert registered_items[0]["current_column_code"] == second_slot["column_code"]
    assert registered_items[0]["current_cell_code"] == second_slot["cell_code"]


def test_operator_home_feed_endpoint_paginates_recent_registered_items_with_cover_art(
    ops_home_recent_client,
):
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name")]
    first_slot = slots[0]
    inserted_ids: list[int] = []

    for idx in range(35):
        owned_item_id = insert_music_owned_item(
            item_name=f"최근 등록 상품 {idx + 1}",
            artist="등록 테스트",
            label="Feed Label",
            catalog_no=f"FEED-{idx + 1:03d}",
            barcode=f"880000001{idx + 1:04d}",
            track_list=[f"Track {idx + 1}"],
            track_items=[{"display": "1. Track", "title": f"Track {idx + 1}"}],
            storage_slot_id=int(first_slot["id"]),
        )
        inserted_ids.append(owned_item_id)

    with db.get_conn() as conn:
        for idx, owned_item_id in enumerate(inserted_ids, start=1):
            created_at = (datetime.now(timezone.utc) - timedelta(minutes=(len(inserted_ids) - idx))).isoformat()
            conn.execute(
                "UPDATE owned_item SET created_at = ?, updated_at = ? WHERE id = ?",
                (created_at, created_at, owned_item_id),
            )
            conn.execute(
                "UPDATE music_item_detail SET cover_image_url = ? WHERE owned_item_id = ?",
                (f"https://covers.example.com/feed-{idx}.jpg", owned_item_id),
            )

    response = ops_home_recent_client.get("/operator/home/feed", params={"kind": "registered", "page": 1, "limit": 30})
    assert response.status_code == 200
    payload = response.json()

    assert payload["kind"] == "registered"
    assert payload["page"] == 1
    assert payload["limit"] == 30
    assert payload["total_count"] >= 35
    assert len(payload["items"]) == 30
    assert payload["items"][0]["item_title"] == "최근 등록 상품 35"
    assert payload["items"][0]["cover_image_url"] == "https://covers.example.com/feed-35.jpg"

    second_page = ops_home_recent_client.get("/operator/home/feed", params={"kind": "registered", "page": 2, "limit": 30})
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["page"] == 2
    assert len(second_payload["items"]) >= 5
    assert second_payload["items"][0]["item_title"] == "최근 등록 상품 5"


def test_operator_home_recent_and_feed_include_collector_meta_fields(
    ops_home_recent_client,
):
    first_slot = db.upsert_storage_slot("메타장-1", "01", "01", "STD")

    owned_item_id = insert_music_owned_item(
        item_name="메타 확장 상품",
        artist="메타 팀",
        label="Collector Label",
        catalog_no="COLLECT-001",
        barcode="8800000019999",
        track_list=["Track 1"],
        track_items=[{"display": "1. Track 1", "title": "Track 1"}],
        storage_slot_id=int(first_slot["id"]),
    )

    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE music_item_detail
            SET pressing_country = ?,
                format_items_json = ?,
                runout_matrix_json = ?
            WHERE owned_item_id = ?
            """,
            (
                "UK",
                '[{"qty": "2", "descriptions": ["Vinyl", "LP", "Album", "Stereo"]}]',
                '["A1 MPO", "B1 MPO"]',
                owned_item_id,
            ),
        )

    recent_response = ops_home_recent_client.get("/operator/home/recent")
    assert recent_response.status_code == 200
    recent_payload = recent_response.json()
    recent_item = next(row for row in recent_payload["recent_registered_items"] if row["owned_item_id"] == owned_item_id)
    assert recent_item["pressing_country"] == "UK"
    assert recent_item["barcode"] == "8800000019999"
    assert recent_item["format_items"] == [{"qty": "2", "descriptions": ["Vinyl", "LP", "Album", "Stereo"]}]
    assert recent_item["runout_sample"] == "A1 MPO | B1 MPO"

    feed_response = ops_home_recent_client.get("/operator/home/feed", params={"kind": "registered", "page": 1, "limit": 30})
    assert feed_response.status_code == 200
    feed_payload = feed_response.json()
    feed_item = next(row for row in feed_payload["items"] if row["owned_item_id"] == owned_item_id)
    assert feed_item["pressing_country"] == "UK"
    assert feed_item["barcode"] == "8800000019999"
    assert feed_item["format_items"] == [{"qty": "2", "descriptions": ["Vinyl", "LP", "Album", "Stereo"]}]
    assert feed_item["runout_sample"] == "A1 MPO | B1 MPO"


def test_operator_home_feed_endpoint_returns_recent_moved_page_with_previous_location(
    ops_home_recent_client,
):
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name")]
    first_slot = slots[0]
    second_slot = slots[1]

    first_id = insert_music_owned_item(
        item_name="최근 이동 피드 A",
        artist="이동 팀",
        label="Move Label",
        catalog_no="MOVE-001",
        barcode="8800000090001",
        track_list=["Move A"],
        track_items=[{"display": "1. Move A", "title": "Move A"}],
    )
    second_id = insert_music_owned_item(
        item_name="최근 이동 피드 B",
        artist="이동 팀",
        label="Move Label",
        catalog_no="MOVE-002",
        barcode="8800000090002",
        track_list=["Move B"],
        track_items=[{"display": "1. Move B", "title": "Move B"}],
    )
    stale_id = insert_music_owned_item(
        item_name="오래된 이동 피드",
        artist="이동 팀",
        label="Move Label",
        catalog_no="MOVE-003",
        barcode="8800000090003",
        track_list=["Move C"],
        track_items=[{"display": "1. Move C", "title": "Move C"}],
    )

    db.update_owned_item_slot(first_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(first_id, int(second_slot["id"]), movement_note="recent a")
    db.update_owned_item_slot(second_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(second_id, int(second_slot["id"]), movement_note="recent b")
    db.update_owned_item_slot(stale_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(stale_id, int(second_slot["id"]), movement_note="stale move")

    with db.get_conn() as conn:
        recent_times = [
            (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        ]
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC LIMIT 1
            )
            """,
            (recent_times[0], first_id),
        )
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC LIMIT 1
            )
            """,
            (recent_times[1], second_id),
        )
        stale_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC LIMIT 1
            )
            """,
            (stale_time, stale_id),
        )

    response = ops_home_recent_client.get("/operator/home/feed", params={"kind": "moved", "page": 1, "limit": 30})
    assert response.status_code == 200
    payload = response.json()

    assert payload["kind"] == "moved"
    assert payload["total_count"] >= 2
    assert [row["owned_item_id"] for row in payload["items"][:2]] == [second_id, first_id]
    assert payload["items"][0]["current_slot_display_name"] == second_slot["display_name"]
    assert payload["items"][0]["previous_slot_display_name"] == first_slot["display_name"]
    assert payload["items"][0]["current_cabinet_name"] == second_slot["cabinet_name"]


def test_collection_dashboard_recent_moves_match_operator_home_moved_feed(
    ops_home_recent_client,
):
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name")]
    first_slot = slots[0]
    second_slot = slots[1]

    first_id = insert_music_owned_item(
        item_name="대시보드 최근 이동 A",
        artist="이동 팀",
        label="Move Label",
        catalog_no="MOVE-DASH-001",
        barcode="8800000091001",
        track_list=["Move A"],
        track_items=[{"display": "1. Move A", "title": "Move A"}],
    )
    second_id = insert_music_owned_item(
        item_name="대시보드 최근 이동 B",
        artist="이동 팀",
        label="Move Label",
        catalog_no="MOVE-DASH-002",
        barcode="8800000091002",
        track_list=["Move B"],
        track_items=[{"display": "1. Move B", "title": "Move B"}],
    )

    db.update_owned_item_slot(first_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(first_id, int(second_slot["id"]), movement_note="recent a")
    db.update_owned_item_slot(second_id, int(first_slot["id"]), movement_note="initial")
    db.update_owned_item_slot(second_id, int(second_slot["id"]), movement_note="recent b")

    with db.get_conn() as conn:
        first_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        second_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC LIMIT 1
            )
            """,
            (first_time, first_id),
        )
        conn.execute(
            """
            UPDATE owned_item_location_event
            SET created_at = ?
            WHERE id = (
              SELECT id FROM owned_item_location_event
              WHERE owned_item_id = ?
              ORDER BY id DESC LIMIT 1
            )
            """,
            (second_time, second_id),
        )

    dashboard = db.get_collection_dashboard()
    moved_feed = db.get_ops_home_feed(kind="moved", page=1, limit=12)

    assert dashboard["recent_move_total"] == moved_feed["total_count"]
    assert [row["owned_item_id"] for row in dashboard["recent_moves"][:2]] == [second_id, first_id]
    assert [row["owned_item_id"] for row in dashboard["recent_moves"][:2]] == [
        row["owned_item_id"] for row in moved_feed["items"][:2]
    ]
    assert dashboard["recent_moves"][0]["from_display_name"] == moved_feed["items"][0]["previous_slot_display_name"]
    assert dashboard["recent_moves"][0]["to_display_name"] == moved_feed["items"][0]["current_slot_display_name"]


def test_index_defines_ops_home_recent_sections_markup_and_loader():
    html = read_static_html("index.html")
    assert 'id="operatorRecentSections"' in html
    assert "async function loadOperatorHomeRecentSections()" in html
    assert 'const res = await fetch("/operator/home/recent");' in html
    assert "function renderOperatorHomeRecentSections()" in html
    assert 'el.style.display = "none";' in html
    assert "recent_moved_total_count" in html
    assert "recent_registered_total_count" in html


def test_index_defines_operator_feed_markup_and_loader():
    html = read_static_html("index.html")
    assert 'id="operatorFeedRegisteredBtn"' in html
    assert 'id="operatorFeedMovedBtn"' in html
    assert 'id="operatorFeedPager"' in html
    assert "async function loadOperatorHomeFeed(options = {})" in html
    assert 'const res = await fetch(`/operator/home/feed?${params.toString()}`);' in html
    assert "operatorLookupMode = \"FEED\";" in html
    assert "최근 등록 상품이 없습니다." in html
    assert "최근 이동 상품이 없습니다." in html
    assert "곡명이나 상품명으로 조회하면 현재 위치와 직전 위치가 함께 표시됩니다." not in html
