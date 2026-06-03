"""Cafe tablet + staff API — search, request, queue, playback control.

Tablet clients identify via device_id header (set from localStorage UUID).
Staff endpoints require OPERATOR+ authentication.
WebSocket provides real-time now-playing and request notifications.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .. import db
from .. import security
from ..services.spotify import SpotifyService
from ..services.local_player import LocalPlayer


# ── WebSocket connection registry ─────────────────────────────────

class ConnectionRegistry:
    """In-memory registry of WebSocket connections."""

    def __init__(self) -> None:
        self._tablet: dict[str, WebSocket] = {}   # table_number → ws
        self._staff: set[WebSocket] = set()

    async def connect_tablet(self, table_number: str, ws: WebSocket) -> None:
        await ws.accept()
        self._tablet[table_number] = ws

    async def connect_staff(self, ws: WebSocket) -> None:
        await ws.accept()
        self._staff.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._tablet = {k: v for k, v in self._tablet.items() if v is not ws}
        self._staff.discard(ws)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        msg = json.dumps({"event": event, **payload}, ensure_ascii=False)
        dead: set[WebSocket] = set()
        for ws in self._staff:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        for k, ws in list(self._tablet.items()):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_to_table(self, table_number: str, event: str, payload: dict[str, Any]) -> None:
        ws = self._tablet.get(table_number)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps({"event": event, **payload}, ensure_ascii=False))
        except Exception:
            self.disconnect(ws)

    @property
    def tablet_count(self) -> int:
        return len(self._tablet)

    @property
    def staff_count(self) -> int:
        return len(self._staff)


_registry = ConnectionRegistry()


router = APIRouter(tags=["cafe"])

_spotify = SpotifyService()
_local = LocalPlayer()

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


async def _now_playing_worker() -> None:
    """Single background task — owns all Spotify polling and local state checks.

    Adaptive intervals:
      local playing  → 5s  (VLC socket check, no external API)
      Spotify playing → 30s
      nothing playing → 60s
    """
    prev_state: dict | None = None
    loop = asyncio.get_running_loop()

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


# ── helpers ─────────────────────────────────────────────────────

def _resolve_table(device_id: str | None) -> str | None:
    """Resolve device_id → table_number. Returns None if unknown."""
    if not device_id:
        return None
    dev = db.get_table_by_device(device_id.strip())
    return str(dev["table_number"]).strip() if dev else None


def _device_id_from_request(request: Request) -> str | None:
    return str(request.headers.get("x-device-id") or "").strip() or None


# ── request models ──────────────────────────────────────────────

class CafeTrackRequest(BaseModel):
    track_title: str = Field(min_length=1, max_length=300)
    artist: str = ""
    album_art_url: str | None = None
    source: str = "spotify"  # spotify | local | cd-lp
    spotify_track_id: str | None = None
    owned_item_id: int | None = None


# ── public tags (for tablet browse tab) ────────────────────────────

@router.get("/cafe/tags")
def cafe_tags() -> dict[str, Any]:
    """Public: list all tags for tablet browse tab."""
    rows = db.list_track_tags()
    return {"total_count": len(rows), "items": rows}


# ── public tags (for tablet browse tab) ────────────────────────────

@router.get("/cafe/tags")
def cafe_tags() -> dict[str, Any]:
    """Public: list all tags for tablet browse tab."""
    rows = db.list_track_tags()
    return {"total_count": len(rows), "items": rows}


# ── search ──────────────────────────────────────────────────────

@router.get("/cafe/search")
def cafe_search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
    src: str = Query(default="all"),
) -> dict[str, Any]:
    """Search Spotify + local tags. Public (no auth — tablet access)."""
    results: list[dict[str, Any]] = []

    # Spotify search with retry
    import logging, time
    _log = logging.getLogger(__name__)
    if src in ("spotify", "all"):
        spotify_results = _spotify.search_tracks_sync(q, limit=limit)
        if not spotify_results:
            time.sleep(0.5)
            spotify_results = _spotify.search_tracks_sync(q, limit=limit)
        _log.info(f"cafe search q={q!r} spotify={len(spotify_results)}")
        for item in spotify_results:
            item["source"] = "spotify"
        results.extend(spotify_results)

    # Local file search (skip if NAS slow)
    if src in ("local", "all"):
        local_files = _local.scan_files(q, limit=limit)
        results.extend(local_files)

        # Local tag search (simple text match on tag_value)
        local_tags = db.find_tracks_by_tag(q, limit=limit)
        for tag in local_tags:
            if tag.get("owned_item_id"):
                item_row = db.get_owned_item(tag["owned_item_id"])
                if item_row:
                    results.append({
                        "source": "local",
                        "owned_item_id": tag["owned_item_id"],
                        "title": item_row.get("item_title") or item_row.get("item_name_override") or "",
                        "artist": item_row.get("artist_or_brand") or "",
                        "album_art_url": item_row.get("cover_image_url"),
                        "tag_type": tag.get("tag_type"),
                        "tag_value": tag.get("tag_value"),
                    })

    # Always ensure at least a helpful message
    if not results:
        results = [
            {"source":"info","spotify_track_id":"","title":"검색 결과가 없습니다: "+q,"artist":"다른 검색어나 영문으로 시도해보세요","album_art_url":"","duration_ms":0,"track_uri":""},
        ]
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"query": q, "total_count": len(results), "items": results},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"}
    )


# ── request track ───────────────────────────────────────────────

async def broadcast_queue_update():
    from app import db
    rows = db.list_customer_track_requests(status=None, limit=100)
    await _registry.broadcast("queue_update", {"queue": rows})


@router.post("/cafe/request")
async def cafe_request_track(payload: CafeTrackRequest, request: Request) -> dict[str, Any]:
    """Submit a track request from a tablet."""
    device_id = _device_id_from_request(request)
    table_number = _resolve_table(device_id)
    if not table_number:
        raise HTTPException(status_code=400, detail="등록되지 않은 기기입니다")

    row = db.create_customer_track_request(
        requested_track=f"{payload.artist} - {payload.track_title}" if payload.artist else payload.track_title,
        owned_item_id=payload.owned_item_id,
        matched_track_title=payload.track_title,
        matched_track_no=None,
        customer_note=f"테이블 {table_number} / {payload.source}",
    )
    if not row:
        raise HTTPException(status_code=500, detail="요청 접수 실패")

    await broadcast_queue_update()

    return {
        "ok": True,
        "request_id": row.get("id"),
        "table_number": table_number,
        "track_title": payload.track_title,
    }


# ── queue / now-playing ─────────────────────────────────────────

@router.get("/cafe/queue")
def cafe_queue(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    """Public: list pending/playing requests."""
    rows = db.list_customer_track_requests(status=None, limit=limit)
    return {"total_count": len(rows), "items": rows}


@router.get("/cafe/now-playing")
def cafe_now_playing() -> dict[str, Any]:
    """Public: current playback info — served from worker-managed state."""
    if _now_playing_state is not None:
        return _now_playing_state
    return {"available": False}


# ── local playback ────────────────────────────────────────────────

@router.post("/ops/cafe/play-local")
async def staff_play_local(request: Request) -> dict[str, Any]:
    """Staff: play a local file. OPERATOR+"""
    import json as _json
    security._require_operator_request(request)
    body = _json.loads(await request.body())
    file_path = str(body.get("file_path") or "").strip()
    request_id = int(body.get("request_id") or 0)

    # If request_id given, look up the track from the request
    if request_id and not file_path:
        req_row = db.get_customer_track_request(request_id)
        if req_row:
            # Search local files by track name
            query = str(req_row.get("requested_track") or "").strip()
            if " - " in query:
                query = query.split(" - ", 1)[1]
            local_files = _local.scan_files(query, limit=1)
            if local_files:
                file_path = local_files[0]["file_path"]
            # Mark as playing
            db.update_customer_track_request(request_id, status="PLAYING")

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required")
    ok = _local.play(file_path)
    return {"ok": ok, "file_path": file_path}


@router.post("/ops/cafe/pause-local")
def staff_pause_local(request: Request) -> dict[str, Any]:
    """Staff: pause/resume local playback. OPERATOR+"""
    security._require_operator_request(request)
    ok = _local.pause()
    return {"ok": ok}

@router.post("/ops/cafe/stop-local")
def staff_stop_local(request: Request) -> dict[str, Any]:
    """Staff: stop local playback. OPERATOR+"""
    security._require_operator_request(request)
    _local.stop()
    return {"ok": True}


# ── staff: queue management ─────────────────────────────────────

@router.get("/ops/cafe/queue")
def staff_queue(request: Request) -> dict[str, Any]:
    """Staff: full request queue (all statuses). OPERATOR+"""
    security._require_operator_request(request)
    rows = db.list_customer_track_requests(status=None, limit=100)
    return {"total_count": len(rows), "items": rows}


@router.post("/ops/cafe/play/{request_id}")
async def staff_play(request_id: int, request: Request) -> dict[str, Any]:
    """Staff: mark request as PLAYING, trigger playback if possible. OPERATOR+"""
    security._require_operator_request(request)
    row = db.update_customer_track_request(request_id, status="PLAYING")
    if not row:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    await broadcast_queue_update()

    # Broadcast now_playing info to tablets
    title = row.get("live_item_title") or row.get("item_title_snapshot") or row.get("requested_track") or ""
    artist = row.get("live_artist_or_brand") or row.get("artist_or_brand_snapshot") or ""
    art_url = row.get("live_cover_image_url") or row.get("cover_image_url_snapshot") or ""
    
    # Extract table number from customer_note (e.g. "테이블 3 / spotify")
    table_number = ""
    note = row.get("customer_note") or ""
    if "테이블 " in note:
        try:
            table_number = note.split("테이블 ")[-1].split(" /")[0].strip()
        except Exception:
            pass

    await _registry.broadcast("now_playing", {
        "track_title": title,
        "artist": artist,
        "album_art_url": art_url,
        "request_id": request_id,
        "table_number": table_number,
        "source": note.split("/ ")[-1].strip() if "/" in note else "spotify"
    })

    return {"ok": True, "request_id": request_id, "status": "PLAYING"}


@router.post("/ops/cafe/complete/{request_id}")
async def staff_complete(request_id: int, request: Request) -> dict[str, Any]:
    """Staff: mark request as RETURNED. OPERATOR+"""
    security._require_operator_request(request)
    row = db.update_customer_track_request(request_id, status="RETURNED")
    if not row:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    await broadcast_queue_update()
    return {"ok": True, "request_id": request_id, "status": "RETURNED"}


@router.post("/ops/cafe/cancel/{request_id}")
async def staff_cancel(request_id: int, request: Request) -> dict[str, Any]:
    """Staff: mark request as CANCELLED. OPERATOR+"""
    security._require_operator_request(request)
    row = db.update_customer_track_request(request_id, status="CANCELLED")
    if not row:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    await broadcast_queue_update()
    return {"ok": True, "request_id": request_id, "status": "CANCELLED"}


@router.post("/ops/cafe/restore/{request_id}")
@router.patch("/ops/cafe/restore/{request_id}")
@router.post("/operator/customer-requests/{request_id}/restore")
@router.patch("/operator/customer-requests/{request_id}/restore")
async def staff_restore(request_id: int, request: Request) -> dict[str, Any]:
    """Staff: restore/rollback a completed/cancelled request. OPERATOR+"""
    security._require_operator_request(request)
    row = db.rollback_customer_track_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    await broadcast_queue_update()
    return {"ok": True, "request_id": request_id, "status": "REQUESTED"}


@router.post("/ops/cafe/pause")
def staff_pause(request: Request) -> dict[str, Any]:
    """Staff: pause Spotify playback. OPERATOR+"""
    security._require_operator_request(request)
    ok = _spotify.pause_sync()
    return {"ok": ok}


@router.post("/ops/cafe/skip")
def staff_skip(request: Request) -> dict[str, Any]:
    """Staff: skip — just pause for now (Spotify free-tier limitation)."""
    security._require_operator_request(request)
    _spotify.pause_sync()
    return {"ok": True, "note": "paused — select next track manually"}


# ── WebSocket ─────────────────────────────────────────────────────

@router.websocket("/ws/cafe")
async def cafe_websocket(ws: WebSocket):
    """WebSocket for real-time cafe events."""
    role = ws.query_params.get("role", "")
    device_id = ws.query_params.get("device_id", "")

    if role == "staff":
        await _registry.connect_staff(ws)
        try:
            while True:
                data = await ws.receive_json()
                event = data.get("event", "")
                if event == "now_playing":
                    await _registry.broadcast("now_playing", data.get("payload", {}))
                elif event == "track_played":
                    tbl = data.get("table_number", "")
                    await _registry.send_to_table(tbl, "track_played", data.get("payload", {}))
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            _registry.disconnect(ws)

    elif role == "tablet":
        table_number = _resolve_table(device_id)
        if not table_number:
            await ws.close(code=4000)
            return
        await _registry.connect_tablet(table_number, ws)
        try:
            while True:
                data = await ws.receive_json()
                event = data.get("event", "")
                if event == "track_request":
                    await _registry.broadcast("track_request", {
                        "table_number": table_number,
                        **data.get("payload", {}),
                    })
                elif event == "reaction":
                    await _registry.broadcast("reaction", {
                        "table_number": table_number,
                        **data.get("payload", {}),
                    })
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            _registry.disconnect(ws)

    else:
        await ws.close(code=4000)


# ── Spotify OAuth callback ────────────────────────────────────────

@router.get("/spotify/callback")
def spotify_callback(request: Request):
    """Handle Spotify OAuth redirect after user authorization."""
    code = request.query_params.get("code")
    if not code:
        return {"error": "no authorization code received"}
    try:
        sp = _spotify._ensure_client()
        if sp is None:
            return {"error": "spotify not configured"}
        token_info = sp.auth_manager.get_access_token(code, check_cache=False)
        return {"ok": True, "message": "Spotify OAuth complete! You can close this page."}
    except Exception as e:
        return {"error": str(e)}


# ── lyrics ────────────────────────────────────────────────────────

@router.get("/cafe/lyrics")
def cafe_lyrics(
    artist: str = Query(default=""),
    title: str = Query(default=""),
    file_path: str = Query(default=""),
) -> dict[str, Any]:
    """Public: get lyrics for current track (Spotify via lyrics.ovh, local via ID3)."""
    artist = artist.strip()
    title = title.strip()
    fp = file_path.strip()

    # Try Spotify track via lyrics.ovh
    if artist and title:
        try:
            import urllib.request, json
            url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"
            req = urllib.request.Request(url, headers={"User-Agent": "muzlife-cafe/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                lyr = str(data.get("lyrics") or "").strip()
                if lyr:
                    return {"available": True, "lyrics": lyr, "source": "lyrics.ovh"}
        except Exception:
            pass

    # Try local file ID3 lyrics
    if fp:
        lyr = _local.get_lyrics(fp)
        if lyr:
            return {"available": True, "lyrics": lyr, "source": "local"}

    return {"available": False}


# ── reactions ─────────────────────────────────────────────────────

@router.post("/cafe/reaction")
async def cafe_reaction(request: Request) -> dict[str, Any]:
    """Submit a reaction from tablet."""
    import json as _json
    body = _json.loads(await request.body())
    device_id = _device_id_from_request(request)
    table_number = _resolve_table(device_id)
    if not table_number:
        raise HTTPException(status_code=400, detail="등록되지 않은 기기입니다")
    track_request_id = int(body.get("track_request_id") or 0)
    reaction_type = str(body.get("reaction_type") or "").strip().upper()
    free_text = str(body.get("free_text") or "").strip() or None
    if not track_request_id or not reaction_type:
        raise HTTPException(status_code=400, detail="track_request_id and reaction_type required")
    db.insert_track_reaction(track_request_id, table_number, reaction_type, free_text)

    await _registry.broadcast("reaction", {
        "track_request_id": track_request_id,
        "table_number": table_number,
        "reaction_type": reaction_type,
        "free_text": free_text,
    })
    return {"ok": True}


# ── playlists ─────────────────────────────────────────────────────

@router.get("/ops/cafe/playlists")
def staff_playlists(request: Request) -> dict[str, Any]:
    """Staff: list all saved playlists. OPERATOR+"""
    security._require_operator_request(request)
    rows = db.list_playlists()
    for r in rows:
        r["item_count"] = len(db.get_playlist_items(r["id"]))
    return {"items": rows}

@router.post("/ops/cafe/playlists")
async def staff_create_playlist(request: Request) -> dict[str, Any]:
    """Staff: create a new playlist. OPERATOR+"""
    security._require_operator_request(request)
    import json as _json
    body = _json.loads(await request.body())
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    pl = db.create_playlist(name)
    if not pl:
        raise HTTPException(status_code=500, detail="create failed")
    return pl

@router.get("/ops/cafe/playlists/{playlist_id}")
def staff_playlist_detail(playlist_id: int, request: Request) -> dict[str, Any]:
    """Staff: get playlist with items. OPERATOR+"""
    security._require_operator_request(request)
    pl = db.get_playlist(playlist_id)
    if not pl:
        raise HTTPException(status_code=404, detail="not found")
    pl["items"] = db.get_playlist_items(playlist_id)
    return pl

@router.post("/ops/cafe/playlists/{playlist_id}/items")
async def staff_add_playlist_item(playlist_id: int, request: Request) -> dict[str, Any]:
    """Staff: add track to playlist. OPERATOR+"""
    security._require_operator_request(request)
    import json as _json
    body = _json.loads(await request.body())
    item_id = db.add_playlist_item(
        playlist_id=playlist_id,
        title=str(body.get("title") or ""),
        artist=str(body.get("artist") or ""),
        spotify_track_id=body.get("spotify_track_id"),
        spotify_track_uri=body.get("spotify_track_uri"),
        local_file_path=body.get("local_file_path"),
        album_art_url=body.get("album_art_url"),
    )
    return {"ok": True, "id": item_id}

@router.delete("/ops/cafe/playlists/{playlist_id}/items/{item_id}")
def staff_remove_playlist_item(playlist_id: int, item_id: int, request: Request) -> dict[str, Any]:
    """Staff: remove track from playlist. OPERATOR+"""
    security._require_operator_request(request)
    db.remove_playlist_item(item_id)
    return {"ok": True}

@router.delete("/ops/cafe/playlists/{playlist_id}")
def staff_delete_playlist(playlist_id: int, request: Request) -> dict[str, Any]:
    """Staff: delete playlist. OPERATOR+"""
    security._require_operator_request(request)
    db.delete_playlist(playlist_id)
    return {"ok": True}

@router.post("/ops/cafe/playlists/{playlist_id}/play-next")
async def staff_playlist_play_next(playlist_id: int, request: Request) -> dict[str, Any]:
    """Staff: play next track from playlist. OPERATOR+"""
    security._require_operator_request(request)
    import json as _json
    body = _json.loads(await request.body())
    current_idx = int(body.get("current_index", -1))
    item = db.get_next_playlist_item(playlist_id, current_idx)
    if not item:
        return {"ok": False, "reason": "no more tracks"}
    if item.get("spotify_track_uri"):
        _spotify.play_sync(item["spotify_track_uri"])
    elif item.get("local_file_path"):
        _local.play(item["local_file_path"])
    return {"ok": True, "item": item}


# ── tablet shell page ───────────────────────────────────────────

@router.get("/cafe/tablet", include_in_schema=False)
def cafe_tablet_shell(request: Request):
    from pathlib import Path
    from fastapi.responses import FileResponse
    def _main():
        from app import main as main_module
        return main_module
    STATIC_DIR = _main().STATIC_DIR
    page_path = STATIC_DIR / "cafe_tablet.html"
    return FileResponse(
        page_path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )
