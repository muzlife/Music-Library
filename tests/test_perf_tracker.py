import os
import tempfile

os.environ.setdefault("LIBRARY_DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings

get_settings.cache_clear()

import time
from app.services.perf_tracker import perf_track
from app.db.perf_log import list_perf_log_aggregated


def test_perf_track_records_batch():
    with perf_track("test_batch", kind="BATCH"):
        time.sleep(0.01)  # 10ms 대기

    rows = list_perf_log_aggregated(kind="BATCH", is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "test_batch" in names
    row = next(r for r in rows if r["name"] == "test_batch")
    assert row["max_ms"] >= 10


def test_perf_track_records_context():
    with perf_track("test_with_ctx", kind="BATCH", context={"processed": 42}):
        pass

    from app.db.perf_log import list_perf_log_detail

    rows = list_perf_log_detail(name="test_with_ctx")
    assert len(rows) >= 1
    import json

    ctx = json.loads(rows[0]["context_json"] or "{}")
    assert ctx.get("processed") == 42


def test_perf_track_records_even_on_exception():
    try:
        with perf_track("test_exc", kind="BATCH"):
            raise ValueError("test error")
    except ValueError:
        pass

    rows = list_perf_log_aggregated(kind="BATCH", is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "test_exc" in names
