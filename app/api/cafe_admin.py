"""Cafe admin / operations management API.

Allows operators to manage table tablet mapping devices, and query reaction statistics.
"""

from __future__ import annotations

from typing import Any
import json
from fastapi import APIRouter, HTTPException, Request

from .. import db
from .. import security

router = APIRouter(tags=["cafe_admin"])


@router.get("/ops/cafe/devices")
def get_devices(request: Request) -> dict[str, Any]:
    """List all registered table devices. OPERATOR+"""
    security._require_operator_request(request)
    return {"items": db.list_table_devices()}


@router.post("/ops/cafe/devices")
async def add_device(request: Request) -> dict[str, Any]:
    """Register or update a table device mapping. OPERATOR+"""
    security._require_operator_request(request)
    try:
        body = json.loads(await request.body())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    table_number = str(body.get("table_number") or "").strip()
    device_id = str(body.get("device_id") or "").strip()
    device_label = str(body.get("device_label") or "").strip()

    if not table_number or not device_id:
        raise HTTPException(status_code=400, detail="table_number and device_id are required")

    dev = db.register_table_device(table_number, device_id, device_label)
    return {"ok": True, "device": dev}


@router.delete("/ops/cafe/devices/{device_id}")
def remove_device(device_id: str, request: Request) -> dict[str, Any]:
    """Deactivate/remove a device mapping by UUID. OPERATOR+"""
    security._require_operator_request(request)
    ok = db.deactivate_table_device(device_id)
    return {"ok": ok}


@router.get("/ops/cafe/stats")
def get_cafe_stats(request: Request) -> dict[str, Any]:
    """Get daily reaction statistics and recent reaction feed. OPERATOR+"""
    security._require_operator_request(request)
    with db.get_conn() as conn:
        reactions_summary = conn.execute(
            "SELECT reaction_type, COUNT(*) AS count FROM track_reaction GROUP BY reaction_type"
        ).fetchall()

        table_reactions = conn.execute(
            "SELECT table_number, COUNT(*) AS count FROM track_reaction GROUP BY table_number"
        ).fetchall()

        recent_reactions = conn.execute(
            """
            SELECT tr.*, COALESCE(ctr.requested_track, ctr.matched_track_title) AS track_title
            FROM track_reaction tr
            LEFT JOIN customer_track_request ctr ON ctr.id = tr.track_request_id
            ORDER BY tr.created_at DESC LIMIT 50
            """
        ).fetchall()

    return {
        "reactions_summary": [dict(r) for r in reactions_summary],
        "table_reactions": [dict(r) for r in table_reactions],
        "recent_reactions": [dict(r) for r in recent_reactions],
    }
