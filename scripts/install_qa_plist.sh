#!/usr/bin/env bash
#───────────────────────────────────────────────────────────
# Install the QA launchd plist with EnvironmentVariables
#───────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT_DIR}/runtime/plist/com.muzlife.library-qa.plist"
DST="${HOME}/Library/LaunchAgents/com.muzlife.library-qa.plist"

if [[ ! -f "${SRC}" ]]; then
  echo "ERROR: source plist not found: ${SRC}" >&2
  exit 1
fi

echo "→ Installing plist to ${DST}"
cp "${SRC}" "${DST}"
chmod 644 "${DST}"

echo "→ Unloading existing (if any)..."
launchctl bootout "gui/$(id -u)/com.muzlife.library-qa" 2>/dev/null || true
sleep 1

echo "→ Loading new plist..."
launchctl bootstrap "gui/$(id -u)" "${DST}" 2>/dev/null || \
  launchctl load -w "${DST}"

echo "→ Checking status..."
sleep 2
if pgrep -f 'uvicorn.*8100' >/dev/null 2>&1; then
  echo "✅  QA server is running on port 8100"
else
  echo "⚠️   QA server not running yet — check logs:"
  echo "    tail -20 ~/apps/hahahoho-qa/runtime/logs/launchd.qa.stderr.log"
fi
