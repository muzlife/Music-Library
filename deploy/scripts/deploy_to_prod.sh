#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/deploy_to_prod.sh [prod_ssh_target] [prod_app_root]

Environment:
  PROD_SSH_TARGET          Remote SSH target, e.g. matia@macmini2018.local
  PROD_APP_ROOT            Remote app root, e.g. /Users/matia/apps/hahahoho-prod
  PROD_SSH_KEY_PATH        Optional SSH private key path
  PROD_LAUNCHD_LABEL       launchd label, default: com.muzlife.library-prod
  PROD_HEALTHCHECK_URL     Remote local health URL, default: http://127.0.0.1:8000/health
  REMOTE_INSTALL_REQUIREMENTS
                          1 to run pip install -r requirements.txt after sync (default: 1)
EOF
}

PROD_SSH_TARGET="${PROD_SSH_TARGET:-${1:-}}"
PROD_APP_ROOT="${PROD_APP_ROOT:-${2:-}}"
PROD_SSH_KEY_PATH="${PROD_SSH_KEY_PATH:-}"
PROD_LAUNCHD_LABEL="${PROD_LAUNCHD_LABEL:-com.muzlife.library-prod}"
PROD_HEALTHCHECK_URL="${PROD_HEALTHCHECK_URL:-http://127.0.0.1:8000/health}"
REMOTE_INSTALL_REQUIREMENTS="${REMOTE_INSTALL_REQUIREMENTS:-1}"

if [[ -z "${PROD_SSH_TARGET}" || -z "${PROD_APP_ROOT}" ]]; then
  usage >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync not found" >&2
  exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh not found" >&2
  exit 1
fi

RELEASE_SHA="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
RELEASE_BRANCH="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"

SSH_CMD=(ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes)
RSYNC_RSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes"

if [[ -n "${PROD_SSH_KEY_PATH}" ]]; then
  SSH_CMD+=(-i "${PROD_SSH_KEY_PATH}")
  RSYNC_RSH="${RSYNC_RSH} -i ${PROD_SSH_KEY_PATH}"
fi

ssh_exec() {
  "${SSH_CMD[@]}" "${PROD_SSH_TARGET}" "$@"
}

echo "[1/5] Verify remote SSH connectivity"
ssh_exec "echo ok-prod >/dev/null"

echo "[2/5] Create pre-deploy DB backup on prod"
ssh_exec "cd '${PROD_APP_ROOT}' && /bin/bash ./deploy/scripts/backup_daily_db.sh '${PROD_APP_ROOT}' >/dev/null"

echo "[3/5] Sync repository contents to prod"
rsync -av \
  -e "${RSYNC_RSH}" \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.venv/' \
  --exclude '.venv_api/' \
  --exclude 'runtime/' \
  --exclude '.env.local' \
  --exclude 'data/' \
  --exclude 'logs/' \
  --exclude 'Purchases/' \
  --exclude 'test-results/' \
  --exclude 'app/static/uploads/' \
  --exclude '.superpowers/' \
  --exclude 'library.db' \
  "${ROOT_DIR}/" \
  "${PROD_SSH_TARGET}:${PROD_APP_ROOT}/"

ssh_exec "find '${PROD_APP_ROOT}/deploy/scripts' -maxdepth 1 -name '*.sh' -exec chmod +x {} + && chmod +x '${PROD_APP_ROOT}/scripts/run_api.sh'"

if [[ "${REMOTE_INSTALL_REQUIREMENTS}" == "1" ]]; then
  echo "[4/5] Install remote Python dependencies"
  ssh_exec "cd '${PROD_APP_ROOT}' && if [[ -x .venv/bin/python3 ]]; then .venv/bin/python3 -m pip install -r requirements.txt >/dev/null; else python3 -m pip install -r requirements.txt >/dev/null; fi"
else
  echo "[4/5] Skip remote dependency install"
fi

echo "[5/5] Restart prod app and verify health"
ssh_exec "launchctl bootout gui/\$(id -u)/${PROD_LAUNCHD_LABEL} >/dev/null 2>&1 || true; launchctl bootstrap gui/\$(id -u) \"\$HOME/Library/LaunchAgents/${PROD_LAUNCHD_LABEL}.plist\""
ssh_exec "for attempt in 1 2 3 4 5 6 7 8 9 10; do curl --fail --silent --show-error '${PROD_HEALTHCHECK_URL}' >/dev/null && exit 0; sleep 2; done; exit 1"

printf 'Deploy complete: branch=%s sha=%s target=%s app_root=%s\n' \
  "${RELEASE_BRANCH}" "${RELEASE_SHA}" "${PROD_SSH_TARGET}" "${PROD_APP_ROOT}"
