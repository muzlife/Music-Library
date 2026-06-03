# Cafe Now-Playing SSE 전환 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/cafe/now-playing` 폴링 구조를 SSE + 단일 백그라운드 워커로 교체해 Spotify API 일일 호출을 17,280회 → 최대 2,880회로 줄인다.

**Architecture:** `app/api/cafe.py`에 asyncio 백그라운드 워커 하나가 Spotify adaptive 폴링(재생 중 30s / 정지 60s / 로컬 재생 중 0)을 담당하고, 상태 변경 시 `_broadcast()`로 연결된 모든 SSE 클라이언트에 push한다. 클라이언트는 `EventSource`로 교체해 폴링 `setInterval`을 제거한다.

**Tech Stack:** FastAPI `StreamingResponse`, `asyncio.Queue`, `asyncio.create_task`, `EventSource` (브라우저 내장)

**Design spec:** `docs/superpowers/specs/2026-06-03-cafe-now-playing-sse-design.md`

---

## 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `app/services/spotify.py` | `_PLAYBACK_CACHE` 제거, `return None` 제거, `import time` 제거, `current_playback_sync()` 단순화 |
| `app/api/cafe.py` | `_sse_clients`/`_now_playing_state`/`_broadcast()` 추가, `_now_playing_worker()` 추가, SSE 엔드포인트 추가, `cafe_now_playing()` 단순화, `_NOW_PLAYING_CACHE` 제거, play/pause/stop/skip 핸들러에 `_broadcast()` 삽입 |
| `app/main.py` | lifespan에서 `_now_playing_worker` asyncio task 시작 |
| `app/static/cafe_tablet.html` | `setInterval` 3s → `EventSource` |
| `app/static/ops_cafe.html` | `load()` 내 `api('/cafe/now-playing')` 호출 → `EventSource` |
| `tests/test_cafe_sse.py` | 신규: SSE 인프라 단위 테스트 |

---

## Task 1: `spotify.py` — `current_playback_sync()` 복원 및 캐시 제거

**Files:**
- Modify: `app/services/spotify.py`
- Test: `tests/test_spotify_service.py`

현재 `return None`이 임시로 삽입되어 있고 5초 캐시(`_PLAYBACK_CACHE`)가 있다.
워커가 30~60초마다 호출하므로 캐시는 불필요하다. 함수를 직접 API만 호출하도록 단순화한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_spotify_service.py`에 추가

```python
def test_current_playback_sync_calls_api_not_returns_none(monkeypatch):
    """current_playback_sync()가 return None 없이 실제 _ensure_client를 호출해야 한다."""
    from app.services.spotify import SpotifyService
    sp = SpotifyService()
    called = []
    monkeypatch.setattr(sp, '_ensure_client', lambda: called.append(1) or None)
    result = sp.current_playback_sync()
    assert result is None          # client=None 이므로 None 반환
    assert len(called) == 1        # 하지만 _ensure_client는 호출됐어야 함
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest tests/test_spotify_service.py::test_current_playback_sync_calls_api_not_returns_none -v
```
예상: `FAILED` — `assert len(called) == 1` (현재 `return None`으로 호출 안 됨)

- [ ] **Step 3: `spotify.py` 수정** — `import time`, `_PLAYBACK_CACHE`, 캐시 관련 코드 제거

`app/services/spotify.py` 상단에서 제거:
```python
# 제거할 코드 (lines 19-24)
import time

