#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/install_backup_launchd_jobs.sh [--mode all|prod|qa] [--prod-backup-dir <dir>] <prod_app_root> <qa_app_root>

Examples:
  ./deploy/scripts/install_backup_launchd_jobs.sh /Users/me/apps/hahahoho-prod /Users/me/apps/hahahoho-qa
  ./deploy/scripts/install_backup_launchd_jobs.sh --mode qa --prod-backup-dir /Users/me/apps/hahahoho-qa/runtime/imports/prod-weekly-full /Users/me/apps/hahahoho-prod /Users/me/apps/hahahoho-qa
EOF
}

MODE="all"
PROD_BACKUP_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --prod-backup-dir)
      PROD_BACKUP_DIR="${2:-}"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

PROD_APP_ROOT="${1:-}"
QA_APP_ROOT="${2:-}"

if [[ -z "${PROD_APP_ROOT}" || -z "${QA_APP_ROOT}" ]]; then
  usage >&2
  exit 1
fi

require_expected_root_name() {
  local expected_name="$1"
  local actual_path="$2"

  if [[ "$(basename "${actual_path}")" != "${expected_name}" ]]; then
    echo "expected app root to end with ${expected_name}: ${actual_path}" >&2
    exit 1
  fi
}

require_expected_root_name "hahahoho-prod" "${PROD_APP_ROOT}"
require_expected_root_name "hahahoho-qa" "${QA_APP_ROOT}"

if [[ -z "${PROD_BACKUP_DIR}" ]]; then
  PROD_BACKUP_DIR="${PROD_APP_ROOT}/runtime/backups/weekly-full"
fi

DEST_DIR="${HOME}/Library/LaunchAgents"
mkdir -p "${DEST_DIR}"

render_plist() {
  local template_path="$1"
  local dest_path="$2"

  sed \
    -e "s|__APP_ROOT__|${PROD_APP_ROOT}|g" \
    -e "s|__PROD_APP_ROOT__|${PROD_APP_ROOT}|g" \
    -e "s|__PROD_BACKUP_DIR__|${PROD_BACKUP_DIR}|g" \
    -e "s|__QA_APP_ROOT__|${QA_APP_ROOT}|g" \
    "${template_path}" > "${dest_path}"
  plutil -lint "${dest_path}" >/dev/null
}

install_prod_jobs() {
  render_plist \
    "${ROOT_DIR}/deploy/templates/launchd/com.muzlife.backup-daily-db.plist" \
    "${DEST_DIR}/com.muzlife.backup-daily-db.plist"
  render_plist \
    "${ROOT_DIR}/deploy/templates/launchd/com.muzlife.backup-weekly-full.plist" \
    "${DEST_DIR}/com.muzlife.backup-weekly-full.plist"
}

install_qa_jobs() {
  render_plist \
    "${ROOT_DIR}/deploy/templates/launchd/com.muzlife.qa-sync-weekly.plist" \
    "${DEST_DIR}/com.muzlife.qa-sync-weekly.plist"
}

case "${MODE}" in
  all)
    install_prod_jobs
    install_qa_jobs
    ;;
  prod)
    install_prod_jobs
    ;;
  qa)
    install_qa_jobs
    ;;
  *)
    echo "Unsupported mode: ${MODE}" >&2
    exit 1
    ;;
esac

cat <<EOF
Installed backup launchd plists:
EOF

if [[ "${MODE}" == "all" || "${MODE}" == "prod" ]]; then
  cat <<EOF
  ${DEST_DIR}/com.muzlife.backup-daily-db.plist
  ${DEST_DIR}/com.muzlife.backup-weekly-full.plist
EOF
fi

if [[ "${MODE}" == "all" || "${MODE}" == "qa" ]]; then
  cat <<EOF
  ${DEST_DIR}/com.muzlife.qa-sync-weekly.plist
EOF
fi

cat <<EOF

Next steps:
EOF

if [[ "${MODE}" == "all" || "${MODE}" == "prod" ]]; then
  cat <<EOF
  launchctl bootstrap gui/\$(id -u) ${DEST_DIR}/com.muzlife.backup-daily-db.plist
  launchctl bootstrap gui/\$(id -u) ${DEST_DIR}/com.muzlife.backup-weekly-full.plist
EOF
fi

if [[ "${MODE}" == "all" || "${MODE}" == "qa" ]]; then
  cat <<EOF
  launchctl bootstrap gui/\$(id -u) ${DEST_DIR}/com.muzlife.qa-sync-weekly.plist
EOF
fi
