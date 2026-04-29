"""Webhook hardening regression coverage.

Pins the contract for `/purchase-imports/webhook/gmail`:
  * unsupported Content-Type → 415
  * declared Content-Length over the cap → 413
  * pre-token check still wins (token mismatch beats payload validation)
  * second delivery with the same source_ref short-circuits before parsing
    (idempotent for Gmail / Zapier-style retries)
  * the underlying DB helper is robust to blank inputs
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db, main


_TOKEN_HEADERS = {"x-purchase-import-token": "test-purchase-import-token"}


def test_webhook_rejects_non_json_content_type(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers={**_TOKEN_HEADERS, "content-type": "text/html"},
        content=b"<html></html>",
    )
    assert response.status_code == 415, response.text


def test_webhook_rejects_oversized_declared_body(admin_client: TestClient) -> None:
    headers = {
        **_TOKEN_HEADERS,
        "content-type": "application/json",
        "content-length": str(main.PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES + 1),
    }
    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers=headers,
        content=b"{}",  # invalid JSON, but length check fires first
    )
    assert response.status_code == 413, response.text


def test_webhook_rejects_missing_token(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers={"x-purchase-import-token": "wrong"},
        json={"raw_content": "noop"},
    )
    assert response.status_code == 403, response.text


def test_webhook_dedupes_repeat_delivery_by_source_ref(admin_client: TestClient) -> None:
    payload = {
        "raw_content": "<html><body>noop</body></html>",
        "vendor_code": "OTHER",
        "source_type": "EMAIL_HTML",
        "source_ref": "gmail-message-id-test-123",
        "email_from": "ops@example.com",
        "email_subject": "[Sailmusic] order #00",
        "purchase_date": "2026-04-29",
    }
    # Pre-seed a row matching the webhook (vendor_code, source_ref) so the
    # pre-check fires without us needing the parser to produce items.
    db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "seeded-row", "quantity": 1}],
        source_ref="gmail-message-id-test-123",
        email_from="ops@example.com",
        email_subject=payload["email_subject"],
        purchase_date=payload["purchase_date"],
    )
    assert db.has_purchase_import_for_source_ref("OTHER", "gmail-message-id-test-123") is True

    response = admin_client.post(
        "/purchase-imports/webhook/gmail",
        headers={**_TOKEN_HEADERS, "content-type": "application/json"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"created_count": 0, "created_ids": []}


def test_has_purchase_import_for_source_ref_handles_blank_inputs() -> None:
    assert db.has_purchase_import_for_source_ref("", "anything") is False
    assert db.has_purchase_import_for_source_ref("OTHER", "") is False
    assert db.has_purchase_import_for_source_ref("OTHER", "definitely-not-seeded") is False
