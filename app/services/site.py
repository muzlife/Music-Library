"""Static-serving constants and ops helpers shared across API route modules.

Defined here so api/* can import directly instead of going through the
_main() late-binding pattern that caused circular-import issues.
"""
from __future__ import annotations
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# app/static/ — derived from this file's location (app/services/site.py → app/)
STATIC_DIR: Path = Path(__file__).resolve().parents[1] / "static"
IMAGE_UPLOAD_DIR: Path = STATIC_DIR / "uploads"
MAX_IMAGE_UPLOAD_BYTES: int = 20 * 1024 * 1024

HTML_NO_CACHE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
HTML_PROD_CACHE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
}


def _is_qa_env() -> bool:
    return os.getenv("APP_ENV", "production").lower() in {"qa", "dev", "staging"}


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
QA_MASTER_SHEET_PATH: Path = _PROJECT_ROOT / "docs" / "qa" / "qa_master_sheet.csv"
QA_MANUAL_SHEET_PATH: Path = _PROJECT_ROOT / "docs" / "qa" / "qa_manual_remaining.csv"


def _tail_text_lines(path: Path, limit: int = 2) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    lines = [str(line).strip() for line in text.splitlines() if str(line).strip()]
    if limit <= 0:
        return lines
    return lines[-limit:]


def _read_qa_summary() -> dict[str, Any]:
    if not QA_MASTER_SHEET_PATH.exists():
        return {
            "total_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "blocked_count": 0,
            "not_started_count": 0,
            "remaining_items": [],
            "qa_master_sheet": str(QA_MASTER_SHEET_PATH),
            "qa_manual_sheet": str(QA_MANUAL_SHEET_PATH),
            "updated_at": None,
        }

    with QA_MASTER_SHEET_PATH.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    pass_count = len([row for row in rows if str(row.get("status") or "").strip() == "Pass"])
    fail_count = len([row for row in rows if str(row.get("status") or "").strip() == "Fail"])
    blocked_count = len([row for row in rows if str(row.get("status") or "").strip() == "Blocked"])
    not_started_rows = [row for row in rows if str(row.get("status") or "").strip() == "Not Started"]
    remaining_items = [
        {
            "suite_id": str(row.get("suite_id") or "").strip(),
            "area": str(row.get("area") or "").strip(),
            "priority": str(row.get("priority") or "").strip(),
            "title": str(row.get("title") or "").strip(),
            "role": str(row.get("role") or "").strip(),
        }
        for row in not_started_rows[:6]
    ]
    updated_at = datetime.fromtimestamp(QA_MASTER_SHEET_PATH.stat().st_mtime, timezone.utc).isoformat()
    return {
        "total_count": len(rows),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "blocked_count": blocked_count,
        "not_started_count": len(not_started_rows),
        "remaining_items": remaining_items,
        "qa_master_sheet": str(QA_MASTER_SHEET_PATH),
        "qa_manual_sheet": str(QA_MANUAL_SHEET_PATH),
        "updated_at": updated_at,
    }


def _serialize_env_value(value: str) -> str:
    if not value:
        return '""'
    if re.search(r'[\s#"\'=]', value):
        return json.dumps(value)
    return value


def _write_env_updates(path: Path, updates: dict[str, str]) -> None:
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    rendered_lines: list[str] = []
    for raw_line in existing_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered_lines.append(raw_line)
            continue
        key, _value = raw_line.split("=", 1)
        env_key = key.strip()
        if env_key in pending:
            rendered_lines.append(f"{env_key}={_serialize_env_value(pending.pop(env_key))}")
        else:
            rendered_lines.append(raw_line)
    for env_key, env_value in pending.items():
        rendered_lines.append(f"{env_key}={_serialize_env_value(env_value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rendered_lines).rstrip() + "\n", encoding="utf-8")
