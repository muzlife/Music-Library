#!/usr/bin/env bash
set -euo pipefail

PROD_APP_ROOT="${1:-}"
QA_APP_ROOT="${2:-}"

if [[ -z "${PROD_APP_ROOT}" ]]; then
  echo '{"status":"error","reason":"missing-prod-app-root"}'
  exit 1
fi

python3 - "$PROD_APP_ROOT" "$QA_APP_ROOT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


prod_root = Path(sys.argv[1])
qa_root = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"status": "missing", "manifest_path": str(path)}
    return json.loads(path.read_text("utf-8"))


payload = {
    "paths": {
        "prod_app_root": str(prod_root),
        "qa_app_root": str(qa_root) if qa_root else None,
    },
    "daily_db": load_json(prod_root / "runtime" / "backups" / ".state" / "daily-db-latest.json"),
    "weekly_full": load_json(prod_root / "runtime" / "backups" / ".state" / "weekly-full-latest.json"),
    "qa_sync": load_json(qa_root / "runtime" / "backups" / ".state" / "qa-sync-latest.json") if qa_root else None,
}

print(json.dumps(payload, ensure_ascii=False))
PY
