#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/restore_backup_to_qa.sh <qa_app_root> <db_backup_path> [uploads_tgz]

Examples:
  ./deploy/scripts/restore_backup_to_qa.sh /Users/me/apps/__PROJECT_SLUG__-qa /tmp/library-20260413.db
  ./deploy/scripts/restore_backup_to_qa.sh /Users/me/apps/__PROJECT_SLUG__-qa /tmp/library-20260413.db /tmp/uploads-20260413.tgz
EOF
}

QA_APP_ROOT="${1:-}"
DB_BACKUP_PATH="${2:-}"
UPLOADS_TGZ="${3:-}"

if [[ -z "${QA_APP_ROOT}" || -z "${DB_BACKUP_PATH}" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "${DB_BACKUP_PATH}" ]]; then
  echo "DB backup not found: ${DB_BACKUP_PATH}" >&2
  exit 1
fi

mkdir -p "${QA_APP_ROOT}/runtime/data"
mkdir -p "${QA_APP_ROOT}/runtime/imports"
cp "${DB_BACKUP_PATH}" "${QA_APP_ROOT}/runtime/data/library.db"

if [[ -n "${UPLOADS_TGZ}" ]]; then
  if [[ ! -f "${UPLOADS_TGZ}" ]]; then
    echo "Uploads archive not found: ${UPLOADS_TGZ}" >&2
    exit 1
  fi
  TARGET_UPLOADS_DIR="${QA_APP_ROOT}/app/static/uploads"
  rm -rf "${TARGET_UPLOADS_DIR}"
  mkdir -p "${TARGET_UPLOADS_DIR}"
  TMP_EXTRACT_DIR="$(mktemp -d)"
  trap 'rm -rf "${TMP_EXTRACT_DIR}"' EXIT
  tar -xzf "${UPLOADS_TGZ}" -C "${TMP_EXTRACT_DIR}"
  if [[ -d "${TMP_EXTRACT_DIR}/uploads" ]]; then
    cp -R "${TMP_EXTRACT_DIR}/uploads/." "${TARGET_UPLOADS_DIR}/"
  fi
fi

cat <<EOF
Restored QA backup into:
  ${QA_APP_ROOT}

Next steps:
  launchctl kickstart -k gui/\$(id -u)/com.muzlife.library-qa
  ./scripts/run_deploy_preflight.sh
  ./scripts/run_qa_full.sh
EOF
