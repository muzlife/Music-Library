"""Coverage for the bulk CSV ingest path.

Pins:
  * `bulk_insert_review_queue` writes N rows in a single IMMEDIATE transaction.
  * `bulk_finalize_csv_ingest` updates the batch summary AND writes review
    queue rows atomically — a SQL failure mid-finalize rolls back both.
  * The `/ingest/csv` endpoint produces the same end state as before:
    rows in `review_queue`, `ingestion_batch.completed_at` set, totals match.
"""

from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db


def test_bulk_insert_review_queue_writes_all_rows() -> None:
    db.ensure_startup_db_ready()
    batch_id = db.insert_batch("UNIT_BULK_TEST", "tester", "bulk insert pin")
    rows = [
        {
            "batch_id": batch_id,
            "row_no": i,
            "category": "LP",
            "payload": {"title": f"row-{i}", "artist_or_brand": "QA Bulk"},
            "candidate": {"score": 0.5},
            "confidence": 0.5,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for i in range(1, 11)
    ]
    inserted = db.bulk_insert_review_queue(rows)
    assert inserted == 10

    with db.get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE batch_id = ?", (batch_id,)
        ).fetchone()["n"]
    assert count == 10


def test_bulk_insert_review_queue_handles_empty() -> None:
    db.ensure_startup_db_ready()
    assert db.bulk_insert_review_queue([]) == 0


def test_bulk_finalize_csv_ingest_rolls_back_on_summary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the ingestion_batch UPDATE fails, the review_queue inserts must
    not survive — the IMMEDIATE transaction guarantees all-or-nothing."""
    db.ensure_startup_db_ready()
    batch_id = db.insert_batch("UNIT_BULK_TEST", "tester", "atomicity pin")

    rows = [
        {
            "batch_id": batch_id,
            "row_no": i,
            "category": "LP",
            "payload": {"title": f"atomic-{i}"},
            "candidate": None,
            "confidence": 0.0,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for i in range(1, 6)
    ]

    real_get_write = db.get_write_conn
    poisoned_totals = {"total": "not-an-int", "matched": 0, "review": 0, "failed": 0}

    with pytest.raises((sqlite3.Error, ValueError, TypeError)):
        db.bulk_finalize_csv_ingest(
            batch_id=batch_id,
            totals=poisoned_totals,  # int() coercion raises in the helper
            review_queue_rows=rows,
        )

    # The rows must have been rolled back along with the failed UPDATE.
    with db.get_conn() as conn:
        leaked = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE batch_id = ?", (batch_id,)
        ).fetchone()["n"]
    assert leaked == 0


def test_bulk_finalize_csv_ingest_writes_summary_when_no_rows() -> None:
    db.ensure_startup_db_ready()
    batch_id = db.insert_batch("UNIT_BULK_TEST", "tester", "no rows pin")
    inserted = db.bulk_finalize_csv_ingest(
        batch_id=batch_id,
        totals={"total": 0, "matched": 0, "review": 0, "failed": 0},
        review_queue_rows=[],
    )
    assert inserted == 0
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT total_count, completed_at FROM ingestion_batch WHERE id = ?",
            (batch_id,),
        ).fetchone()
    assert row is not None
    assert int(row["total_count"]) == 0
    assert str(row["completed_at"] or "").strip() != ""


def test_csv_ingest_endpoint_writes_to_review_queue(admin_client: TestClient) -> None:
    csv_text = (
        "category,artist_or_brand,title,barcode,catalog_no\n"
        "LP,QA Artist A,Test Album A,8809000000001,QA-CAT-A\n"
        "CD,QA Artist B,Test Album B,8809000000002,QA-CAT-B\n"
        "LP,QA Artist C,Test Album C,,QA-CAT-C\n"
    )
    response = admin_client.post(
        "/ingest/csv",
        files={"file": ("upload.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
        data={"default_category": "LP", "created_by": "tester"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 3
    assert body["matched_count"] + body["review_count"] + body["failed_count"] == 3

    with db.get_conn() as conn:
        rq_count = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE batch_id = ?", (body["batch_id"],)
        ).fetchone()["n"]
        batch = conn.execute(
            "SELECT total_count, matched_count, review_count, failed_count, completed_at "
            "FROM ingestion_batch WHERE id = ?",
            (body["batch_id"],),
        ).fetchone()
    assert rq_count == 3
    assert int(batch["total_count"]) == 3
    assert str(batch["completed_at"] or "").strip() != ""
