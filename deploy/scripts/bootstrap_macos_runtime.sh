#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/bootstrap_macos_runtime.sh <prod|qa> <app_root>

Examples:
  ./deploy/scripts/bootstrap_macos_runtime.sh prod /Users/me/apps/__PROJECT_SLUG__-prod
  ./deploy/scripts/bootstrap_macos_runtime.sh qa /Users/me/apps/__PROJECT_SLUG__-qa
EOF
}

ROLE="${1:-}"
APP_ROOT="${2:-}"

if [[ -z "${ROLE}" || -z "${APP_ROOT}" ]]; then
  usage >&2
  exit 1
fi

case "${ROLE}" in
  prod)
    TEMPLATE="${ROOT_DIR}/deploy/templates/env/.env.production.example"
    ;;
  qa)
    TEMPLATE="${ROOT_DIR}/deploy/templates/env/.env.qa.example"
    ;;
  *)
    echo "Unknown role: ${ROLE}" >&2
    usage >&2
    exit 1
    ;;
esac

mkdir -p "${APP_ROOT}/runtime/data"
mkdir -p "${APP_ROOT}/runtime/uploads"
mkdir -p "${APP_ROOT}/runtime/logs"
mkdir -p "${APP_ROOT}/runtime/backups"
mkdir -p "${APP_ROOT}/runtime/imports"

if [[ ! -f "${APP_ROOT}/.env.local" ]]; then
  cp "${TEMPLATE}" "${APP_ROOT}/.env.local"
  echo "Created ${APP_ROOT}/.env.local from template."
else
  echo "Skipped ${APP_ROOT}/.env.local because it already exists."
fi

cat <<EOF
Prepared runtime directories for ${ROLE} at:
  ${APP_ROOT}

Next steps:
  1. Edit ${APP_ROOT}/.env.local
  2. Create/activate ${APP_ROOT}/.venv
  3. Run ./deploy/scripts/install_launchd_service.sh ${ROLE} ${APP_ROOT}
EOF
