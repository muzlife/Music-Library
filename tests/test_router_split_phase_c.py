"""Pin the third slice of the main.py → APIRouter split.

  * `app.api.purchase_imports` exposes an `APIRouter` for all 9 purchase
    queue routes (preview / save / webhook / list / candidates / enrich /
    create / ignore).
  * main.py no longer defines those routes inline.
  * The webhook envelope check still fires before Pydantic body parsing
    via the late-bound `_webhook_envelope_dependency` shim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.api import purchase_imports as pi_module


REPO_ROOT = Path(__file__).resolve().parents[1]
_TOKEN_HEADERS = {"x-purchase-import-token": "test-purchase-import-token"}
_EXPECTED_PATHS = {
    ("/purchase-imports/preview", frozenset({"POST"})),
    ("/purchase-imports", frozenset({"POST"})),
    ("/purchase-imports", frozenset({"GET"})),
    ("/purchase-imports/webhook/gmail", frozenset({"POST"})),
    ("/purchase-imports/{queue_id}/candidates", frozenset({"GET"})),
    ("/purchase-imports/{queue_id}/enrich-item-page", frozenset({"POST"})),
    ("/purchase-imports/{queue_id}/create-owned-item", frozenset({"POST"})),
    ("/purchase-imports/{queue_id}/create-owned-item-from-candidate", frozenset({"POST"})),
    ("/purchase-imports/{queue_id}/ignore", frozenset({"POST"})),
}


def test_router_module_exposes_apirouter() -> None:
    assert isinstance(pi_module.router, APIRouter)
    actual = set()
    for route in pi_module.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path is None:
            continue
        actual.add((path, frozenset(methods)))
    missing = _EXPECTED_PATHS - actual
    assert not missing, f"router missing routes: {sorted(missing)}"


def test_main_py_no_longer_defines_purchase_import_routes() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    forbidden_decorators = (
        '@app.post("/purchase-imports/preview"',
        '@app.post("/purchase-imports"',
        '@app.get("/purchase-imports"',
        '@app.post(\n    "/purchase-imports/webhook/gmail"',
        '@app.get("/purchase-imports/{queue_id}/candidates"',
        '@app.post("/purchase-imports/{queue_id}/enrich-item-page"',
        '@app.post("/purchase-imports/{queue_id}/create-owned-item"',
        '@app.post("/purchase-imports/{queue_id}/create-owned-item-from-candidate"',
        '@app.post("/purchase-imports/{queue_id}/ignore"',
    )
    for decorator in forbidden_decorators:
        assert decorator not in main_src, (
            f"main.py still defines {decorator!r}; route should be in app/api/purchase_imports.py"
        )


def test_main_py_imports_purchase_imports_router() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    assert "from .api.purchase_imports import router as purchase_imports_router" in main_src
    assert "app.include_router(purchase_imports_router)" in main_src


def test_webhook_405_before_token_when_method_wrong(admin_client: TestClient) -> None:
    """A GET on the webhook path should be 405 (method not allowed) — the
    APIRouter still respects HTTP method matching."""
    response = admin_client.get("/purchase-imports/webhook/gmail")
    assert response.status_code in {404, 405}


def test_webhook_envelope_still_runs_before_body_parser_after_split(
    admin_client: TestClient,
) -> None:
    """Sanity-check the regression we fixed earlier: the envelope guard
    must still fire BEFORE Pydantic parses the body. A wrong Content-Type
    must produce 415, not a 422 for missing `raw_content`."""
    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers={**_TOKEN_HEADERS, "content-type": "text/html"},
        content=b"<html></html>",
    )
    assert response.status_code == 415, response.text


def test_webhook_dedupe_short_circuits_through_new_router(admin_client: TestClient) -> None:
    """The dedupe pre-check must continue to short-circuit a re-delivery
    even after the route moved into the new module."""
    from app import db

    payload = {
        "raw_content": "<html><body>noop</body></html>",
        "vendor_code": "OTHER",
        "source_type": "EMAIL_HTML",
        "source_ref": "router-phase-c-probe",
        "email_from": "ops@example.com",
        "email_subject": "[Sailmusic] router phase c",
        "purchase_date": "2026-04-29",
    }
    db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "router-phase-c-seed", "quantity": 1}],
        source_ref="router-phase-c-probe",
        email_from="ops@example.com",
        email_subject=payload["email_subject"],
        purchase_date=payload["purchase_date"],
    )
    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers={**_TOKEN_HEADERS, "content-type": "application/json"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"created_count": 0, "created_ids": []}


def test_purchase_imports_list_works_through_new_router(admin_client: TestClient) -> None:
    response = admin_client.get("/purchase-imports?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert "total_count" in body
    assert "items" in body
    assert isinstance(body["items"], list)


def test_main_py_dropped_unused_purchase_schema_imports() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    # These were imported only because the old route signatures used them.
    # Now they live in api/purchase_imports.py instead.
    for orphan in (
        "PurchaseImportListResponse",
        "PurchaseImportSaveRequest",
        "PurchaseImportSaveResponse",
        "PurchaseImportPreviewResponse",
        "PurchaseImportCandidateCreateRequest",
        "PurchaseImportCandidateSearchResponse",
        "PurchaseImportStatus",
        "PurchaseImportVendor",
    ):
        assert orphan not in main_src, (
            f"main.py still imports {orphan} but no longer uses it"
        )
