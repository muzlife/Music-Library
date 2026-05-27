import pytest
from app.config import get_settings
from app.services.spotify import SpotifyService


def test_spotify_service_not_configured_returns_empty(monkeypatch):
    """When no Spotify env vars are set, configured=False and search returns []."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "")
    get_settings.cache_clear()
    svc = SpotifyService()
    assert svc.configured is False
    assert svc.search_tracks_sync("test") == []
    assert svc.get_recommendations_sync("x") == []
    assert svc.play_sync("x") is False
    assert svc.pause_sync() is False
    assert svc.current_playback_sync() is None


def test_spotify_service_configured_initializes(monkeypatch):
    """When env vars are set, configured=True (spotipy init happens lazily)."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost:8100/callback")
    get_settings.cache_clear()
    svc = SpotifyService()
    assert svc.configured is True
    assert svc.client_id == "test_id"
    assert svc.client_secret == "test_secret"
    assert svc.redirect_uri == "http://localhost:8100/callback"
