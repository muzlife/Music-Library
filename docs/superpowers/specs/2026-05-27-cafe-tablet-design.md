# Cafe Tablet System — Design Spec

> Written: 2026-05-27 | Status: Approved

## 1. Purpose

카페 테이블에 비치된 태블릿을 통해 고객이 직접 음악을 검색·신청하고, 현재 재생 중인 곡을 실시간 확인할 수 있는 시스템.
직원은 요청 접수부터 재생까지 운영할 수 있는 통합 화면을 제공받는다.

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                  Mac mini M4                     │
│                                                  │
│  ┌──────────────┐  ┌──────────────────┐         │
│  │ FastAPI       │  │ Spotify Connect   │         │
│  │ • cafe API    │  │ (spotipy SDK)    │         │
│  │ • WebSocket   │  └──────────────────┘         │
│  │ • Spotify 검색│                              │
│  └──────┬───────┘                               │
│         │                                        │
│  ┌──────▼───────┐                               │
│  │  SQLite DB    │                               │
│  │  + track_tag  │                               │
│  │  + customer_  │                               │
│  │    track_req  │                               │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
         │                    │
    HTTP/WS              Spotify API
         │                    │
  ┌──────▼──────┐    ┌───────▼──────┐
  │ 태블릿 #1~N  │    │  Spotify      │
  │ (고객용 웹)  │    │  (음원 재생)   │
  └──────────────┘    └──────────────┘
