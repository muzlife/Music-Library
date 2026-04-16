#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/install_launchd_service.sh <prod|qa> <app_root>

Examples:
  ./deploy/scripts/install_launchd_service.sh prod /Users/me/apps/hahahoho-prod
  ./deploy/scripts/install_launchd_service.sh qa /Users/me/apps/hahahoho-qa
EOF
}

ROLE="${1:-}"
APP_ROOT="${2:-}"

if [[ -z "${ROLE}" || -z "${APP_ROOT}" ]]; then
  usage >&2
  exit 1
fi

require_expected_app_root_name() {
  local role="$1"
  local app_root="$2"
  local expected_name=""

  case "${role}" in
    prod)
      expected_name="hahahoho-prod"
      ;;
    qa)
      expected_name="hahahoho-qa"
      ;;
    *)
      return 0
      ;;
  esac

  if [[ "$(basename "${app_root}")" != "${expected_name}" ]]; then
    echo "${role} app root must end with ${expected_name}: ${app_root}" >&2
    exit 1
  fi
}

case "${ROLE}" in
  prod)
    TEMPLATE="${ROOT_DIR}/deploy/templates/launchd/com.muzlife.library-prod.plist"
    FILENAME="com.muzlife.library-prod.plist"
    ;;
  qa)
    TEMPLATE="${ROOT_DIR}/deploy/templates/launchd/com.muzlife.library-qa.plist"
    FILENAME="com.muzlife.library-qa.plist"
    ;;
  *)
    echo "Unknown role: ${ROLE}" >&2
    usage >&2
    exit 1
    ;;
esac

require_expected_app_root_name "${ROLE}" "${APP_ROOT}"

DEST_DIR="${HOME}/Library/LaunchAgents"
DEST_PATH="${DEST_DIR}/${FILENAME}"
mkdir -p "${DEST_DIR}"

sed "s|__APP_ROOT__|${APP_ROOT}|g" "${TEMPLATE}" > "${DEST_PATH}"
plutil -lint "${DEST_PATH}" >/dev/null

cat <<EOF
Installed launchd plist:
  ${DEST_PATH}

Next steps:
  launchctl bootstrap gui/\$(id -u) ${DEST_PATH}
  launchctl kickstart -k gui/\$(id -u)/${FILENAME%.plist}
EOF