_PLAYBACK_CACHE = {
    "timestamp": 0.0,
    "value": None,
}
```

`current_playback_sync()` 전체를 아래로 교체:
```python
def current_playback_sync(self) -> dict[str, Any] | None:
    sp = self._ensure_client()
    if sp is None:
        return None
    try:
        pb = sp.current_playback()
    except Exception:
        logger.exception("spotify current_playback failed")
        return None
    if not pb or not pb.get("is_playing"):
        return None
    item = pb.get("item") or {}
    album = item.get("album", {})
    images = album.get("images") or []
    return {
        "spotify_track_id": item.get("id"),
        "title": item.get("name"),
        "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
        "album_name": album.get("name"),
        "album_art_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
        "duration_ms": item.get("duration_ms"),
        "position_ms": pb.get("progress_ms"),
        "track_uri": item.get("uri"),
        "is_playing": True,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_spotify_service.py::test_current_playback_sync_calls_api_not_returns_none -v
```
예상: `PASSED`

- [ ] **Step 5: 구문 검사**

```bash
python -m py_compile app/services/spotify.py && echo OK
```

- [ ] **Step 6: 커밋**

```bash
git add app/services/spotify.py tests/test_spotify_service.py
git commit -m "refactor(spotify): remove polling suspension and internal playback cache"
```

---

## Task 2: `cafe.py` — SSE 상태 레지스트리 및 `_broadcast()` 추가

**Files:**
- Modify: `app/api/cafe.py` (lines 86-89, `_NOW_PLAYING_CACHE` 블록)
- Create: `tests/test_cafe_sse.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cafe_sse.py` 신규 생성

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_cafe_sse.py -v
```
예상: `ERROR` — `cafe._sse_clients` 존재하지 않음

- [ ] **Step 3: `cafe.py` 수정** — 기존 캐시 블록을 SSE 상태 레지스트리로 교체

`app/api/cafe.py` lines 86-89 (`_NOW_PLAYING_CACHE` 블록)를 아래로 교체:
```python
# ── SSE now-playing state ─────────────────────────────────────────

_sse_clients: set[asyncio.Queue] = set()
_now_playing_state: dict | None = None


def _broadcast(data: dict) -> None:
    """Push now-playing state to all connected SSE clients."""
    global _now_playing_state
    _now_playing_state = data
    for q in list(_sse_clients):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass
```

`import time as _time` (line 87 바로 위) 도 함께 제거한다.

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_cafe_sse.py -v
```
예상: `PASSED` (2 tests)

- [ ] **Step 5: 구문 검사**

```bash
python -m py_compile app/api/cafe.py && echo OK
```

- [ ] **Step 6: 커밋**

```bash
git add app/api/cafe.py tests/test_cafe_sse.py
git commit -m "feat(cafe): add SSE client registry and _broadcast()"
```

---

## Task 3: `cafe.py` — `_now_playing_worker()` 추가

**Files:**
- Modify: `app/api/cafe.py`
- Modify: `tests/test_cafe_sse.py`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_cafe_sse.py`에 추가

```python
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
```

- [ ] **Step 2: pytest-asyncio 설정 확인**

```bash
python -m pytest tests/test_cafe_sse.py::test_worker_broadcasts_spotify_state -v
```
예상: `ERROR` — `_now_playing_worker` 존재하지 않음 또는 asyncio 설정 오류

만약 `PytestUnraisableExceptionWarning` 또는 asyncio 모드 오류가 나면 `pytest.ini` 또는 `pyproject.toml`에 추가:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: `cafe.py`에 `_now_playing_worker()` 추가**

`_broadcast()` 함수 바로 뒤에 추가:
```python
async def _now_playing_worker() -> None:
    """Single background task — owns all Spotify polling and local state checks.

    Adaptive intervals:
      local playing  → 5s  (VLC socket check, no external API)
      Spotify playing → 30s
      nothing playing → 60s
    """
    prev_state: dict | None = None
    loop = asyncio.get_event_loop()

    while True:
        interval = 60
        try:
            local = _local.current_track()
            if local and local.get("is_playing"):
                state: dict = {"available": True, **local}
                interval = 5
            else:
                pb = await loop.run_in_executor(None, _spotify.current_playback_sync)
                if pb:
                    state = {"available": True, "source": "spotify", **pb}
                    interval = 30
                else:
                    state = {"available": False}
                    interval = 60

            if state != prev_state:
                prev_state = state
                _broadcast(state)

        except Exception:
            logger.exception("now-playing worker error")
            interval = 60

        await asyncio.sleep(interval)
```

- [ ] **Step 4: `logger` 임포트 확인**

`cafe.py` 상단에 `logger`가 없으면 추가:
```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_cafe_sse.py -v
```
예상: `PASSED` (4 tests)

- [ ] **Step 6: 구문 검사**

```bash
python -m py_compile app/api/cafe.py && echo OK
```

- [ ] **Step 7: 커밋**

```bash
git add app/api/cafe.py tests/test_cafe_sse.py
git commit -m "feat(cafe): add _now_playing_worker with adaptive Spotify polling"
```

---

## Task 4: `cafe.py` — SSE 엔드포인트 추가 및 `cafe_now_playing()` 단순화

**Files:**
- Modify: `app/api/cafe.py`
- Modify: `tests/test_cafe_sse.py`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_cafe_sse.py`에 추가

```python
def test_now_playing_rest_returns_worker_state(monkeypatch):
    """GET /cafe/now-playing은 워커가 관리하는 _now_playing_state를 반환해야 한다."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import cafe

    cafe._now_playing_state = {"available": True, "title": "Cached Song"}
    client = TestClient(app)
    resp = client.get("/cafe/now-playing")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Cached Song"

    cafe._now_playing_state = None


def test_now_playing_rest_returns_unavailable_when_no_state():
    """_now_playing_state가 None이면 {"available": False}를 반환해야 한다."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import cafe

    cafe._now_playing_state = None
    client = TestClient(app)
    resp = client.get("/cafe/now-playing")
    assert resp.status_code == 200
    assert resp.json() == {"available": False}
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_cafe_sse.py::test_now_playing_rest_returns_worker_state -v
```
예상: `FAILED` — 현재 `cafe_now_playing()`이 Spotify를 직접 호출하므로 `_now_playing_state`와 무관

- [ ] **Step 3: `cafe.py` — `cafe_now_playing()` 단순화 (lines 237-254)**

기존 함수 전체를 교체:
```python
@router.get("/cafe/now-playing")
def cafe_now_playing() -> dict[str, Any]:
    """Public: current playback info — served from worker-managed state."""
    if _now_playing_state is not None:
        return _now_playing_state
    return {"available": False}
```

- [ ] **Step 4: `cafe.py` — SSE 엔드포인트 추가**

`cafe_now_playing()` 바로 뒤에 추가:
```python
@router.get("/cafe/now-playing/stream")
async def cafe_now_playing_stream(request: Request):
    """Public: SSE stream — pushes now-playing state on every change."""
    from fastapi.responses import StreamingResponse

    async def generate():
        queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        _sse_clients.add(queue)
        try:
            initial = _now_playing_state if _now_playing_state is not None else {"available": False}
            yield f"data: {json.dumps(initial, ensure_ascii=False)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _sse_clients.discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_cafe_sse.py -v
```
예상: `PASSED` (6 tests)

- [ ] **Step 6: 구문 검사**

```bash
python -m py_compile app/api/cafe.py && echo OK
```

- [ ] **Step 7: 커밋**

```bash
git add app/api/cafe.py tests/test_cafe_sse.py
git commit -m "feat(cafe): add SSE endpoint and simplify now-playing REST handler"
```

---

## Task 5: `cafe.py` — play/pause/stop 핸들러에 `_broadcast()` 삽입

**Files:**
- Modify: `app/api/cafe.py`

play/pause/stop 명령 직후 즉시 상태를 push해 워커 폴링 주기를 기다리지 않도록 한다.

- [ ] **Step 1: `staff_play_local` 수정** (line ~284, `ok = _local.play(file_path)` 직후)

```python
    ok = _local.play(file_path)
    if ok:
        track = _local.current_track()
        if track:
            _broadcast({"available": True, **track})
    return {"ok": ok, "file_path": file_path}
```

- [ ] **Step 2: `staff_pause_local` 수정** (line ~292, `_local.pause()` 직후)

```python
    ok = _local.pause()
    _broadcast({"available": False})
    return {"ok": ok}
```

- [ ] **Step 3: `staff_stop_local` 수정** (line ~299, `_local.stop()` 직후)

```python
    _local.stop()
    _broadcast({"available": False})
    return {"ok": True}
```

- [ ] **Step 4: `staff_pause` (Spotify) 수정** (line ~388, `_spotify.pause_sync()` 직후)

```python
    ok = _spotify.pause_sync()
    _broadcast({"available": False})
    return {"ok": ok}
```

- [ ] **Step 5: `staff_skip` 수정** (line ~396, `_spotify.pause_sync()` 직후)

```python
    _spotify.pause_sync()
    _broadcast({"available": False})
    return {"ok": True, "note": "paused — select next track manually"}
```

- [ ] **Step 6: `staff_playlist_play_next` 수정** (line ~610, play 호출 직후)

```python
    if item.get("spotify_track_uri"):
        _spotify.play_sync(item["spotify_track_uri"])
        _broadcast({"available": True, "source": "spotify",
                    "title": item.get("title", ""), "artist": item.get("artist", ""),
                    "album_art_url": item.get("album_art_url"), "is_playing": True})
    elif item.get("local_file_path"):
        _local.play(item["local_file_path"])
        track = _local.current_track()
        if track:
            _broadcast({"available": True, **track})
    return {"ok": True, "item": item}
```

- [ ] **Step 7: 구문 검사**

```bash
python -m py_compile app/api/cafe.py && echo OK
```

- [ ] **Step 8: 전체 테스트 실행**

```bash
python -m pytest tests/test_cafe_sse.py -v
```
예상: 전부 `PASSED`

- [ ] **Step 9: 커밋**

```bash
git add app/api/cafe.py
git commit -m "feat(cafe): broadcast now-playing state immediately on play/pause/stop"
```

---

## Task 6: `main.py` — lifespan에 워커 태스크 등록

**Files:**
- Modify: `app/main.py` (lifespan 함수, line ~177)

- [ ] **Step 1: import 추가**

`main.py` 상단 import 블록에 추가 (다른 api 임포트와 함께):
```python
from .api.cafe import _now_playing_worker as _cafe_now_playing_worker
```

- [ ] **Step 2: lifespan에 태스크 등록**

`_start_auto_backup_worker()` 호출 바로 뒤에 추가:
```python
    _start_metadata_sync_worker()
    _start_auto_backup_worker()
    asyncio.create_task(_cafe_now_playing_worker())   # SSE now-playing worker
```

- [ ] **Step 3: 구문 검사**

```bash
python -m py_compile app/main.py && echo OK
```

- [ ] **Step 4: 서버 기동 확인**

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
sleep 3
curl -s http://127.0.0.1:8099/cafe/now-playing
kill %1
```
예상: `{"available": false}` 또는 현재 재생 상태 JSON

- [ ] **Step 5: 커밋**

```bash
git add app/main.py
git commit -m "feat(main): start cafe now-playing SSE worker on app startup"
```

---

## Task 7: `cafe_tablet.html` — EventSource 전환

**Files:**
- Modify: `app/static/cafe_tablet.html` (lines 164-173)

- [ ] **Step 1: 기존 `setInterval` 교체**

`cafe_tablet.html` lines 164-174의 블록:
```javascript
setInterval(function(){
  fetch('/cafe/now-playing').then(function(r){return r.json()}).then(function(d){
    var np = document.getElementById('np');
    if(d.available){
      var lyrBtn = d.source==='local'&&d.file_path?'<button onclick="showLyrics(\''+d.file_path+'\')" style="margin-top:10px;background:var(--surface);border:1px solid var(--border);color:var(--accent);padding:6px 16px;border-radius:20px;font-size:.78rem;cursor:pointer">📝 가사 보기</button>':'';
np.innerHTML = '<img src="'+(d.album_art_url||'')+'" alt=""><div class="song">'+d.title+'</div><div class="artist">'+d.artist+'</div><div class="album">'+d.album_name+'</div>'+lyrBtn;
    } else {
      np.innerHTML = '<div class="idle">♪ 재생 중인 곡이 없습니다</div>';
    }
  }).catch(function(){});
}, 3000);
```

아래로 교체:
```javascript
(function() {
  function _renderNowPlaying(d) {
    var np = document.getElementById('np');
    if (d.available) {
      var lyrBtn = d.source==='local'&&d.file_path
        ? '<button onclick="showLyrics(\''+d.file_path+'\')" style="margin-top:10px;background:var(--surface);border:1px solid var(--border);color:var(--accent);padding:6px 16px;border-radius:20px;font-size:.78rem;cursor:pointer">📝 가사 보기</button>'
        : '';
      np.innerHTML = '<img src="'+(d.album_art_url||'')+'" alt="">'
        +'<div class="song">'+d.title+'</div>'
        +'<div class="artist">'+d.artist+'</div>'
        +'<div class="album">'+d.album_name+'</div>'
        +lyrBtn;
    } else {
      np.innerHTML = '<div class="idle">♪ 재생 중인 곡이 없습니다</div>';
    }
  }
  var _npEs = new EventSource('/cafe/now-playing/stream');
  _npEs.onmessage = function(e) { _renderNowPlaying(JSON.parse(e.data)); };
})();
```

- [ ] **Step 2: 커밋**

```bash
git add app/static/cafe_tablet.html
git commit -m "feat(tablet): replace now-playing polling with SSE EventSource"
```

---

## Task 8: `ops_cafe.html` — EventSource 전환

**Files:**
- Modify: `app/static/ops_cafe.html` (lines 1084-1099, `load()` 내부)

`load()` 함수 안의 `api('/cafe/now-playing')` 호출은 "대기열에 활성 재생 요청이 없을 때" 폴백으로만 사용된다. 이 부분만 SSE로 교체하고 나머지 `load()` 로직은 그대로 둔다.

- [ ] **Step 1: `ops_cafe.html` 내 now-playing 폴백 교체**

lines 1083-1099의 블록:
```javascript
  } else {
    // Check Spotify status from API if no local active playing request
    api('/cafe/now-playing').then(function(pb) {
      if (pb.available) {
        document.getElementById('now-title').textContent = pb.track_title || pb.title || '';
        document.getElementById('now-artist').textContent = pb.artist || '';
        document.getElementById('now-cover').src = pb.album_art_url || "data:image/svg+xml;...";
        document.getElementById('now-source').textContent = pb.source ? pb.source.toUpperCase() : 'SPOTIFY';
        fetchLyrics(pb.artist || '', pb.track_title || pb.title || '');
      } else {
        document.getElementById('now-title').textContent = '재생 중인 곡 없음';
        document.getElementById('now-artist').textContent = '대기열에서 [재생]을 누르거나 재생목록을 실행하세요.';
        document.getElementById('now-cover').src = "data:image/svg+xml;...";
        document.getElementById('now-source').textContent = 'OFFLINE';
        document.getElementById('lyrics-text').textContent = '가사가 없습니다.';
      }
    });
  }
```

`} else {` 블록 내부를 아래로 교체 (`api('/cafe/now-playing')` 호출 제거, SSE에서 업데이트):
```javascript
  } else {
    // now-playing is updated via SSE (_opsNpEs below) — nothing to do here
  }
```

`setInterval(load, 10000);` 바로 뒤에 SSE 구독 추가:
```javascript
setInterval(load, 10000);

// SSE: now-playing push (replaces polling inside load())
(function() {
  function _opsRenderNowPlaying(pb) {
    if (pb.available) {
      document.getElementById('now-title').textContent = pb.track_title || pb.title || '';
      document.getElementById('now-artist').textContent = pb.artist || '';
      document.getElementById('now-cover').src = pb.album_art_url
        || "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100%' height='100%' fill='%231a2538'/><text x='50%' y='55%' font-family='sans-serif' font-size='12' fill='%2394a3b8' text-anchor='middle'>No Cover</text></svg>";
      document.getElementById('now-source').textContent = pb.source ? pb.source.toUpperCase() : 'SPOTIFY';
      fetchLyrics(pb.artist || '', pb.track_title || pb.title || '');
    } else {
      document.getElementById('now-title').textContent = '재생 중인 곡 없음';
      document.getElementById('now-artist').textContent = '대기열에서 [재생]을 누르거나 재생목록을 실행하세요.';
      document.getElementById('now-cover').src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100%' height='100%' fill='%231a2538'/><text x='50%' y='55%' font-family='sans-serif' font-size='12' fill='%2394a3b8' text-anchor='middle'>No Cover</text></svg>";
      document.getElementById('now-source').textContent = 'OFFLINE';
      document.getElementById('lyrics-text').textContent = '가사가 없습니다.';
    }
  }
  var _opsNpEs = new EventSource('/cafe/now-playing/stream');
  _opsNpEs.onmessage = function(e) { _opsRenderNowPlaying(JSON.parse(e.data)); };
})();
```

- [ ] **Step 2: 커밋**

```bash
git add app/static/ops_cafe.html
git commit -m "feat(ops-cafe): replace now-playing polling with SSE EventSource"
```

---

## Task 9: QA 배포 및 스모크 테스트

**Files:** QA 서버 (`~/apps/hahahoho-qa/`)

- [ ] **Step 1: 변경된 5개 파일을 QA 서버에 복사**

```bash
for f in app/services/spotify.py app/api/cafe.py app/main.py \
          app/static/cafe_tablet.html app/static/ops_cafe.html; do
  scp $f macmini-m4:~/apps/hahahoho-qa/$f
done
```
(macmini-m4는 QA 서버 호스트명으로 조정)

- [ ] **Step 2: 구문 검사**

```bash
ssh macmini-m4 "cd ~/apps/hahahoho-qa && python3 -m py_compile app/services/spotify.py app/api/cafe.py app/main.py && echo ALL OK"
```

- [ ] **Step 3: QA 서버 재시작**

```bash
ssh macmini-m4 "PID=\$(pgrep -f 'uvicorn.*8100'); kill -TERM \$PID; sleep 5; ps -eo pid,etime,command | grep 'uvicorn.*8100' | grep -v grep"
```

- [ ] **Step 4: SSE 엔드포인트 연결 확인**

```bash
curl -N --max-time 5 https://qa-library.muzlife.com/cafe/now-playing/stream
```
예상: `data: {"available": false}` 또는 현재 재생 상태 출력 후 `: keepalive` 반복

- [ ] **Step 5: REST 엔드포인트 정상 확인**

```bash
curl -s https://qa-library.muzlife.com/cafe/now-playing
```
예상: `{"available": false}` 또는 재생 중 상태

- [ ] **Step 6: 브라우저 확인**

`https://qa-library.muzlife.com/cafe/tablet` 열어서:
- 개발자 도구 → Network → EventStream 탭에서 `/cafe/now-playing/stream` 연결 확인
- `setInterval` 3초 폴링이 사라지고 SSE로 대체됐는지 확인

- [ ] **Step 7: 상용 서버 적용 (macmini2018)**

```bash
for f in app/services/spotify.py app/api/cafe.py app/main.py \
          app/static/cafe_tablet.html app/static/ops_cafe.html; do
  scp $f macmini2018.local:~/apps/hahahoho-prod/$f
done
ssh macmini2018.local "cd ~/apps/hahahoho-prod && python3 -m py_compile app/services/spotify.py app/api/cafe.py app/main.py && echo OK"
ssh macmini2018.local "PID=\$(pgrep -f 'uvicorn.*8000'); kill -TERM \$PID; sleep 6; curl -s -w 'HTTP:%{http_code}' http://localhost:8000/"
```
예상: `HTTP:401`
