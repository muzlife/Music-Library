"""Tests for SSE now-playing infrastructure in cafe.py."""
import asyncio
import pytest


def test_broadcast_updates_state_and_queues():
    """_broadcast()가 _now_playing_state를 갱신하고 모든 큐에 데이터를 넣어야 한다."""
    from app.api import cafe

    q1: asyncio.Queue = asyncio.Queue(maxsize=5)
    q2: asyncio.Queue = asyncio.Queue(maxsize=5)
    cafe._sse_clients.clear()
    cafe._sse_clients.add(q1)
    cafe._sse_clients.add(q2)

    data = {"available": True, "title": "Test Song", "artist": "Artist"}
    cafe._broadcast(data)

    assert cafe._now_playing_state == data
    assert q1.get_nowait() == data
    assert q2.get_nowait() == data

    cafe._sse_clients.clear()
    cafe._now_playing_state = None


def test_broadcast_drops_full_queue_silently():
    """큐가 가득 찬 클라이언트는 예외 없이 skip해야 한다."""
    from app.api import cafe

    q_full: asyncio.Queue = asyncio.Queue(maxsize=1)
    q_full.put_nowait({"available": False})  # 이미 가득 참
    cafe._sse_clients.clear()
    cafe._sse_clients.add(q_full)

    cafe._broadcast({"available": True, "title": "New Song"})  # 예외 없어야 함

    cafe._sse_clients.clear()
    cafe._now_playing_state = None
