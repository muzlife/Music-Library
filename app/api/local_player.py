"""로컬 NAS 음악 스트리밍 + album_master 로컬 연결 API."""
from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..db.album_master_local_link import (
    MUSIC_ROOT,
    AUDIO_EXTS,
    auto_match,
    delete_local_link,
    find_cover_path,
    get_local_link,
    list_tracks_for_link,
    list_tracks_in_dir,
    parse_dir_name,
    set_local_link,
)

router = APIRouter()

_SAFE_ROOT = str(Path(MUSIC_ROOT).resolve())


def _encode_path(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode()).decode()


def _decode_and_validate(p: str) -> str:
    try:
        path = base64.urlsafe_b64decode(p.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid path encoding")
    resolved = str(Path(path).resolve())
    if not resolved.startswith(_SAFE_ROOT + os.sep) and resolved != _SAFE_ROOT:
        raise HTTPException(status_code=403, detail="path outside music root")
    return resolved


def _track_to_json(track: dict[str, Any]) -> dict[str, Any]:
    fp = track["file_path"]
    return {
        "file_path": fp,
        "title": track.get("title") or Path(fp).stem,
        "track_number": track.get("track_number"),
        "duration_seconds": track.get("duration_seconds"),
        "stream_url": f"/local-music/stream?p={_encode_path(fp)}",
        "ext": Path(fp).suffix.lower().lstrip("."),
    }


# ── Player info ──────────────────────────────────────────────────────────────

@router.get("/album-masters/{master_id}/local-player")
def get_local_player(master_id: int, request: Request) -> dict[str, Any]:
    from ..security import _require_operator_request
    _require_operator_request(request)

    link = get_local_link(master_id)
    if not link:
        return {"linked": False, "dir_path": None, "tracks": [], "cover_url": None}

    dir_path = link["local_dir_path"]
    tracks = list_tracks_for_link(master_id)
    cover = find_cover_path(dir_path)

    return {
        "linked": True,
        "dir_path": dir_path,
        "match_confidence": link.get("match_confidence"),
        "tracks": [_track_to_json(t) for t in tracks],
        "cover_url": f"/local-music/cover?p={_encode_path(dir_path)}" if cover else None,
    }


# ── Streaming ────────────────────────────────────────────────────────────────

@router.get("/local-music/stream")
def stream_track(p: str, request: Request) -> FileResponse:
    from ..security import _require_operator_request
    _require_operator_request(request)

    path = _decode_and_validate(p)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="file not found")
    if Path(path).suffix.lower() not in AUDIO_EXTS:
        raise HTTPException(status_code=403, detail="not an audio file")

    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/local-music/cover")
def get_cover(p: str, request: Request) -> FileResponse:
    from ..security import _require_operator_request
    _require_operator_request(request)

    dir_path = _decode_and_validate(p)
    cover = find_cover_path(dir_path)
    if not cover:
        raise HTTPException(status_code=404, detail="no cover image found")

    media_type = mimetypes.guess_type(cover)[0] or "image/jpeg"
    return FileResponse(cover, media_type=media_type)


# ── Link management ──────────────────────────────────────────────────────────

class LocalLinkBody(BaseModel):
    dir_path: str


@router.post("/album-masters/{master_id}/local-link")
def link_local_dir(master_id: int, body: LocalLinkBody, request: Request) -> dict[str, Any]:
    from ..security import _require_operator_request
    _require_operator_request(request)

    resolved = str(Path(body.dir_path).resolve())
    if not resolved.startswith(_SAFE_ROOT):
        raise HTTPException(status_code=400, detail="path outside music root")
    if not Path(resolved).is_dir():
        raise HTTPException(status_code=400, detail="directory not found")

    set_local_link(master_id, resolved, "MANUAL")
    tracks = list_tracks_in_dir(resolved)
    cover = find_cover_path(resolved)
    return {
        "linked": True,
        "dir_path": resolved,
        "match_confidence": "MANUAL",
        "tracks": [_track_to_json(t) for t in tracks],
        "cover_url": f"/local-music/cover?p={_encode_path(resolved)}" if cover else None,
    }


@router.delete("/album-masters/{master_id}/local-link")
def unlink_local_dir(master_id: int, request: Request) -> dict[str, Any]:
    from ..security import _require_operator_request
    _require_operator_request(request)
    delete_local_link(master_id)
    return {"ok": True}


# ── Auto-match ───────────────────────────────────────────────────────────────

@router.post("/local-music/auto-match")
def run_auto_match(request: Request, dry_run: bool = False) -> dict[str, Any]:
    from ..security import _require_admin_request
    _require_admin_request(request)
    result = auto_match(dry_run=dry_run)
    return {"ok": True, **result}
