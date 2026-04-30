"""Pin the fourth slice of the db.py → app/db/ package split.

  * `app.db.customer_track_request` exposes the customer-track-request
    CRUD surface used by the operator workflow.
  * `app.db` re-exports every public symbol so existing call sites
    (the operator API router, the test suite) continue to work
    unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import customer_track_request as ctr_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "create_customer_track_request",
    "get_customer_track_request",
    "list_customer_track_requests",
    "count_customer_track_requests",
    "update_customer_track_request",
)


def test_customer_track_request_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(ctr_module, name)]
    assert not missing, f"app.db.customer_track_request missing: {missing}"


def test_db_package_reexports_customer_track_request_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ctr_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.customer_track_request.{name}"
        )


def test_init_py_no_longer_redefines_customer_track_request_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/customer_track_request.py"
        )


def test_legacy_customer_track_request_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        count_customer_track_requests,
        create_customer_track_request,
        get_customer_track_request,
        list_customer_track_requests,
        update_customer_track_request,
    )


def test_customer_track_request_round_trip_through_package_surface() -> None:
    """create → get → list → count → update flow via package surface.

    We don't link to a real owned_item; create_customer_track_request
    accepts owned_item_id=None which short-circuits the owned-item /
    location lookups.
    """
    db.ensure_startup_db_ready()
    created = db.create_customer_track_request(
        requested_track="phase-4 probe track",
        requested_by="phase-4-probe",
    )
    assert created
    request_id = int(created["id"])

    fetched = db.get_customer_track_request(request_id)
    assert fetched is not None
    assert fetched["requested_track"] == "phase-4 probe track"
    assert fetched["status"] == "REQUESTED"

    listed_ids = {item["id"] for item in db.list_customer_track_requests(limit=200)}
    assert request_id in listed_ids

    requested_count_before = db.count_customer_track_requests(status="REQUESTED")
    assert requested_count_before >= 1

    updated = db.update_customer_track_request(
        request_id,
        status="PLAYING",
        response_note="phase-4 probe response",
        handled_by="phase-4-probe-handler",
    )
    assert updated is not None
    assert updated["status"] == "PLAYING"
    assert updated["response_note"] == "phase-4 probe response"
    assert str(updated.get("handled_at") or "").strip() != ""

    # Cleanup so the probe row doesn't pollute later tests / counters.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM customer_track_request WHERE id = ?", (request_id,)
        )
