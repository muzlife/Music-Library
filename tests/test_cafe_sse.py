"""Tests for SSE now-playing infrastructure in cafe.py."""
import asyncio
import pytest


@pytest.fixture(autouse=True)
def _cleanup_cafe_global_state():
    """각 테스트 전후 cafe 모듈 전역 상태를 초기화한다."""
    from app.api import cafe
    cafe._sse_clients.clear()
    cafe._now_playing_state = None
    yield
    cafe._sse_clients.clear()
    cafe._now_playing_state = None


def test_broadcast_updates_state_and_queues():
    """_broadcast()가 _now_playing_state를 갱신하고 모든 큐에 데이터를 넣어야 한다."""
    from app.api import cafe

    q1: asyncio.Queue = asyncio.Queue(maxsize=5)
    q2: asyncio.Queue = asyncio.Queue(maxsize=5)
    cafe._sse_clients.add(q1)
    cafe._sse_clients.add(q2)

    data = {"available": True, "title": "Test Song", "artist": "Artist"}
    cafe._broadcast(data)

    assert cafe._now_playing_state == data
    assert q1.get_nowait() == data
    assert q2.get_nowait() == data


def test_broadcast_drops_full_queue_silently():
    """큐가 가득 찬 클라이언트는 예외 없이 skip해야 한다."""
    from app.api import cafe

    q_full: asyncio.Queue = asyncio.Queue(maxsize=1)
    q_full.put_nowait({"available": False})  # 이미 가득 참
    cafe._sse_clients.add(q_full)

    cafe._broadcast({"available": True, "title": "New Song"})  # 예외 없어야 함


@pytest.mark.asyncio
async def test_worker_broadcasts_spotify_state(monkeypatch):
    """워커가 Spotify 재생 상태를 감지해 broadcast해야 한다."""
    from app.api import cafe

    broadcast_calls = []
    monkeypatch.setattr(cafe, '_broadcast', lambda d: broadcast_calls.append(d))
    monkeypatch.setattr(cafe._local, 'current_track', lambda: None)

    spotify_state = {
        "spotify_track_id": "abc123",
        "title": "Test Track",
        "artist": "Test Artist",
        "album_name": "Test Album",
        "album_art_url": None,
        "duration_ms": 200000,
        "position_ms": 1000,
        "track_uri": "spotify:track:abc123",
        "is_playing": True,
    }
    monkeypatch.setattr(cafe._spotify, 'current_playback_sync', lambda: spotify_state)

    task = asyncio.create_task(cafe._now_playing_worker())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(broadcast_calls) == 1
    assert broadcast_calls[0]["available"] is True
    assert broadcast_calls[0]["source"] == "spotify"
    assert broadcast_calls[0]["title"] == "Test Track"


@pytest.mark.asyncio
async def test_worker_prefers_local_over_spotify(monkeypatch):
    """로컬 재생 중이면 Spotify를 호출하지 않고 로컬 상태를 broadcast해야 한다."""
    from app.api import cafe

    broadcast_calls = []
    spotify_calls = []
    monkeypatch.setattr(cafe, '_broadcast', lambda d: broadcast_calls.append(d))
    monkeypatch.setattr(cafe._spotify, 'current_playback_sync',
                        lambda: spotify_calls.append(1) or None)
    monkeypatch.setattr(cafe._local, 'current_track', lambda: {
        "source": "local",
        "title": "Local Song",
        "artist": "Local Artist",
        "is_playing": True,
        "file_path": "/music/test.mp3",
    })

    task = asyncio.create_task(cafe._now_playing_worker())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(broadcast_calls) == 1
    assert broadcast_calls[0]["source"] == "local"
    assert len(spotify_calls) == 0  # Spotify 미호출
