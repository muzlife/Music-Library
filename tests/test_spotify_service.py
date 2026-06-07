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


def test_current_playback_sync_calls_api_not_returns_none(monkeypatch):
    """current_playback_sync()가 return None 없이 실제 _ensure_client를 호출해야 한다."""
    from app.services.spotify import SpotifyService
    sp = SpotifyService()
    called = []
    monkeypatch.setattr(sp, '_ensure_client', lambda: called.append(1) or None)
    result = sp.current_playback_sync()
    assert result is None          # client=None 이므로 None 반환
    assert len(called) == 1        # 하지만 _ensure_client는 호출됐어야 함


def test_spotify_service_configured_initializes(monkeypatch):
    """When env vars are set, configured=True (spotipy init happens lazily)."""
    monkeypatch.setenv("SPOTIFY_ENABLED", "true")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost:8100/callback")
    get_settings.cache_clear()
    svc = SpotifyService()
    assert svc.configured is True
    assert svc.client_id == "test_id"
    assert svc.client_secret == "test_secret"
    assert svc.redirect_uri == "http://localhost:8100/callback"


def test_current_playback_sync_returns_dict_when_playing(monkeypatch):
    """재생 중일 때 올바른 딕셔너리를 반환해야 한다."""
    sp = SpotifyService()

    mock_pb = {
        "is_playing": True,
        "progress_ms": 45000,
        "item": {
            "id": "track123",
            "name": "Test Track",
            "uri": "spotify:track:track123",
            "duration_ms": 200000,
            "artists": [{"name": "Test Artist"}],
            "album": {
                "name": "Test Album",
                "images": [{"url": "http://img/large"}, {"url": "http://img/medium"}],
            },
        },
    }

    class FakeClient:
        def current_playback(self):
            return mock_pb

    monkeypatch.setattr(sp, '_ensure_client', lambda: FakeClient())
    result = sp.current_playback_sync()

    assert result is not None
    assert result["title"] == "Test Track"
    assert result["artist"] == "Test Artist"
    assert result["album_name"] == "Test Album"
    assert result["album_art_url"] == "http://img/medium"  # images[1]
    assert result["duration_ms"] == 200000
    assert result["position_ms"] == 45000
    assert result["is_playing"] is True
