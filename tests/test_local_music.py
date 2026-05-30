import os
import urllib.parse
from unittest import mock
import pytest
from fastapi.testclient import TestClient
from app.db.local_music_index import get_local_track_by_path, _ensure_index_table
from app.db import get_conn
from app.services.local_player import MUSIC_ROOT


def test_get_local_track_by_path_indexed():
    # Insert a dummy record into the temporary test DB
    with get_conn() as conn:
        _ensure_index_table(conn)
        conn.execute("DELETE FROM local_music_index")
        conn.execute(
            """
            INSERT INTO local_music_index 
            (file_path, title, artist, album, genre, year, track_number, duration_seconds, file_size, has_cover, indexed_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "/Volumes/Music/01.K-pop/test_song.mp3",
                "Indexed Title",
                "Indexed Artist",
                "Indexed Album",
                "K-Pop",
                "2026",
                3,
                180.5,
                5000000,
                1,
                "2026-05-29T00:00:00Z"
            )
        )

    info = get_local_track_by_path("/Volumes/Music/01.K-pop/test_song.mp3")
    assert info is not None
    assert info["title"] == "Indexed Title"
    assert info["artist"] == "Indexed Artist"
    assert info["album"] == "Indexed Album"
    assert info["has_cover"] == 1


@mock.patch("os.path.isfile")
@mock.patch("tinytag.TinyTag.get")
def test_get_local_track_by_path_dynamic(mock_tiny_get, mock_isfile):
    mock_isfile.return_value = True
    
    # Mock TinyTag object behavior
    mock_tag = mock.MagicMock()
    mock_tag.title = "Dynamic Title"
    mock_tag.artist = "Dynamic Artist"
    mock_tag.album = "Dynamic Album"
    mock_tag.genre = "K-Pop"
    mock_tag.year = "2026"
    mock_tag.track = "5"
    mock_tag.duration = 210.2
    mock_tag.get_image.return_value = b"some_image_bytes"
    mock_tiny_get.return_value = mock_tag

    # Clear index DB first so it falls back to dynamic parsing
    with get_conn() as conn:
        _ensure_index_table(conn)
        conn.execute("DELETE FROM local_music_index")

    info = get_local_track_by_path("/Volumes/Music/01.K-pop/dynamic_song.mp3")
    assert info is not None
    assert info["title"] == "Dynamic Title"
    assert info["artist"] == "Dynamic Artist"
    assert info["album"] == "Dynamic Album"
    assert info["has_cover"] == 1


@mock.patch("os.path.isfile")
@mock.patch("tinytag.TinyTag.get")
def test_cafe_local_cover_success(mock_tiny_get, mock_isfile, client: TestClient):
    mock_isfile.return_value = True
    
    # Mock TinyTag for embedded PNG cover
    mock_tag = mock.MagicMock()
    mock_tag.get_image.return_value = b"\x89PNG\r\n\x1a\nFake PNG Bytes"
    mock_tiny_get.return_value = mock_tag

    # Set file_path inside MUSIC_ROOT
    fp = os.path.join(MUSIC_ROOT, "subfolder", "song.mp3")
    
    response = client.get(f"/cafe/local-cover?file_path={urllib.parse.quote(fp)}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG\r\n\x1a\nFake PNG Bytes"


def test_cafe_local_cover_traversal_protection(client: TestClient):
    # Try traversing outside of MUSIC_ROOT
    bad_path = os.path.realpath(os.path.join(MUSIC_ROOT, "../../../etc/passwd"))
    
    response = client.get(f"/cafe/local-cover?file_path={urllib.parse.quote(bad_path)}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


@mock.patch("os.path.isfile")
def test_cafe_local_cover_not_found(mock_isfile, client: TestClient):
    mock_isfile.return_value = False
    
    fp = os.path.join(MUSIC_ROOT, "non_existent.mp3")
    response = client.get(f"/cafe/local-cover?file_path={urllib.parse.quote(fp)}")
    assert response.status_code == 404


@mock.patch("app.api.cafe._spotify")
def test_import_spotify_playlist(mock_spotify, operator_client: TestClient):
    # Mock Spotify metadata and track queries
    mock_spotify.playlist_metadata_sync.return_value = {
        "name": "My K-Pop Hits",
        "description": "Favs"
    }
    mock_spotify.playlist_tracks_sync.return_value = [
        {
            "spotify_track_id": "track_id_1",
            "title": "Song One",
            "artist": "Artist One",
            "album_name": "Album One",
            "album_art_url": "http://example.com/art1.jpg",
            "duration_ms": 180000,
            "track_uri": "spotify:track:track_id_1"
        },
        {
            "spotify_track_id": "track_id_2",
            "title": "Song Two",
            "artist": "Artist Two",
            "album_name": "Album Two",
            "album_art_url": "http://example.com/art2.jpg",
            "duration_ms": 200000,
            "track_uri": "spotify:track:track_id_2"
        }
    ]

    response = operator_client.post(
        "/ops/cafe/playlists/import-spotify",
        json={"playlist_url_or_id": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGmq7BmE"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["ok"] is True
    assert res_data["name"] == "Spotify - My K-Pop Hits"
    assert res_data["item_count"] == 2
    
    # Query database to confirm items
    pl_id = res_data["playlist_id"]
    from app import db
    items = db.get_playlist_items(pl_id)
    assert len(items) == 2
    assert items[0]["title"] == "Song One"
    assert items[0]["artist"] == "Artist One"
    assert items[1]["title"] == "Song Two"
    assert items[1]["artist"] == "Artist Two"


def test_staff_manual_track_request(operator_client: TestClient):
    response = operator_client.post(
        "/ops/cafe/request",
        json={
            "title": "운영자 테스트 곡",
            "artist": "운영자 아티스트",
            "album_art_url": "http://example.com/cover.jpg",
            "source": "spotify",
            "owned_item_id": None
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["ok"] is True
    assert res_data["request_id"] is not None
    
    # Confirm DB contents
    req_id = res_data["request_id"]
    from app import db
    req = db.get_customer_track_request(req_id)
    assert req is not None
    assert req["requested_track"] == "운영자 아티스트 - 운영자 테스트 곡"
    assert req["item_title_snapshot"] == "운영자 테스트 곡"
    assert req["artist_or_brand_snapshot"] == "운영자 아티스트"
    assert req["cover_image_url_snapshot"] == "http://example.com/cover.jpg"


def test_playlist_folder_crud_and_reordering(operator_client: TestClient):
    from app import db

    # 1. Database layer verification
    # Create folder
    folder = db.create_playlist_folder("월요일 재즈")
    assert folder is not None
    assert folder["name"] == "월요일 재즈"
    folder_id = folder["id"]

    # List folders
    folders = db.list_playlist_folders()
    assert any(f["id"] == folder_id and f["name"] == "월요일 재즈" for f in folders)

    # Update folder name
    ok = db.update_playlist_folder(folder_id, "월요일 어쿠스틱")
    assert ok is True
    updated_folder = db.get_playlist_folder(folder_id)
    assert updated_folder["name"] == "월요일 어쿠스틱"

    # Create playlist under this folder
    pl = db.create_playlist("재즈 명반 리스트", folder_id=folder_id)
    assert pl is not None
    assert pl["folder_id"] == folder_id

    # Create unassigned playlist
    pl_unassigned = db.create_playlist("미지정 리스트")
    assert pl_unassigned is not None
    assert pl_unassigned["folder_id"] is None

    # Move unassigned playlist to folder
    ok = db.update_playlist(pl_unassigned["id"], folder_id=folder_id)
    assert ok is True
    pl_moved = db.get_playlist(pl_unassigned["id"])
    assert pl_moved["folder_id"] == folder_id

    # Delete folder (Safe SET NULL behavior check)
    ok = db.delete_playlist_folder(folder_id)
    assert ok is True
    assert db.get_playlist_folder(folder_id) is None
    # Playlists folder_id should be NULL now
    assert db.get_playlist(pl["id"])["folder_id"] is None
    assert db.get_playlist(pl_unassigned["id"])["folder_id"] is None

    # Delete playlists
    db.delete_playlist(pl["id"])
    db.delete_playlist(pl_unassigned["id"])


def test_playlist_folder_api(operator_client: TestClient):
    # 2. API layer validation (OPERATOR auth required)
    # Create folder via POST
    response = operator_client.post("/ops/cafe/playlist-folders", json={"name": "화요일 팝"})
    assert response.status_code == 200
    folder_data = response.json()
    assert folder_data["name"] == "화요일 팝"
    folder_id = folder_data["id"]

    # List folder via GET
    response = operator_client.get("/ops/cafe/playlist-folders")
    assert response.status_code == 200
    tree_data = response.json()
    assert "folders" in tree_data
    assert any(f["id"] == folder_id for f in tree_data["folders"])

    # Create playlist under folder via API POST
    response = operator_client.post("/ops/cafe/playlists", json={"name": "팝 최신곡", "folder_id": folder_id})
    assert response.status_code == 200
    pl_data = response.json()
    pl_id = pl_data["id"]

    # Reorder items inside playlist
    # Add some tracks first
    from app import db
    item1_id = db.add_playlist_item(pl_id, "Track One", "Artist A", spotify_track_id="tr1")
    item2_id = db.add_playlist_item(pl_id, "Track Two", "Artist B", spotify_track_id="tr2")
    item3_id = db.add_playlist_item(pl_id, "Track Three", "Artist C", spotify_track_id="tr3")

    # Confirm initial sort order (by insertion)
    items = db.get_playlist_items(pl_id)
    assert len(items) == 3
    assert items[0]["id"] == item1_id
    assert items[1]["id"] == item2_id
    assert items[2]["id"] == item3_id

    # Reorder via PUT API
    response = operator_client.put(
        f"/ops/cafe/playlists/{pl_id}/items/order",
        json={"item_ids": [item3_id, item1_id, item2_id]}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Confirm reordered order
    reordered_items = db.get_playlist_items(pl_id)
    assert len(reordered_items) == 3
    assert reordered_items[0]["id"] == item3_id
    assert reordered_items[1]["id"] == item1_id
    assert reordered_items[2]["id"] == item2_id

    # Delete folder via DELETE API
    response = operator_client.delete(f"/ops/cafe/playlist-folders/{folder_id}")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # Cleanup
    db.delete_playlist(pl_id)
