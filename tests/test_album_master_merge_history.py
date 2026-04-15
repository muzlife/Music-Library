from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings
from app.main import app


def login_admin(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200


@pytest.fixture
def isolated_album_master_merge_history_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARY_DB_PATH", str(tmp_path / "album-master-merge-history.db"))
    get_settings.cache_clear()
    db.init_db()
    yield
    get_settings.cache_clear()


@pytest.fixture
def album_master_merge_history_client(isolated_album_master_merge_history_db) -> TestClient:
    with TestClient(app) as test_client:
        login_admin(test_client)
        yield test_client


def insert_music_owned_item(*, item_name: str, artist: str, catalog_no: str) -> int:
    return db.insert_owned_item(
        {
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "item_name_override": item_name,
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": artist,
                "label_name": "Merge Label",
                "catalog_no": catalog_no,
                "barcode": f"8800000{catalog_no[-4:]}",
                "track_list": ["Intro"],
                "track_items": [{"display": "1. Intro", "title": "Intro"}],
            },
        }
    )


def insert_album_master(*, source_code: str, source_master_id: str, title: str, artist_or_brand: str) -> int:
    now = db.utc_now_iso()
    with db.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO album_master
              (source_code, source_master_id, title, artist_or_brand, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, '{}', ?, ?)
            """,
            (source_code, source_master_id, title, artist_or_brand, now, now),
        )
        return int(cur.lastrowid)


def seed_album_master_merge_case() -> dict[str, int]:
    source_owned_id = insert_music_owned_item(item_name="Source Album", artist="Source Artist", catalog_no="SRC-001")
    target_owned_id = insert_music_owned_item(item_name="Target Album", artist="Target Artist", catalog_no="TGT-001")

    source_master_id = insert_album_master(
        source_code="MANUAL",
        source_master_id="MERGE-SRC-001",
        title="Source Album",
        artist_or_brand="Source Artist",
    )
    target_master_id = insert_album_master(
        source_code="MANUAL",
        source_master_id="MERGE-TGT-001",
        title="Target Album",
        artist_or_brand="Target Artist",
    )

    db.bind_album_master_members(source_master_id, [source_owned_id])
    db.bind_album_master_members(target_master_id, [target_owned_id])
    db.set_owned_item_linked_album_master(source_owned_id, source_master_id)
    db.set_owned_item_linked_album_master(target_owned_id, target_master_id)
    external_ref_id = db.ensure_album_master_external_ref(
        source_master_id,
        "DISCOGS",
        "discogs-merge-src-001",
        title_hint="Source Album",
        artist_or_brand_hint="Source Artist",
    )

    return {
        "source_owned_id": source_owned_id,
        "target_owned_id": target_owned_id,
        "source_master_id": source_master_id,
        "target_master_id": target_master_id,
        "external_ref_id": external_ref_id,
    }


def test_album_master_merge_records_history_and_latest_rollback_restores_previous_state(
    album_master_merge_history_client: TestClient,
):
    seeded = seed_album_master_merge_case()

    merge_response = album_master_merge_history_client.post(
        f"/album-masters/{seeded['source_master_id']}/merge",
        json={"target_album_master_id": seeded["target_master_id"]},
    )

    assert merge_response.status_code == 200
    merge_payload = merge_response.json()
    assert int(merge_payload["merge_history_id"]) > 0

    history_response = album_master_merge_history_client.get("/album-masters/merge-history?limit=5")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload[0]["merged_by"] == "admin"
    assert history_payload[0]["source_album_master_id"] == seeded["source_master_id"]
    assert history_payload[0]["target_album_master_id"] == seeded["target_master_id"]
    assert history_payload[0]["moved_member_count"] == 1
    assert history_payload[0]["rollback_available"] is True

    rollback_response = album_master_merge_history_client.post("/album-masters/merge-history/latest/rollback")
    assert rollback_response.status_code == 200
    rollback_payload = rollback_response.json()
    assert rollback_payload["rolled_back"] is True
    assert rollback_payload["source_album_master_id"] == seeded["source_master_id"]
    assert rollback_payload["target_album_master_id"] == seeded["target_master_id"]
    assert rollback_payload["restored_member_count"] == 1

    assert db.album_master_exists(seeded["source_master_id"]) is True
    source_members = db.list_owned_items_by_album_master(seeded["source_master_id"])
    target_members = db.list_owned_items_by_album_master(seeded["target_master_id"])
    assert [int(row["id"]) for row in source_members] == [seeded["source_owned_id"]]
    assert [int(row["id"]) for row in target_members] == [seeded["target_owned_id"]]

    source_refs = db.list_album_master_external_refs(seeded["source_master_id"])
    assert [int(row["id"]) for row in source_refs] == [seeded["external_ref_id"]]


def test_latest_merge_rollback_is_blocked_when_target_master_changes_after_merge(
    album_master_merge_history_client: TestClient,
):
    seeded = seed_album_master_merge_case()

    merge_response = album_master_merge_history_client.post(
        f"/album-masters/{seeded['source_master_id']}/merge",
        json={"target_album_master_id": seeded["target_master_id"]},
    )
    assert merge_response.status_code == 200

    db.update_album_master_sort_artist_name(seeded["target_master_id"], "Changed Sort Artist")

    history_response = album_master_merge_history_client.get("/album-masters/merge-history?limit=5")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload[0]["rollback_available"] is False
    assert history_payload[0]["rollback_blocked_reason"]

    rollback_response = album_master_merge_history_client.post("/album-masters/merge-history/latest/rollback")
    assert rollback_response.status_code == 409
    assert "rollback" in str(rollback_response.json()["detail"]).lower()


def test_latest_merge_rollback_restores_previous_owned_item_link_even_for_overlap_members(
    album_master_merge_history_client: TestClient,
):
    seeded = seed_album_master_merge_case()

    overlap_owned_id = insert_music_owned_item(item_name="Overlap Album", artist="Overlap Artist", catalog_no="OVR-001")
    db.bind_album_master_members(seeded["source_master_id"], [overlap_owned_id], replace_existing=False)
    db.bind_album_master_members(seeded["target_master_id"], [overlap_owned_id], replace_existing=False)
    db.set_owned_item_linked_album_master(overlap_owned_id, seeded["target_master_id"])

    merge_response = album_master_merge_history_client.post(
        f"/album-masters/{seeded['source_master_id']}/merge",
        json={"target_album_master_id": seeded["target_master_id"]},
    )
    assert merge_response.status_code == 200

    rollback_response = album_master_merge_history_client.post("/album-masters/merge-history/latest/rollback")
    assert rollback_response.status_code == 200

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT linked_album_master_id FROM owned_item WHERE id = ? LIMIT 1",
            (overlap_owned_id,),
        ).fetchone()
    assert int(row["linked_album_master_id"] or 0) == seeded["target_master_id"]
