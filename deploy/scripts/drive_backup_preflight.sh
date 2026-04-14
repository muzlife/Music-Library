#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${1:-}"

if [[ -z "${APP_ROOT}" ]]; then
  echo '{"status":"error","reason":"missing-app-root"}'
  exit 1
fi

ENV_FILE="${APP_ROOT}/.env.local"
if [[ -f "${ENV_FILE}" ]]; then
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    if [[ "${key}" == "GOOGLE_DRIVE_BACKUP_DIR" ]]; then
      GOOGLE_DRIVE_BACKUP_DIR="${value}"
      export GOOGLE_DRIVE_BACKUP_DIR
    fi
  done < "${ENV_FILE}"
fi

GOOGLE_DRIVE_BACKUP_DIR="${GOOGLE_DRIVE_BACKUP_DIR:-}"

if [[ -z "${GOOGLE_DRIVE_BACKUP_DIR}" ]]; then
  echo '{"status":"error","reason":"missing-google-drive-backup-dir"}'
  exit 1
fi

mkdir -p "${GOOGLE_DRIVE_BACKUP_DIR}"

if [[ ! -d "${GOOGLE_DRIVE_BACKUP_DIR}" || ! -w "${GOOGLE_DRIVE_BACKUP_DIR}" ]]; then
  printf '{"status":"error","reason":"drive-dir-not-writable","google_drive_backup_dir":"%s"}\n' "${GOOGLE_DRIVE_BACKUP_DIR}"
  exit 1
fi

python3 - <<'PY'
import json
import os

print(json.dumps({
    "status": "ready",
    "google_drive_backup_dir": os.environ.get("GOOGLE_DRIVE_BACKUP_DIR", ""),
}))
PY
