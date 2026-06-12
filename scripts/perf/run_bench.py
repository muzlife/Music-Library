#!/usr/bin/env python3
"""Benchmark harness — runs 7 scenarios against data/bench_library.db, prints p50/p95/max.

Usage:
    python3 scripts/perf/run_bench.py                     # bench DB (default)
    BENCH_DB_PATH=data/bench_library.db python3 scripts/perf/run_bench.py
    python3 scripts/perf/run_bench.py --save              # save docs/perf/bench_YYYYMMDD.md

Requirements: bench DB must exist (run seed_bench_db.py first).
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ── DB path guard ──────────────────────────────────────────────────────────────
_env_path = os.environ.get("BENCH_DB_PATH", "")
BENCH_DB: Path = (
    (Path(_env_path) if Path(_env_path).is_absolute() else REPO_ROOT / _env_path)
    if _env_path
    else REPO_ROOT / "data" / "bench_library.db"
)
assert "bench" in str(BENCH_DB), f"Safety: refusing non-bench DB path: {BENCH_DB}"
assert "library.db" not in BENCH_DB.name or "bench" in BENCH_DB.name, \
    f"Refusing: path looks like live DB: {BENCH_DB}"
if not BENCH_DB.exists():
    sys.exit(f"ERROR: bench DB not found at {BENCH_DB}\nRun: python3 scripts/perf/seed_bench_db.py")

# ── Point app at bench DB before importing FastAPI app ────────────────────────
os.environ["LIBRARY_DB_PATH"] = str(BENCH_DB)
os.environ["LIBRARY_AUTH_SESSION_SECRET"] = "bench-secret-not-for-production-use"
os.environ["APP_ENV"] = "bench"

# Silence uvicorn startup logging
import logging
logging.disable(logging.WARNING)

sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

# Import after setting env vars
from app.main import app  # noqa: E402

# Re-enable logging for our own output
logging.disable(logging.NOTSET)

RUNS = 30  # iterations per scenario
WARMUP = 3  # warm-up calls (not counted)


def measure(client: TestClient, url: str, *, runs: int = RUNS, warmup: int = WARMUP) -> tuple[float, float, float]:
    """Return (p50_ms, p95_ms, max_ms)."""
    for _ in range(warmup):
        client.get(url)
    times: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        r = client.get(url)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)
        if r.status_code >= 500:
            print(f"  WARNING: {url} → HTTP {r.status_code}", file=sys.stderr)
    times.sort()
    p50 = statistics.median(times)
    p95 = times[int(len(times) * 0.95)]
    return p50, p95, max(times)


def fmt(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    return f"{ms:.0f}ms"


def run(save: bool = False) -> str:
    client = TestClient(app, raise_server_exceptions=False)

    scenarios: list[tuple[str, str]] = [
        ("1. owned-items no-filter",         "/owned-items?limit=50"),
        ("2a. owned-items q=한글",           "/owned-items?q=아이&limit=50"),
        ("2b. owned-items artist_or_brand",  "/owned-items?artist_or_brand=BTS&limit=50"),
        ("3. owned-items with count",        "/owned-items?limit=50&include_total=true"),
        ("4. album-masters q=아티스트",      "/album-masters?q=아이유&limit=50"),
        ("5a. operator home/recent",         "/operator/home/recent"),
        ("5b. operator home/feed",           "/operator/home/feed?kind=registered&limit=50"),
        ("6. dashboard/collection",          "/dashboard/collection"),
        ("7. cafe/search local",             "/cafe/search?q=Track&src=local&limit=20"),
    ]

    from datetime import date
    today = date.today().strftime("%Y%m%d")
    header = f"# Perf Benchmark — {today} — bench_library.db (30k rows)\n\n"
    header += f"Scenarios: {RUNS} runs each, {WARMUP} warm-up calls\n\n"
    header += "| # | Scenario | p50 | p95 | max |\n"
    header += "|---|----------|-----|-----|-----|\n"

    rows: list[str] = []
    print(f"\nBenchmarking {len(scenarios)} scenarios × {RUNS} runs …\n")
    for label, url in scenarios:
        print(f"  {label} …", end="", flush=True)
        p50, p95, mx = measure(client, url)
        row = f"| | {label} | {fmt(p50)} | {fmt(p95)} | {fmt(mx)} |"
        rows.append(row)
        print(f" p50={fmt(p50)} p95={fmt(p95)} max={fmt(mx)}")

    report = header + "\n".join(rows) + "\n"

    if save:
        out_dir = REPO_ROOT / "docs" / "perf"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"bench_{today}.md"
        out_path.write_text(report, encoding="utf-8")
        print(f"\nSaved → {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run perf benchmarks against bench DB")
    parser.add_argument("--save", action="store_true", help="Save report to docs/perf/bench_YYYYMMDD.md")
    args = parser.parse_args()
    print(run(save=args.save))


if __name__ == "__main__":
    main()
