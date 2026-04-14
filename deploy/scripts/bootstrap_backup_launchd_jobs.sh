#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="${HOME}/Library/LaunchAgents"
MODE="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 1
      ;;
  esac
done

case "${MODE}" in
  all)
    LABELS=(
      "com.muzlife.backup-daily-db"
      "com.muzlife.backup-weekly-full"
      "com.muzlife.qa-sync-weekly"
    )
    ;;
  prod)
    LABELS=(
      "com.muzlife.backup-daily-db"
      "com.muzlife.backup-weekly-full"
    )
    ;;
  qa)
    LABELS=(
      "com.muzlife.qa-sync-weekly"
    )
    ;;
  *)
    echo "Unsupported mode: ${MODE}" >&2
    exit 1
    ;;
esac

for label in "${LABELS[@]}"; do
  plist_path="${DEST_DIR}/${label}.plist"
  if [[ ! -f "${plist_path}" ]]; then
    echo "Missing plist: ${plist_path}" >&2
    exit 1
  fi
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${plist_path}"
  launchctl kickstart -k "gui/$(id -u)/${label}"
done

cat <<EOF
Bootstrapped backup launchd jobs:
  ${DEST_DIR}/com.muzlife.backup-daily-db.plist
  ${DEST_DIR}/com.muzlife.backup-weekly-full.plist
  ${DEST_DIR}/com.muzlife.qa-sync-weekly.plist
EOF
