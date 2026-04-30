"""Ingestion batch + review queue DB surface.

Ninth slice extracted from the legacy `app/db.py`. Owns the
`ingestion_batch` and `review_queue` tables — the staging area that the
CSV ingest endpoint writes into and the operator review screen reads
from.

Public exports
  * insert_batch, finalize_batch
  * insert_review_queue, bulk_insert_review_queue,
    bulk_finalize_csv_ingest
  * list_review_queue

`app/db/__init__.py` re-exports every public symbol so existing call
sites (the /ingest/csv endpoint, the review queue routes, the test
suite) keep working unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import get_conn, get_write_conn, utc_now_iso  # noqa: E402  — package surface


def insert_batch(ingest_source: str, created_by: str | None, notes: str | None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO ingestion_batch
              (ingest_source, started_at, created_by, notes)
            VALUES (?, ?, ?, ?)
            """,
            (ingest_source, utc_now_iso(), created_by, notes),
        )
        return int(cur.lastrowid)


def finalize_batch(batch_id: int, total: int, matched: int, review: int, failed: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE ingestion_batch
            SET total_count = ?,
                matched_count = ?,
                review_count = ?,
                failed_count = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (total, matched, review, failed, utc_now_iso(), batch_id),
        )


def insert_review_queue(
    batch_id: int,
    row_no: int | None,
    category: str | None,
    payload: dict[str, Any],
    candidate: dict[str, Any] | None,
    confidence: float,
    review_status: str,
    review_note: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO review_queue
              (batch_id, row_no, category, payload_json, candidate_json, confidence_score, review_status, review_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                row_no,
                category,
                json.dumps(payload, ensure_ascii=True),
                json.dumps(candidate, ensure_ascii=True) if candidate else None,
                confidence,
                review_status,
                review_note,
                utc_now_iso(),
            ),
        )


def bulk_insert_review_queue(rows: list[dict[str, Any]]) -> int:
    """Bulk-insert N review_queue rows in a single IMMEDIATE transaction.

    Each row in `rows` must contain the same keys as `insert_review_queue`'s
    parameters: `batch_id`, `row_no`, `category`, `payload`, `candidate`,
    `confidence`, `review_status`, `review_note`.

    Replaces the prior pattern of "1 connection per row" — for a 1k-row CSV
    upload that meant 1k transactions and 1k fsync barriers. With a single
    write transaction wrapping `executemany`, the same workload commits in
    one fsync. We measured this matters most when the disk is slower than
    the metadata classifier (e.g., a network-mounted volume), where the
    pre-change bottleneck was almost entirely commit overhead.
    """
    if not rows:
        return 0
    now = utc_now_iso()
    payload_seq = [
        (
            int(row.get("batch_id") or 0),
            row.get("row_no"),
            row.get("category"),
            json.dumps(row.get("payload") or {}, ensure_ascii=True),
            json.dumps(row.get("candidate"), ensure_ascii=True)
            if row.get("candidate") is not None
            else None,
            float(row.get("confidence") or 0.0),
            str(row.get("review_status") or "NEEDS_REVIEW"),
            row.get("review_note"),
            now,
        )
        for row in rows
    ]
    with get_write_conn() as conn:
        conn.executemany(
            """
            INSERT INTO review_queue
              (batch_id, row_no, category, payload_json, candidate_json,
               confidence_score, review_status, review_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload_seq,
        )
    return len(payload_seq)


def bulk_finalize_csv_ingest(
    batch_id: int,
    totals: dict[str, int],
    review_queue_rows: list[dict[str, Any]],
) -> int:
    """End-of-CSV writer: bulk-inserts review queue rows AND updates the
    batch summary inside a single IMMEDIATE transaction so a failure
    halfway through a 10k-row CSV either commits everything or nothing.

    Returns the number of review_queue rows actually inserted.
    """
    now = utc_now_iso()
    payload_seq = [
        (
            int(row.get("batch_id") or batch_id),
            row.get("row_no"),
            row.get("category"),
            json.dumps(row.get("payload") or {}, ensure_ascii=True),
            json.dumps(row.get("candidate"), ensure_ascii=True)
            if row.get("candidate") is not None
            else None,
            float(row.get("confidence") or 0.0),
            str(row.get("review_status") or "NEEDS_REVIEW"),
            row.get("review_note"),
            now,
        )
        for row in review_queue_rows
    ]
    inserted = 0
    with get_write_conn() as conn:
        if payload_seq:
            conn.executemany(
                """
                INSERT INTO review_queue
                  (batch_id, row_no, category, payload_json, candidate_json,
                   confidence_score, review_status, review_note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload_seq,
            )
            inserted = len(payload_seq)
        conn.execute(
            """
            UPDATE ingestion_batch
            SET total_count = ?,
                matched_count = ?,
                review_count = ?,
                failed_count = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                int(totals.get("total") or 0),
                int(totals.get("matched") or 0),
                int(totals.get("review") or 0),
                int(totals.get("failed") or 0),
                now,
                int(batch_id),
            ),
        )
    return inserted


def list_review_queue(
    review_status: str,
    category: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    query = """
      SELECT id, batch_id, row_no, category, payload_json, candidate_json,
             confidence_score, review_status, review_note, created_at, reviewed_at, reviewed_by
      FROM review_queue
      WHERE review_status = ?
    """
    params: list[Any] = [review_status]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY confidence_score DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        obj = dict(row)
        obj["payload"] = json.loads(obj.pop("payload_json"))
        candidate_raw = obj.pop("candidate_json")
        obj["candidate"] = json.loads(candidate_raw) if candidate_raw else None
        results.append(obj)
    return results




__all__ = [
    "insert_batch",
    "finalize_batch",
    "insert_review_queue",
    "bulk_insert_review_queue",
    "bulk_finalize_csv_ingest",
    "list_review_queue",
]
