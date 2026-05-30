import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from spotipy.exceptions import SpotifyException

from app.services.spotify import SpotifyService, _PLAYBACK_CACHE
from app.config import get_settings


def test_playback_caching_and_ttl(monkeypatch):
    """Test that playback state is cached for 5 seconds and respects TTL."""
    # Ensure service is configured so ensure_client proceeds
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    # Clear any previous cache
    _PLAYBACK_CACHE["timestamp"] = 0.0
    _PLAYBACK_CACHE["value"] = None

    svc = SpotifyService()
    mock_client = MagicMock()
    mock_client.current_playback.return_value = {
        "is_playing": True,
        "progress_ms": 1234,
        "item": {
            "id": "track_id",
            "name": "Track Title",
            "uri": "spotify:track:track_id",
            "album": {
                "name": "Album Name",
                "images": [{"url": "http://img1"}, {"url": "http://img2"}],
            },
            "artists": [{"name": "Artist Name"}],
        }
    }

    with patch.object(svc, "_ensure_client", return_value=mock_client):
        # 1. First call: should query client
        first_call = svc.current_playback_sync()
        assert first_call is not None
        assert first_call["spotify_track_id"] == "track_id"
        assert mock_client.current_playback.call_count == 1

        # 2. Second call (immediate): should return cached value and not query client again
        second_call = svc.current_playback_sync()
        assert second_call is not None
        assert second_call["spotify_track_id"] == "track_id"
        assert mock_client.current_playback.call_count == 1

        # 3. Simulate TTL expiry by patching time.time to return 6 seconds in future
        now = time.time()
        with patch("time.time", return_value=now + 6.0):
            # Third call: should query client again
            third_call = svc.current_playback_sync()
            assert third_call is not None
            assert mock_client.current_playback.call_count == 2


def test_playback_error_caching(monkeypatch):
    """Test that a failure in current_playback is cached to prevent spamming."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    _PLAYBACK_CACHE["timestamp"] = 0.0
    _PLAYBACK_CACHE["value"] = None

    svc = SpotifyService()
    mock_client = MagicMock()
    mock_client.current_playback.side_effect = Exception("Spotify API Down")

    with patch.object(svc, "_ensure_client", return_value=mock_client):
        # First call: fails and caches None
        assert svc.current_playback_sync() is None
        assert mock_client.current_playback.call_count == 1

        # Second call: returns cached None without calling Spotify again
        assert svc.current_playback_sync() is None
        assert mock_client.current_playback.call_count == 1


def test_spotify_album_tracks_http_exceptions(operator_client: TestClient, monkeypatch):
    """Test that spotipy exceptions in spotify_album_tracks are mapped to correct status codes."""
    # Ensure service is configured
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    # 1. Test 429 Rate Limit mapping
    with patch("app.services.spotify.SpotifyService.album_tracks_sync") as mock_tracks:
        # Simulate spotipy raising a SpotifyException for HTTP 429
        mock_tracks.side_effect = SpotifyException(
            http_status=429,
            code=-1,
            msg="Rate limit exceeded",
            headers={"Retry-After": "5"}
        )

        response = operator_client.get("/spotify/albums/dummy_album_id/tracks")
        assert response.status_code == 429
        assert "rate-limit" in response.json()["detail"]

    # 2. Test 502 Bad Gateway mapping (e.g. for general SpotifyException like 500)
    with patch("app.services.spotify.SpotifyService.album_tracks_sync") as mock_tracks:
        mock_tracks.side_effect = SpotifyException(
            http_status=500,
            code=-1,
            msg="Internal Server Error"
        )

        response = operator_client.get("/spotify/albums/dummy_album_id/tracks")
        assert response.status_code == 502
        assert "Spotify API error" in response.json()["detail"]

    # 3. Test generic Exception mapping (verifies NameError is avoided and maps to 502)
    with patch("app.services.spotify.SpotifyService.album_tracks_sync") as mock_tracks:
        mock_tracks.side_effect = ValueError("Something went wrong internally")

        response = operator_client.get("/spotify/albums/dummy_album_id/tracks")
        assert response.status_code == 502
        assert "Failed to fetch tracklist" in response.json()["detail"]


def test_spotify_album_tracks_caching(operator_client: TestClient, monkeypatch):
    """Test that static album track lists are cached on the server."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    # Clear previous cache
    from app.api.album_masters import _ALBUM_TRACKS_CACHE
    _ALBUM_TRACKS_CACHE.clear()

    # Mock track lists returning valid data
    dummy_tracks = [{"id": "t1", "name": "Track 1", "track_number": 1, "duration_ms": 1000, "uri": "spotify:track:t1", "artists": [{"name": "Artist 1"}]}]
    
    with patch("app.services.spotify.SpotifyService.album_tracks_sync", return_value=dummy_tracks) as mock_sync:
        # First call: should query backend/SpotifyService
        response1 = operator_client.get("/spotify/albums/test_cache_album_id/tracks")
        assert response1.status_code == 200
        assert mock_sync.call_count == 1

        # Second call: should hit the in-memory cache and not call SpotifyService again
        response2 = operator_client.get("/spotify/albums/test_cache_album_id/tracks")
        assert response2.status_code == 200
        assert mock_sync.call_count == 1
        assert response2.json() == response1.json()