```

**음원 소스:**
- Spotify Premium 계정 1개로 Spotify Connect 제어 (무료 Web API + 유료 Premium)
- 로컬 저장 음원 (기존 owned_item 기반)
- 필요시 CD/LP (수동 재생, 태블릿에는 소스 구분 없이 표시)

## 3. Data Model

### 3.1 New: track_tag table

```sql
CREATE TABLE track_tag (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag_type TEXT NOT NULL,       -- 'MOOD', 'GENRE', 'ERA', 'CUSTOM'
  tag_value TEXT NOT NULL,      -- '재즈', '비오는 날', '90년대'
  owned_item_id INTEGER,        -- NULL if spotify track
  spotify_track_id TEXT,        -- NULL if local track
  created_by TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
);
CREATE INDEX idx_track_tag_type_value ON track_tag (tag_type, tag_value);
CREATE INDEX idx_track_tag_owned ON track_tag (owned_item_id);
CREATE INDEX idx_track_tag_spotify ON track_tag (spotify_track_id);
```

### 3.2 Existing: customer_track_request (unchanged)

Already has: weather data, season, status flow (REQUESTED→PLAYING→RETURNED/CANCELLED), timestamps, playback_deck.

### 3.3 New: table_device registry

```sql
CREATE TABLE table_device (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_number TEXT NOT NULL UNIQUE,   -- '1', '2', '테라스'
  device_label TEXT,                   -- '삼성 태블릿 A8'
  device_id TEXT UNIQUE,               -- client-generated UUID, mapped by admin
  is_active INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 3.4 New: track_reaction

```sql
CREATE TABLE track_reaction (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track_request_id INTEGER NOT NULL,
  table_number TEXT NOT NULL,
  reaction_type TEXT NOT NULL,  -- 'LOVE', 'VIBE', 'SIMILAR', 'WEATHER', 'CUSTOM'
  free_text TEXT,               -- only when reaction_type='CUSTOM', max 50 chars
  created_at TEXT NOT NULL,
  FOREIGN KEY (track_request_id) REFERENCES customer_track_request(id) ON DELETE CASCADE
);
```

## 4. Customer Tablet UI

### 4.1 Layout

Three tabs + persistent bottom bar:

```
┌──────────────────────────────┐
│  [🔍 검색] [🏷️ 둘러보기] [▶️ 지금]  │
├──────────────────────────────┤
│                              │
│   Main content area          │
│                              │
├──────────────────────────────┤
│  ┌────┐                      │
│  │ 🎵 │ "가을이 오면"          │  ← Bottom bar (always visible)
│  └────┘ 이문세 ───○─── 2:34   │
└──────────────────────────────┘
```

### 4.2 Tab 1: Search (검색)

- Free text input with Spotify API autocomplete
- Results: album art thumbnail + track title + artist + "신청하기" button
- Each result shows tag chips if available

### 4.3 Tab 2: Browse (둘러보기)

- Tag chip cloud: 🎷재즈 ☕감성적인 🌧️비오는날 📻90년대 🕺신나는 🌙잔잔한
- Tapping a tag shows tracks with that tag (from local + Spotify recommendations)
- "Similar to now playing" button uses Spotify Recommendations API

### 4.4 Tab 3: Now (지금)

- Request queue: shows all pending/playing requests with status
- "My table's requests" highlighted
- Play history (recently played)

### 4.5 Playback Overlay

When a track requested by THIS table starts playing:

```
┌──────────────────────────────┐
│        ✨ 지금 재생 중! ✨       │
│     ┌──────────────┐         │
│     │  Album Art   │         │
│     └──────────────┘         │
│   "가을이 오면" - 이문세        │
│   테이블 3에서 신청하신          │
│   곡이 재생됩니다 🎵            │
│                              │
│   ┌──────────────────┐       │
│   │ 💕 완전 좋아요      │       │
│   │ ☕ 분위기 딱이에요   │       │
│   │ 🎵 비슷한 곡 더     │       │
│   │ 🌧️ 날씨랑 찰떡      │       │
│   │ ✍️ 직접 쓰기       │       │
│   └──────────────────┘       │
└──────────────────────────────┘
```

- 5-second full overlay → auto-collapse to bottom bar
- Reaction cards appear during playback only
- "직접 쓰기" limited to 50 chars, basic profanity filter

### 4.6 Device Identification

- Each tablet generates a UUID on first visit, stored in localStorage
- Tablet page accessed at `/cafe/tablet` (device self-identifies via localStorage UUID)
- Admin maps device_id → table_number via management UI (table_device table)

## 5. Staff Operations UI (/ops/cafe)

### 5.1 Request Board

Three-column kanban: [대기] [처리중] [완료]

Each request card shows:
- Track title + artist
- Album art thumbnail
- Table number
- Request timestamp
- [재생] [보류] [완료] action buttons

### 5.2 Playback Control

- Current track display with progress
- Play/Pause/Skip controls
- Source selector: Spotify / Local / CD-LP (manual)
- Volume control

### 5.3 Real-time Feed

- Incoming requests animate in (WebSocket push)
- Reaction feed: "테이블3 💕완전 좋아요" in real-time
- Sound notification for new requests (optional)

## 6. WebSocket Protocol

### 6.1 Connection

```
ws://host/ws/cafe?role=tablet&device_id=<uuid>
ws://host/ws/cafe?role=staff&token=<session_token>
```

### 6.2 Events

| Event | Direction | Payload |
|-------|-----------|---------|
| `track_request` | tablet→server | {track_title, artist, album_art_url, source, track_id} |
| `now_playing` | server→all | {track_title, artist, album_art_url, position_ms, duration_ms} |
| `track_played` | server→target_tablet | {track_title, artist, table_number, request_id} |
| `reaction` | tablet→server | {track_request_id, reaction_type, free_text?} |
| `queue_update` | server→staff | {queue: [...]} |
| `reaction_feed` | server→staff | {table_number, reaction_type, track_title} |

### 6.3 Implementation

- In-memory connection registry (`dict[table_number → WebSocket]` + `set[staff_WebSocket]`); device_id→table_number resolved via DB on connect
- No Redis needed (single process)
- Reconnection with exponential backoff on client side

## 7. Spotify Integration

### 7.1 Service Module

```python
# app/services/spotify.py
class SpotifyService:
    async def search_tracks(query: str, limit: int = 10) -> list[TrackResult]
    async def get_recommendations(seed_track_id: str, limit: int = 10) -> list[TrackResult]
    async def play(track_uri: str) -> None
    async def pause() -> None
    async def current_playback() -> NowPlaying | None
```

### 7.2 Auth

- spotipy SDK with OAuth authorization code flow
- Token cached in config, auto-refreshed
- One-time setup: admin opens Spotify auth URL, pastes redirect code

### 7.3 Rate Limits

- Search API: ~180 requests/min (free tier, sufficient for cafe use)
- Recommendations API: ~30 requests/min

## 8. Implementation Phases

| Phase | Scope | Estimate |
|-------|-------|----------|
| **1** | Spotify service + track_tag table + tag admin API | Foundation |
| **2** | `/cafe/tablet` UI (search, browse, request) | Tablet UI |
| **3** | WebSocket server + now-playing broadcast | Real-time |
| **4** | `/ops/cafe` staff board + playback control | Staff ops |
| **5** | Reaction cards + overlay + analytics dashboard | Polish |

## 9. Non-Goals (for this phase)

- Roon integration (retired — unstable)
- Table ordering/food menu integration
- Multi-location support (single cafe first)
- AI auto-tagging (manual tags first)
- Offline/PWA support (browser-based first)
- Album check-out/in tracking (operational complexity TBD)

## 10. Success Criteria

1. Customer can search and request tracks from tablet in under 30 seconds
2. Staff sees new request on board within 1 second (WebSocket)
3. Now-playing updates on all tablets within 1 second
4. Search covers Spotify catalog + locally tagged items
5. Tag-based browsing works with at least 20 initial tags
