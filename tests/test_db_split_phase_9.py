"""Pin the ninth slice of the db.py → app/db/ package split.

  * `app.db.ingestion_batch` exposes the CSV ingest staging surface —
    `insert_batch` / `finalize_batch` for the batch row plus
    `insert_review_queue` / `bulk_insert_review_queue` /
    `bulk_finalize_csv_ingest` / `list_review_queue` for the review
    queue rows the operator screen reads from.
  * `app.db` re-exports every symbol so existing call sites (the
    `/ingest/csv` endpoint, the review queue routes, the test suite)
    keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import ingestion_batch as ib_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "insert_batch",
    "finalize_batch",
    "insert_review_queue",
    "bulk_insert_review_queue",
    "bulk_finalize_csv_ingest",
    "list_review_queue",
)


def test_ingestion_batch_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(ib_module, name)]
    assert not missing, f"app.db.ingestion_batch missing: {missing}"


def test_db_package_reexports_ingestion_batch_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ib_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.ingestion_batch.{name}"
        )


def test_init_py_no_longer_redefines_ingestion_batch_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/ingestion_batch.py"
        )


def test_legacy_ingestion_batch_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        bulk_finalize_csv_ingest,
        bulk_insert_review_queue,
        finalize_batch,
        insert_batch,
        insert_review_queue,
        list_review_queue,
    )


def test_csv_batch_round_trip_through_package_surface() -> None:
    """insert_batch → bulk_insert_review_queue → list_review_queue →
    finalize_batch via the package surface, then verify totals stick."""
    db.ensure_startup_db_ready()

    batch_id = db.insert_batch(
        ingest_source="phase-9-probe",
        created_by="phase-9-suite",
        notes="phase-9 smoke",
    )
    assert isinstance(batch_id, int) and batch_id > 0

    rows = [
        {
            "batch_id": batch_id,
            "row_no": idx,
            "category": "ALBUM",
            "payload": {"title": f"phase9-{idx}"},
            "candidate": None,
            "confidence": 0.5,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for idx in range(3)
    ]
    inserted = db.bulk_insert_review_queue(rows)
    assert inserted == 3

    listed = db.list_review_queue("NEEDS_REVIEW", "ALBUM", limit=100, offset=0)
    titles = {item["payload"].get("title") for item in listed if int(item.get("batch_id") or 0) == batch_id}
    assert titles >= {"phase9-0", "phase9-1", "phase9-2"}

    db.finalize_batch(batch_id, total=3, matched=0, review=3, failed=0)

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT total_count, review_count, completed_at FROM ingestion_batch WHERE id = ?",
            (batch_id,),
        ).fetchone()
    assert row is not None
    assert int(row["total_count"]) == 3
    assert int(row["review_count"]) == 3
    assert row["completed_at"] is not None

    # Cleanup so the probe doesn't pollute downstream fixtures.
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM review_queue WHERE batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM ingestion_batch WHERE id = ?", (batch_id,))


def test_bulk_finalize_csv_ingest_combines_insert_and_summary() -> None:
    """`bulk_finalize_csv_ingest` should atomically insert rows AND update
    the batch summary in one shot."""
    db.ensure_startup_db_ready()

    batch_id = db.insert_batch(
        ingest_source="phase-9-bulk-probe",
        created_by="phase-9-suite",
        notes="phase-9 bulk-finalize smoke",
    )

    rows = [
        {
            "batch_id": batch_id,
            "row_no": idx,
            "category": "GOODS",
            "payload": {"sku": f"bulk-{idx}"},
            "candidate": None,
            "confidence": 0.25,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for idx in range(2)
    ]
    inserted = db.bulk_finalize_csv_ingest(
        batch_id,
        totals={"total": 2, "matched": 0, "review": 2, "failed": 0},
        review_queue_rows=rows,
    )
    assert inserted == 2

    with db.get_conn() as conn:
        summary = conn.execute(
            "SELECT total_count, review_count, completed_at FROM ingestion_batch WHERE id = ?",
            (batch_id,),
        ).fetchone()
        review_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    assert summary is not None and int(summary["total_count"]) == 2
    assert summary["completed_at"] is not None
    assert int(review_rows["n"]) == 2

    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM review_queue WHERE batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM ingestion_batch WHERE id = ?", (batch_id,))
