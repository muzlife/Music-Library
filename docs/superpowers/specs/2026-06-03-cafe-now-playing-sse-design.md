# Cafe Now-Playing SSE 전환 설계

**날짜**: 2026-06-03  
**목적**: `/cafe/now-playing` 폴링 구조를 SSE + 단일 백그라운드 워커로 교체해 Spotify API 호출을 최소화

---

## 배경

현재 `cafe_tablet.html`(3초)·`ops_cafe.html`(10초)이 `/cafe/now-playing`을 각자 폴링하고, 서버는 5초 캐시를 통해 Spotify `current_playback`을 최대 17,280회/일 호출한다. Spotify 일일 쿼터를 소진해 배치 매칭까지 차단되는 문제가 발생함.

---

## 목표

- Spotify API 호출을 단일 백그라운드 루프로 집중 (클라이언트 수 무관)
- 재생 상태에 따른 adaptive 폴링으로 불필요한 호출 제거
- 로컬 재생 중 Spotify 호출 완전 중단
- 클라이언트는 변경 시에만 수신 (polling → push)

---

## 아키텍처

```
app 시작
  └─ asyncio.create_task(_now_playing_worker())   # 전체에 1개

_now_playing_worker
  ├─ 로컬 재생 중  → 5초 폴링 (VLC 소켓, 외부 API 없음)
  ├─ Spotify 재생 중 → 30초마다 current_playback 호출
  ├─ 무재생       → 60초마다 Spotify 확인
  └─ 상태 변경 감지 → _broadcast() → 전체 SSE 클라이언트 push

GET /cafe/now-playing/stream   # 새 SSE 엔드포인트 (공개)
GET /cafe/now-playing          # 기존 REST 유지, 워커 상태 반환
```

play/stop/pause API 핸들러는 플레이어 조작 직후 `_broadcast()` 직접 호출 — 워커 폴링 주기를 기다리지 않고 즉시 push.

대상 핸들러:
- `staff_play_local` — 로컬 파일 재생 시작
- `staff_pause_local` — 로컬 일시정지
- `staff_stop_local` — 로컬 정지
- Spotify play (track request fulfillment, `_spotify.play_sync()` 호출 지점)
- `staff_pause_spotify` — Spotify 일시정지

---

## 컴포넌트 설계

### 1. 모듈 레벨 상태 (`app/api/cafe.py`)

```python
_sse_clients: set[asyncio.Queue] = set()   # 연결된 SSE 클라이언트 큐
_now_playing_state: dict | None = None     # 마지막으로 broadcast된 상태
```

### 2. `_broadcast(data: dict)`

```python
def _broadcast(data: dict) -> None:
    global _now_playing_state
    _now_playing_state = data
    for q in list(_sse_clients):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass   # 느린 클라이언트는 drop
```

### 3. `_now_playing_worker()` (asyncio coroutine)

```
while True:
    try:
        local = _local.current_track()
        if local and local.get("is_playing"):
            state = {"available": True, **local}
            interval = 5          # 로컬 종료 감지용, 외부 API 없음
        else:
            pb = await run_in_executor(_spotify.current_playback_sync)
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
        interval = 60   # 오류 시 60초 대기 후 재시도

    await asyncio.sleep(interval)
```

워커는 `while True` 안에서 예외를 잡아 재시작 — 태스크 자체는 죽지 않음.

### 4. SSE 엔드포인트

```
GET /cafe/now-playing/stream
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

- 연결 즉시 `_now_playing_state` (또는 `{"available": False}`) 전송
- 큐에서 데이터 수신 시 `data: <json>\n\n` 전송
- 25초마다 `: keepalive\n\n` (프록시 타임아웃 방지)
- 연결 끊김 감지 시 `finally`에서 큐 제거
- 클라이언트 큐 maxsize=5 (느린 클라이언트 버퍼 제한)

### 5. 기존 REST 엔드포인트 유지

`GET /cafe/now-playing`은 `_now_playing_state`를 즉시 반환하도록 단순화. Spotify API 직접 호출 없음.

---

## 파일 변경 범위

| 파일 | 변경 내용 |
|------|---------|
| `app/api/cafe.py` | `_sse_clients`, `_broadcast()`, `_now_playing_worker()` 추가; SSE 엔드포인트 추가; play/stop/pause 핸들러에 `_broadcast()` 삽입; `_NOW_PLAYING_CACHE` 제거; `cafe_now_playing()` 단순화 |
| `app/main.py` | startup 이벤트에서 `asyncio.create_task(_now_playing_worker())` |
| `app/services/spotify.py` | `current_playback_sync()` 상단의 `return None` 제거; 내부 `_PLAYBACK_CACHE` 5s 캐시 제거 (워커가 호출 빈도 제어하므로 불필요) |
| `app/static/cafe_tablet.html` | `setInterval` 3s now-playing 제거 → `EventSource('/cafe/now-playing/stream')` |
| `app/static/ops_cafe.html` | `setInterval` 10s의 now-playing 호출 부분 → `EventSource` |

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| SSE 클라이언트 연결 끊김 | `finally`에서 큐 제거, 브라우저 자동 재연결 |
| Spotify API 오류 | 이전 상태 유지, 60초 후 재시도, 로그 |
| 워커 예외 | `try/except`로 잡아 로그 후 60초 대기, `while True`로 재시작 |
| 프록시 타임아웃 | 25초마다 SSE keepalive 코멘트 전송 |
| 큐 가득 참 | `put_nowait` 실패 시 해당 클라이언트 drop (silent) |

---

## 예상 Spotify API 호출량

| 시나리오 | 호출/일 |
|---------|--------|
| 현재 (정지 전) | ~17,280 |
| 전환 후 — 하루 12시간 Spotify 재생 | 1,440 |
| 전환 후 — 하루 12시간 로컬 재생 | 720 (나머지 12시간 idle 60s) |
| 전환 후 — 최악 (24시간 Spotify 재생) | 2,880 |

---

## 구현 순서

1. `spotify.py` — `return None` 및 내부 캐시 제거
2. `cafe.py` — 상태 레지스트리, `_broadcast()`, 워커, SSE 엔드포인트, 핸들러 수정
3. `main.py` — startup 태스크 등록
4. `cafe_tablet.html` — EventSource 전환
5. `ops_cafe.html` — EventSource 전환
6. QA 서버 배포 → 동작 확인 후 상용 적용
