#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${1:-}"

if [[ -z "${APP_ROOT}" ]]; then
  echo '{"status":"error","reason":"missing-app-root"}'
  exit 1
fi

ENV_FILE="${APP_ROOT}/.env.local"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

GCS_BACKUP_PREFIX="${GCS_BACKUP_PREFIX:-}"
GSUTIL_BIN="${GSUTIL_BIN:-gsutil}"

if [[ -z "${GCS_BACKUP_PREFIX}" ]]; then
  echo '{"status":"error","reason":"missing-gcs-backup-prefix"}'
  exit 1
fi

if ! command -v "${GSUTIL_BIN}" >/dev/null 2>&1; then
  printf '{"status":"error","reason":"missing-gsutil","gsutil_bin":"%s"}\n' "${GSUTIL_BIN}"
  exit 1
fi

"${GSUTIL_BIN}" ls "${GCS_BACKUP_PREFIX}" >/dev/null 2>&1 || true

python3 - <<'PY'
import json
import os

print(json.dumps({
    "status": "ready",
    "gcs_backup_prefix": os.environ.get("GCS_BACKUP_PREFIX", ""),
    "gsutil_bin": os.popen(f"command -v {os.environ.get('GSUTIL_BIN', 'gsutil')}").read().strip() or os.environ.get("GSUTIL_BIN", "gsutil"),
}))
PY
