# Cafe Tablet System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cafe tablet system where customers search/request tracks from tablets and staff manage playback via a real-time ops board, backed by Spotify + local library.

**Architecture:** Single FastAPI app with WebSocket for real-time events. Customer tablets serve a static HTML page (`cafe_tablet.html`) communicating via REST + WS. Staff uses `/ops/cafe` with a kanban-style request board and playback controls. Spotify integration via spotipy SDK. New tables: `track_tag`, `table_device`, `track_reaction`.

**Tech Stack:** FastAPI, SQLite, vanilla JS (tablet UI), spotipy (Spotify SDK), WebSocket (fastapi.WebSocket)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app/services/spotify.py` | Spotify API wrapper (search, play, current playback) |
| `app/db/track_tag.py` | track_tag table CRUD + ensure-table |
| `app/db/table_device.py` | table_device table CRUD + ensure-table |
| `app/db/track_reaction.py` | track_reaction table + insert |
| `app/db/__init__.py` | Register new tables in init_db, re-export new modules |
| `app/config.py` | Add Spotify OAuth config fields |
| `app/api/cafe_admin.py` | Tag admin API (CRUD for track_tag, table_device management) |
| `app/api/cafe.py` | Tablet API (search, request, WS) + staff API (queue, playback) |
| `app/static/cafe_tablet.html` | Customer tablet UI (search/browse/now-playing) |
| `app/static/ops_cafe.html` | Staff operations board (kanban, playback control) |
| `app/main.py` | Register new routers |

---

## Phase 1: Foundation — Spotify + Tags + Tables

### Task 1.1: Spotify config + service module

**Files:** Modify `app/config.py`, Create `app/services/spotify.py`, Create `tests/test_spotify_service.py`

- [ ] **Step 1:** Add Spotify env vars to `app/config.py` Settings class
```python
spotify_client_id: str = ""
spotify_client_secret: str = ""
spotify_redirect_uri: str = "http://localhost:8100/spotify/callback"
```
- [ ] **Step 2:** Create `app/services/spotify.py` with `SpotifyService` class
  - `configured` property (bool)
  - `_ensure_client()` — lazy spotipy init with OAuth
  - `search_tracks_sync(query, limit=10)` — returns list of {spotify_track_id, title, artist, album_name, album_art_url, duration_ms, track_uri}
  - `play_sync(track_uri)` — Spotify Connect playback
  - `pause_sync()` — pause
  - `current_playback_sync()` — returns dict or None
- [ ] **Step 3:** Create `tests/test_spotify_service.py`
  - `test_spotify_service_not_configured_returns_empty` — patch env to empty, verify search returns []
  - `test_spotify_service_configured_initializes` — patch env with test values, verify configured=True
- [ ] **Step 4:** Run `pytest tests/test_spotify_service.py -v` → PASS
- [ ] **Step 5:** Commit
```bash
git add app/config.py app/services/spotify.py tests/test_spotify_service.py
git commit -m "feat(cafe): add SpotifyService with config, search, and playback stubs"
```

---

### Task 1.2: track_tag DB module

**Files:** Create `app/db/track_tag.py`, Modify `app/db/__init__.py`, Create `tests/test_track_tag.py`

- [ ] **Step 1:** Create `app/db/track_tag.py`
  - `_ensure_track_tag_table(conn)` — CREATE TABLE IF NOT EXISTS with indexes
  - `insert_track_tag(*, tag_type, tag_value, owned_item_id=None, spotify_track_id=None, created_by=None) -> int`
  - `list_track_tags(tag_type=None) -> list[dict]`
  - `find_tracks_by_tag(tag_value, limit=20) -> list[dict]`
  - `delete_track_tag(tag_id) -> bool`
- [ ] **Step 2:** Register in `app/db/__init__.py`
  - In `init_db()`: call `_ensure_track_tag_table(conn)`
  - Add re-export block: `from .track_tag import (...all functions...)`
- [ ] **Step 3:** Create `tests/test_track_tag.py`
  - `test_track_tag_insert_and_list` — insert a tag, list by type, verify
  - `test_track_tag_delete` — insert then delete, verify gone
- [ ] **Step 4:** Run `pytest tests/test_track_tag.py -v` → PASS
- [ ] **Step 5:** Commit
```bash
git add app/db/track_tag.py app/db/__init__.py tests/test_track_tag.py
git commit -m "feat(cafe): add track_tag table with CRUD for mood/genre/era tags"
```

---

### Task 1.3: table_device + track_reaction DB modules

**Files:** Create `app/db/table_device.py`, Create `app/db/track_reaction.py`, Modify `app/db/__init__.py`

- [ ] **Step 1:** Create `app/db/table_device.py`
  - `_ensure_table_device_table(conn)`
  - `register_table_device(table_number, device_id, device_label="") -> dict`
  - `get_table_by_device(device_id) -> dict | None`
  - `list_table_devices() -> list[dict]`
  - `deactivate_table_device(device_id) -> bool`
- [ ] **Step 2:** Create `app/db/track_reaction.py`
  - `_ensure_track_reaction_table(conn)`
  - `insert_track_reaction(track_request_id, table_number, reaction_type, free_text=None) -> int`
  - `list_reactions_by_request(track_request_id) -> list[dict]`
- [ ] **Step 3:** Register both in `app/db/__init__.py`
  - In `init_db()`: call `_ensure_table_device_table(conn)` and `_ensure_track_reaction_table(conn)`
  - Add re-export blocks for both modules
- [ ] **Step 4:** Commit (no separate tests — covered by integration tests in Phase 2+)
```bash
git add app/db/table_device.py app/db/track_reaction.py app/db/__init__.py
git commit -m "feat(cafe): add table_device and track_reaction DB modules"
```

---

### Task 1.4: Tag admin API + table device management

**Files:** Create `app/api/cafe_admin.py`, Modify `app/main.py`

- [ ] **Step 1:** Create `app/api/cafe_admin.py`
  - `GET /admin/cafe/tags` — list all tags (ADMIN+OPERATOR)
  - `POST /admin/cafe/tags` — create tag (ADMIN+OPERATOR)
  - `DELETE /admin/cafe/tags/{tag_id}` — delete tag (ADMIN+OPERATOR)
  - `GET /admin/cafe/tables` — list table devices (ADMIN+OPERATOR)
  - `POST /admin/cafe/tables` — register table device (ADMIN)
  - `DELETE /admin/cafe/tables/{device_id}` — deactivate (ADMIN)
- [ ] **Step 2:** Register router in `app/main.py`
```python
from app.api.cafe_admin import router as cafe_admin_router
app.include_router(cafe_admin_router)
```
- [ ] **Step 3:** Commit
```bash
git add app/api/cafe_admin.py app/main.py
git commit -m "feat(cafe): add tag admin API and table device management endpoints"
```

---

## Phase 2: Customer Tablet UI

### Task 2.1: Cafe REST API (search, request)

**Files:** Create `app/api/cafe.py`, Modify `app/main.py`

- [ ] **Step 1:** Create `app/api/cafe.py` with router
  - `GET /cafe/search?q=...&limit=10` — search Spotify + local tags, merge results (VIEWER+, no auth for tablet — use device_id header)
  - `POST /cafe/request` — create customer_track_request from tablet (device_id header → table_number lookup)
  - `GET /cafe/queue` — list pending/playing requests (for tablet "now" tab)
  - `GET /cafe/now-playing` — current playback info
- [ ] **Step 2:** Register in `app/main.py`
```python
from app.api.cafe import router as cafe_router
app.include_router(cafe_router)
```
- [ ] **Step 3:** Update allowed_paths in middleware to allow `/cafe/search`, `/cafe/now-playing` for unauthenticated tablet access
- [ ] **Step 4:** Commit
```bash
git add app/api/cafe.py app/main.py
git commit -m "feat(cafe): add REST API for tablet search, request, queue"
```

---

### Task 2.2: Customer tablet HTML page

**Files:** Create `app/static/cafe_tablet.html`

- [ ] **Step 1:** Create full tablet UI page with:
  - **Top nav:** 3 tabs (검색, 둘러보기, 지금)
  - **검색 tab:** text input + debounced Spotify search + results list with album art + "신청하기" button
  - **둘러보기 tab:** tag chip cloud (fetch from /admin/cafe/tags) → tap to see tracks
  - **지금 tab:** queue list + "내 테이블 신청곡" highlight + now playing
  - **Bottom bar:** always-visible now-playing with cover art + progress
  - **Device ID:** generate UUID on first visit, store in localStorage
  - **All styling:** dark theme matching existing ops theme
- [ ] **Step 2:** Add shell route in `app/api/cafe.py`:
```python
@router.get("/cafe/tablet", include_in_schema=False)
def cafe_tablet_shell(request: Request):
    # serve static/cafe_tablet.html with cache-busting