def test_track_sequence_match_with_offsets():
    """Verify that _track_sequence_match supports start offsets (skits/intro tracks)."""
    from app.db.album_master_spotify import _track_sequence_match

    db_tracks = ["Song A", "Song B", "Song C"]

    # 1. Exact match at offset 0
    sp_tracks_0 = ["Song A", "Song B", "Song C"]
    assert _track_sequence_match(db_tracks, sp_tracks_0) == 3

    # 2. Match with 1 intro track (offset 1)
    sp_tracks_1 = ["Intro", "Song A", "Song B", "Song C"]
    assert _track_sequence_match(db_tracks, sp_tracks_1) == 3

    # 3. Match with 2 intro tracks/skits (offset 2)
    sp_tracks_2 = ["Intro", "Skit", "Song A", "Song B", "Song C"]
    assert _track_sequence_match(db_tracks, sp_tracks_2) == 3

    # 4. Too many intro tracks (offset 3) - should not match completely
    sp_tracks_3 = ["Intro", "Skit", "Another Skit", "Song A", "Song B", "Song C"]
    assert _track_sequence_match(db_tracks, sp_tracks_3) < 3


def test_dynamic_matching_threshold_for_singles_eps():
    """Verify that EPs/Singles with 1-2 tracks can match successfully under dynamic thresholds."""
    from app.db.album_master_spotify import _match_by_album

    mock_sp = MagicMock()
    # Mock search results returning a single BTS album
    mock_sp.search_albums_sync.return_value = [
        {
            "spotify_album_id": "bts_album_id",
            "spotify_album_uri": "spotify:album:bts_album_id",
            "name": "BTS Single Album",
            "artist": "BTS",
            "release_date": "2020-01-01",
            "image_url": "http://img1",
        }
    ]
    # Mock getting the Spotify tracks
    with patch("app.db.album_master_spotify._get_spotify_album_tracks", return_value=["Song A", "Song B"]):
        # 1. 1-track Single match (should succeed under dynamic threshold)
        res_1 = _match_by_album(mock_sp, "BTS", "BTS Single Album", ["Song A"])
        assert res_1 is not None
        assert res_1["album_id"] == "bts_album_id"

        # 2. 2-track EP match (should succeed under dynamic threshold)
        res_2 = _match_by_album(mock_sp, "BTS", "BTS Single Album", ["Song A", "Song B"])
        assert res_2 is not None
        assert res_2["album_id"] == "bts_album_id"


