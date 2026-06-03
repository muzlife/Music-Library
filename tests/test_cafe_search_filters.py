from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


def test_cafe_search_src_local(client: TestClient) -> None:
    """Test /cafe/search with src=local option only queries local scanner."""
    with patch("app.api.cafe._spotify") as mock_spotify, \
         patch("app.api.cafe._local") as mock_local, \
         patch("app.api.cafe.db") as mock_db:
        
        # Setup mocks
        mock_local.scan_files.return_value = [{"source": "local", "title": "Local Song", "artist": "Local Artist", "file_path": "/path/to/song.mp3"}]
        mock_db.find_tracks_by_tag.return_value = []
        
        resp = client.get("/cafe/search?q=test&src=local")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify result
        assert data["query"] == "test"
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Local Song"
        
        # Spotify search should not be called
        mock_spotify.search_tracks_sync.assert_not_called()
        mock_local.scan_files.assert_called_once_with("test", limit=10)


def test_cafe_search_src_spotify(client: TestClient) -> None:
    """Test /cafe/search with src=spotify option only queries Spotify."""
    with patch("app.api.cafe._spotify") as mock_spotify, \
         patch("app.api.cafe._local") as mock_local, \
         patch("app.api.cafe.db") as mock_db:
        
        # Setup mocks
        mock_spotify.search_tracks_sync.return_value = [{"title": "Spotify Song", "artist": "Spotify Artist"}]
        
        resp = client.get("/cafe/search?q=test&src=spotify")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify result
        assert data["query"] == "test"
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Spotify Song"
        assert data["items"][0]["source"] == "spotify"
        
        # Local scanning should not be called
        mock_local.scan_files.assert_not_called()
        mock_db.find_tracks_by_tag.assert_not_called()
        mock_spotify.search_tracks_sync.assert_called_once_with("test", limit=10)


def test_cafe_search_src_all(client: TestClient) -> None:
    """Test /cafe/search with src=all queries both sources."""
    with patch("app.api.cafe._spotify") as mock_spotify, \
         patch("app.api.cafe._local") as mock_local, \
         patch("app.api.cafe.db") as mock_db:
        
        mock_spotify.search_tracks_sync.return_value = [{"title": "Spotify Song", "artist": "Spotify Artist"}]
        mock_local.scan_files.return_value = [{"source": "local", "title": "Local Song", "artist": "Local Artist"}]
        mock_db.find_tracks_by_tag.return_value = []
        
        resp = client.get("/cafe/search?q=test&src=all")
        assert resp.status_code == 200
        data = resp.json()
        
        # Both results should be present
        titles = [item["title"] for item in data["items"]]
        assert "Spotify Song" in titles
        assert "Local Song" in titles
        
        # Both mock services must be called
        mock_spotify.search_tracks_sync.assert_called_once_with("test", limit=10)
        mock_local.scan_files.assert_called_once_with("test", limit=10)


@pytest.mark.skip(reason="unimplemented")
def test_playlist_folders_includes_album_art_urls(operator_client: TestClient) -> None:
    """Test /ops/cafe/playlist-folders returns album_art_urls list for each playlist."""
    # Ensure tables and initial state are ready
    from app import db
    db.ensure_startup_db_ready()

    # 1. Create a dummy playlist
    pl = db.create_playlist("Art Test Playlist")
    pl_id = pl["id"]

    try:
        # 2. Add some items with album cover art
        db.add_playlist_item(pl_id, "Track 1", "Artist 1", album_art_url="http://example.com/art1.jpg")
        db.add_playlist_item(pl_id, "Track 2", "Artist 2", album_art_url="http://example.com/art2.jpg")
        db.add_playlist_item(pl_id, "Track 3", "Artist 3", album_art_url=None) # Null art
        db.add_playlist_item(pl_id, "Track 4", "Artist 4", album_art_url="http://example.com/art4.jpg")
        db.add_playlist_item(pl_id, "Track 5", "Artist 5", album_art_url="http://example.com/art5.jpg")
        db.add_playlist_item(pl_id, "Track 6", "Artist 6", album_art_url="http://example.com/art6.jpg")

        # 3. Call the folders endpoint
        resp = operator_client.get("/ops/cafe/playlist-folders")
        assert resp.status_code == 200
        data = resp.json()

        # Find our playlist in 'unassigned'
        pl_data = next((p for p in data["unassigned"] if p["id"] == pl_id), None)
        assert pl_data is not None
        assert "album_art_urls" in pl_data
        
        # Verify it has up to 4 non-null urls
        urls = pl_data["album_art_urls"]
        assert len(urls) == 4
        assert "http://example.com/art1.jpg" in urls
        assert "http://example.com/art2.jpg" in urls
        assert "http://example.com/art4.jpg" in urls
        assert "http://example.com/art5.jpg" in urls
        assert "http://example.com/art6.jpg" not in urls # Only top 4 non-null covers
        
    finally:
        # Cleanup
        db.delete_playlist(pl_id)