```
- [ ] **Step 3:** Commit
```bash
git add app/static/cafe_tablet.html app/api/cafe.py
git commit -m "feat(cafe): add customer tablet UI page with search, browse, request"
```

---

## Phase 3: Real-Time WebSocket

### Task 3.1: WebSocket endpoint + connection registry

**Files:** Modify `app/api/cafe.py`

- [ ] **Step 1:** Add WebSocket endpoint to `app/api/cafe.py`
  - `@router.websocket("/ws/cafe")` 
  - Parse `role` and `device_id` from query params
  - On connect: register in ConnectionRegistry
  - On disconnect: unregister
  - Handle `track_request` message from tablet → broadcast to staff
  - Handle `now_playing` message from staff → broadcast to all
  - Handle `track_played` message from staff → send overlay trigger to target tablet
- [ ] **Step 2:** Implement `ConnectionRegistry` class
  - `dict[table_number, WebSocket]` for tablets
  - `set[WebSocket]` for staff clients
  - `broadcast(event_type, payload)` → send to all
  - `send_to_table(table_number, event_type, payload)` → single tablet
  - Methods are async, handle disconnects gracefully
- [ ] **Step 3:** Commit
```bash
git add app/api/cafe.py
git commit -m "feat(cafe): add WebSocket endpoint with connection registry for real-time events"
```

---

### Task 3.2: WebSocket client integration in tablet UI

**Files:** Modify `app/static/cafe_tablet.html`

- [ ] **Step 1:** Add WebSocket client to tablet HTML
  - Connect on page load: `ws://host/ws/cafe?role=tablet&device_id=<uuid>`
  - Listen for `now_playing` → update bottom bar
  - Listen for `track_played` with this table's number → show overlay
  - Send `track_request` on "신청하기" click
  - Reconnect with exponential backoff on disconnect
