"""Activity log API — audit history, cabinet movement history, server logs.

Endpoints:
  GET /admin/activity-log                          — full audit log (admin)
  GET /admin/activity-log/album-master/{id}        — album_master audit entries
  GET /admin/activity-log/owned-item/{id}          — owned_item audit + location events
  GET /admin/server-logs                           — tail of server stdout/stderr log
  GET /owned-items/{id}/location-events            — cabinet history (operator+)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import db
from ..config import get_settings
from ..security import _require_admin_request, _require_operator_request
from ..db.error_log import (
    list_error_log as _list_error_log,
    get_unread_error_count as _get_unread_count,
    acknowledge_error_log as _acknowledge,
)
from ..db.perf_log import (
    list_perf_log_aggregated as _list_perf_agg,
    list_perf_log_detail as _list_perf_detail,
)

router = APIRouter(tags=["activity"])

_LOG_TAIL_MAX = 2000


def _tail_file(path: str | Path, lines: int) -> list[str]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    all_lines = text.splitlines()
    return all_lines[-lines:] if len(all_lines) > lines else all_lines


# ── Audit log ──────────────────────────────────────────────────────

@router.get("/admin/activity-log", include_in_schema=False)
def get_activity_log(
    request: Request,
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    changed_by: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin_request(request)
    result = db.list_audit_log(
        entity_type=entity_type, entity_id=entity_id,
        action=action, changed_by=changed_by,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return {"total_count": result["total_count"], "offset": offset, "items": result["items"]}


@router.get("/admin/activity-log/album-master/{album_master_id}", include_in_schema=False)
def get_album_master_audit(
    album_master_id: int,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin_request(request)
    result = db.list_audit_log(entity_type="album_master", entity_id=album_master_id, limit=limit, offset=offset)
    return {"album_master_id": album_master_id, "total_count": result["total_count"], "items": result["items"]}


@router.get("/admin/activity-log/owned-item/{owned_item_id}", include_in_schema=False)
def get_owned_item_activity(
    owned_item_id: int,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin_request(request)
    audit = db.list_audit_log(entity_type="owned_item", entity_id=owned_item_id, limit=limit, offset=offset)
    location_rows = db.list_owned_item_location_events(owned_item_id=owned_item_id, limit=limit, offset=offset)
    return {
        "owned_item_id": owned_item_id,
        "audit": {"total_count": audit["total_count"], "items": audit["items"]},
        "location_events": {"total_count": len(location_rows), "items": location_rows},
    }


# ── Cabinet history (operator level) ──────────────────────────────

@router.get("/owned-items/{owned_item_id}/location-events", include_in_schema=False)
def get_owned_item_location_events(
    owned_item_id: int,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_operator_request(request)
    rows = db.list_owned_item_location_events(owned_item_id=owned_item_id, limit=limit, offset=offset)
    return {"owned_item_id": owned_item_id, "total_count": len(rows), "items": rows}


@router.get("/admin/activity-log/location-events", include_in_schema=False)
def get_all_location_events(
    request: Request,
    movement_kind: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin_request(request)
    rows = db.list_recent_location_events(
        limit=limit, offset=offset,
        movement_kind=movement_kind,
        date_from=date_from, date_to=date_to,
    )
    return {"total_count": len(rows), "offset": offset, "items": rows}


# ── Server logs ────────────────────────────────────────────────────

@router.get("/admin/server-logs", include_in_schema=False)
def get_server_logs(
    request: Request,
    stream: str = Query(default="stderr", pattern="^(stdout|stderr)$"),
    tail: int = Query(default=200, ge=10, le=_LOG_TAIL_MAX),
) -> dict[str, Any]:
    _require_admin_request(request)
    settings = get_settings()
    if stream == "stdout":
        log_path = settings.server_stdout_log_path
    else:
        log_path = settings.server_stderr_log_path

    if not log_path:
        raise HTTPException(status_code=503, detail="SERVER_STDERR_LOG_PATH / SERVER_STDOUT_LOG_PATH not configured")

    lines = _tail_file(log_path, tail)
    return {
        "stream": stream,
        "log_path": log_path,
        "tail": tail,
        "line_count": len(lines),
        "lines": lines,
    }


# ── Error logs ─────────────────────────────────────────────────────

@router.get("/admin/error-log", include_in_schema=False)
def get_error_log(
    request: Request,
    is_read: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_operator_request(request)
    items = _list_error_log(is_read=is_read, limit=limit, offset=offset)
    return {"items": items, "total_count": len(items), "limit": limit, "offset": offset}


@router.get("/admin/error-log/unread-count", include_in_schema=False)
def get_error_log_unread_count(request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    return {"count": _get_unread_count()}


@router.post("/admin/error-log/acknowledge", include_in_schema=False)
def acknowledge_errors(
    request: Request,
    ids: list[int] | None = Query(default=None),
) -> dict[str, Any]:
    _require_admin_request(request)
    updated = _acknowledge(ids=ids)
    return {"updated": updated}


@router.patch("/admin/error-log/{error_id}/acknowledge", include_in_schema=False)
def acknowledge_single_error(error_id: int, request: Request) -> dict[str, Any]:
    _require_admin_request(request)
    updated = _acknowledge(ids=[error_id])
    return {"updated": updated, "id": error_id}


# ── Performance logs ───────────────────────────────────────────────────

@router.get("/admin/perf-log", include_in_schema=False)
def get_perf_log(
    request: Request,
    kind: str | None = Query(default=None),
    is_slow_only: bool = Query(default=False),
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    _require_operator_request(request)
    items = _list_perf_agg(kind=kind, is_slow_only=is_slow_only, days=days)
    return {"items": items, "total_count": len(items)}


@router.get("/admin/perf-log/detail", include_in_schema=False)
def get_perf_log_detail(
    request: Request,
    name: str = Query(...),
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_operator_request(request)
    items = _list_perf_detail(name=name, kind=kind, limit=limit, offset=offset)
    return {"items": items, "total_count": len(items)}
