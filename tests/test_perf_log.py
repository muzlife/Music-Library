import os, tempfile
os.environ.setdefault("LIBRARY_DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

from app.db.perf_log import insert_perf_log, list_perf_log_aggregated, list_perf_log_detail


def test_insert_and_aggregate():
    insert_perf_log(kind="API", name="GET /owned-items", duration_ms=450, is_slow=True)
    insert_perf_log(kind="API", name="GET /owned-items", duration_ms=80, is_slow=False)
    insert_perf_log(kind="BATCH", name="metadata_sync", duration_ms=38200, is_slow=False)

    rows = list_perf_log_aggregated(kind=None, is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "GET /owned-items" in names
    assert "metadata_sync" in names

    api_row = next(r for r in rows if r["name"] == "GET /owned-items")
    assert api_row["count"] == 2
    assert api_row["max_ms"] == 450
    assert api_row["avg_ms"] == 265


def test_is_slow_filter():
    insert_perf_log(kind="QUERY", name="SELECT ...", duration_ms=350, is_slow=True)
    rows = list_perf_log_aggregated(kind=None, is_slow_only=True, days=1)
    assert all(r["slow_count"] > 0 for r in rows)


def test_detail_list():
    insert_perf_log(kind="API", name="POST /owned-items", duration_ms=120, is_slow=False)
    rows = list_perf_log_detail(name="POST /owned-items", limit=10)
    assert len(rows) >= 1
    assert rows[0]["duration_ms"] == 120