- [ ] **Step 2:** Commit
```bash
git add app/static/cafe_tablet.html
git commit -m "feat(cafe): integrate WebSocket client in tablet UI for real-time updates"
```

---

## Phase 4: Staff Operations Board

### Task 4.1: Staff ops HTML page + playback API

**Files:** Create `app/static/ops_cafe.html`, Modify `app/api/cafe.py`

- [ ] **Step 1:** Add staff API endpoints to `app/api/cafe.py`
  - `GET /ops/cafe/queue` — full request queue (all statuses)
  - `POST /ops/cafe/play/{request_id}` — mark REQUESTED→PLAYING, play via Spotify/local (OPERATOR+)
  - `POST /ops/cafe/complete/{request_id}` — mark PLAYING→RETURNED (OPERATOR+)
  - `POST /ops/cafe/pause` — pause playback (OPERATOR+)
  - `POST /ops/cafe/skip` — skip to next in queue (OPERATOR+)
- [ ] **Step 2:** Create `app/static/ops_cafe.html` with:
  - **Three-column kanban:** [대기] [처리중] [완료]
  - Each card: album art, track title, artist, table number, timestamp
  - Action buttons: [재생] [보류] button per card
  - **Playback bar:** current track + play/pause/skip + progress + source indicator
  - **Reaction feed:** real-time reaction notifications from tablets
  - WebSocket connection for real-time updates
- [ ] **Step 3:** Verify existing `/ops/cafe` shell route serves this page
- [ ] **Step 4:** Commit
```bash
git add app/static/ops_cafe.html app/api/cafe.py
git commit -m "feat(cafe): add staff operations board with kanban and playback control"
```

---

## Phase 5: Reactions + Polish

### Task 5.1: Reaction cards in tablet UI

**Files:** Modify `app/static/cafe_tablet.html`, Modify `app/api/cafe.py`

- [ ] **Step 1:** Add `POST /cafe/reaction` endpoint
  - Accept {track_request_id, reaction_type, free_text?}
  - Look up table_number from device_id header
  - Insert into track_reaction table
  - Broadcast `reaction_feed` to staff WebSocket
- [ ] **Step 2:** Add reaction overlay to tablet HTML
  - Show after `track_played` event received
  - 5 reaction card buttons in a grid (💕, ☕, 🎵, 🌧️, ✍️)
  - "직접 쓰기" opens a small text input, max 50 chars, basic profanity filter (regex for Korean/English curse words)
  - Auto-dismiss after 30 seconds or on tap-outside
  - Send reaction via WebSocket, show brief confirmation
- [ ] **Step 3:** Commit
```bash
git add app/static/cafe_tablet.html app/api/cafe.py
git commit -m "feat(cafe): add reaction cards with emoji presets and free text"
```

---

### Task 5.2: End-to-end smoke test + deploy

**Files:** Create `tests/test_cafe_e2e.py`

- [ ] **Step 1:** Write integration test
  - `test_tablet_search_returns_results` — search for known track
  - `test_tablet_request_creates_customer_track_request`
  - `test_websocket_connect_and_disconnect`
  - `test_tag_crud_via_api`
- [ ] **Step 2:** Run full suite `pytest tests/ -q` → verify no new failures
- [ ] **Step 3:** Deploy to QA and Prod
```bash
rsync -av --delete ... ~/apps/__PROJECT_SLUG__-qa/
rsync -av --delete ... ~/apps/__PROJECT_SLUG__-prod/
launchctl stop com.muzlife.library-qa; launchctl start com.muzlife.library-qa
launchctl stop com.muzlife.library-prod; launchctl start com.muzlife.library-prod
```
- [ ] **Step 4:** Verify in browser: `/cafe/tablet` and `/ops/cafe`
- [ ] **Step 5:** Final commit
```bash
git add tests/test_cafe_e2e.py
git commit -m "test(cafe): add end-to-end smoke tests for cafe tablet system"
```

---

## Summary

Total: 5 phases, 11 tasks. Each task is a self-contained commit.