def test_batch_match_spotify_aborts_immediately_on_429(admin_client: TestClient, monkeypatch):
    """Verify that batch_match_spotify halts immediately and propagates 429 to the API endpoint."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    # Mock batch_match_spotify to raise SpotifyException(429)
    with patch("app.db.album_master_spotify.batch_match_spotify") as mock_batch:
        mock_batch.side_effect = SpotifyException(
            http_status=429,
            code=-1,
            msg="Rate limit hit"
        )

        response = admin_client.post("/album-masters/spotify/match?limit=10")
        assert response.status_code == 429
        assert "rate-limit" in response.json()["detail"]
        assert mock_batch.call_count == 1


def test_spotify_manual_match_endpoints(admin_client: TestClient, monkeypatch):
    """Test that manual spotify match/clear endpoints work correctly with JSON parsing."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "dummy_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "dummy_secret")
    get_settings.cache_clear()

    # Create dummy album_master
    from app.db.connection import get_conn
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO album_master (id, source_code, source_master_id, title, created_at, updated_at)
               VALUES (99999, 'MANUAL', '99999', 'Test Album Master', '2026-05-28T00:00:00Z', '2026-05-28T00:00:00Z')"""
        )
        conn.commit()

    try:
        # Test PUT /album-masters/{id}/spotify/match
        payload = {"spotify_album_id": "manual_spotify_id", "spotify_album_uri": "spotify:album:manual_spotify_id"}
        response = admin_client.put("/album-masters/99999/spotify/match", json=payload)
        assert response.status_code == 200
        assert response.json()["spotify_album_id"] == "manual_spotify_id"

        # Verify database has it
        with get_conn() as conn:
            row = conn.execute("SELECT spotify_album_id FROM album_master WHERE id = 99999").fetchone()
            assert row["spotify_album_id"] == "manual_spotify_id"

        # Test DELETE /album-masters/{id}/spotify/match
        response_delete = admin_client.delete("/album-masters/99999/spotify/match")
        assert response_delete.status_code == 200

        # Verify database is cleared
        with get_conn() as conn:
            row = conn.execute("SELECT spotify_album_id FROM album_master WHERE id = 99999").fetchone()
            assert row["spotify_album_id"] is None
    finally:
        # Cleanup
        with get_conn() as conn:
            conn.execute("DELETE FROM album_master WHERE id = 99999")
            conn.commit()


def test_match_spotify_barcode_strategy():
    """Verify that match_spotify_for_master uses the barcode strategy when a barcode is present."""
    from app.db.album_master_spotify import match_spotify_for_master
    from unittest.mock import MagicMock, patch

    mock_conn = MagicMock()
    mock_conn.execute().fetchone.side_effect = [
        {"id": 1, "title": "Test Album", "artist_or_brand": "Test Artist"},  # master query
        {"barcode": "8809632123456"},  # barcode query
    ]

    mock_sp = MagicMock()
    # Mock barcode search returning a valid match
    mock_sp.search_albums_sync.return_value = [
        {
            "spotify_album_id": "sp_barcode_id",
            "spotify_album_uri": "spotify:album:sp_barcode_id",
            "name": "Test Album",
            "artist": "Test Artist",
            "release_date": "2020",
            "image_url": "http://img",
        }
    ]

    # Mock getting the tracks from DB and Spotify
    with patch("app.db.album_master_spotify._get_tracks_for_master", return_value=["Song 1", "Song 2"]), \
         patch("app.db.album_master_spotify._get_spotify_album_tracks", return_value=["Song 1", "Song 2"]), \
         patch("app.db.album_master_spotify.utc_now_iso", return_value="2026-05-29T00:00:00Z"):
        
        result = match_spotify_for_master(mock_conn, 1, mock_sp)
        assert result["matched"] is True
        assert result["strategy"] == "barcode_search"
        assert result["spotify_album_id"] == "sp_barcode_id"
        assert result["barcode_verified"] is True


def test_match_spotify_various_artists_strategy():
    """Verify that match_spotify_for_master uses the Various Artists strategy."""
    from app.db.album_master_spotify import match_spotify_for_master
    from unittest.mock import MagicMock, patch

    mock_conn = MagicMock()
    # Master is Various Artists
    mock_conn.execute().fetchone.side_effect = [
        {"id": 2, "title": "Test Compilation", "artist_or_brand": "Various Artists"},  # master query
        None,  # barcode query (no barcode)
    ]

    mock_sp = MagicMock()
    mock_sp.search_albums_sync.return_value = [
        {
            "spotify_album_id": "sp_va_id",
            "spotify_album_uri": "spotify:album:sp_va_id",
            "name": "Test Compilation",
            "artist": "Various Artists",
            "release_date": "2020",
            "image_url": "http://img",
        }
    ]

    with patch("app.db.album_master_spotify._get_tracks_for_master", return_value=["Track One", "Track Two"]), \
         patch("app.db.album_master_spotify._get_spotify_album_tracks", return_value=["Track One", "Track Two"]), \
         patch("app.db.album_master_spotify.utc_now_iso", return_value="2026-05-29T00:00:00Z"):
        
        result = match_spotify_for_master(mock_conn, 2, mock_sp)
        assert result["matched"] is True
        assert result["strategy"] == "various_artists_search"
        assert result["spotify_album_id"] == "sp_va_id"

