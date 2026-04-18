#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHORT_MODE="0"

ARGS=()
for arg in "$@"; do
  if [[ "${arg}" == "--short" ]]; then
    SHORT_MODE="1"
  else
    ARGS+=("${arg}")
  fi
done

PROD_APP_ROOT="${ARGS[0]:-${ROOT_DIR}}"
QA_APP_ROOT="${ARGS[1]:-}"

if ! STATUS_JSON="$("${ROOT_DIR}/deploy/scripts/backup_status.sh" "${PROD_APP_ROOT}" "${QA_APP_ROOT}")"; then
  echo "실패: 백업 상태를 읽지 못했습니다."
  exit 1
fi

python3 - "${STATUS_JSON}" "${SHORT_MODE}" <<'PY'
from __future__ import annotations

import json
import sys


payload = json.loads(sys.argv[1])
short_mode = sys.argv[2] == "1"

ok_statuses = {"created", "skipped", "applied", "mirrored", "uploaded"}
scope_defs = [
    ("daily_db", "daily-db"),
    ("weekly_full", "weekly-full"),
    ("qa_sync", "qa-sync"),
]

scopes: list[dict[str, str | None]] = []
warn_count = 0
fail_count = 0
for key, label in scope_defs:
    raw = payload.get(key)
    if not isinstance(raw, dict):
        continue
    status = str(raw.get("status") or "missing").strip() or "missing"
    manifest_path = str(raw.get("manifest_path") or "").strip() or None
    backup_path = str(raw.get("backup_path") or "").strip() or None
    if status in ok_statuses:
        level = "ok"
    elif status == "missing":
        level = "warn"
        warn_count += 1
    else:
        level = "fail"
        fail_count += 1
    scopes.append(
        {
            "label": label,
            "status": status,
            "level": level,
            "manifest_path": manifest_path,
            "backup_path": backup_path,
        }
    )

if fail_count:
    summary = "실패: 백업 상태 점검 중 실패 항목이 있습니다."
elif warn_count:
    summary = "주의: 백업 상태 메타가 비어 있습니다. AFP/외장 마운트 지연이면 launchd 로그를 확인하세요."
else:
    summary = "정상: 백업 상태 메타를 읽었습니다."

print(summary)
for scope in scopes:
    label = str(scope["label"])
    status = str(scope["status"])
    if short_mode:
        print(f"{label}={status}")
        continue
    print(f"- {label}: {status}")
    manifest_path = scope.get("manifest_path")
    backup_path = scope.get("backup_path")
    if manifest_path:
        print(f"  manifest: {manifest_path}")
    if backup_path:
        print(f"  backup: {backup_path}")
PY
