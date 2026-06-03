#!/usr/bin/env bash
#───────────────────────────────────────────────────────────
# Read the existing prod .env file and generate a launchd
# plist with EnvironmentVariables, then install & reload.
#───────────────────────────────────────────────────────────
set -euo pipefail

PROD_DIR="${1:-/Users/__USER__/apps/__PROJECT_SLUG__-prod}"
ENV_FILE="${PROD_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: .env not found at ${ENV_FILE}" >&2
  exit 1
fi

# Build the EnvironmentVariables dict from .env
# Skip comments, empty lines, and known non-secret keys
ENV_XML=""
SKIP_KEYS="^(#|$)"
while IFS='=' read -r key value; do
  key="$(echo "${key}" | xargs)"
  [[ -z "${key}" ]] && continue
  [[ "${key}" == \#* ]] && continue
  value="$(echo "${value}" | sed 's/^"//;s/"$//')"
  ENV_XML="${ENV_XML}    <key>${key}</key>"$'\n'
  ENV_XML="${ENV_XML}    <string>${value}</string>"$'\n'
done < "${ENV_FILE}}

# Read existing plist and inject EnvironmentVariables
PLIST_SRC="${PROD_DIR}/runtime/plist/com.muzlife.library-prod.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.muzlife.library-prod.plist"

if [[ ! -f "${PLIST_SRC}" ]]; then
  echo "ERROR: plist template not found at ${PLIST_SRC}" >&2
  exit 1
fi

# Inject env vars after ProgramArguments
awk -v env_xml="${ENV_XML}" '
  /<\/array>/ && !injected {
    print "  <key>EnvironmentVariables</key>"
    print "  <dict>"
    print env_xml
    print "  </dict>"
    injected = 1
  }
  { print }
' "${PLIST_SRC}" > "${PLIST_DST}"

chmod 644 "${PLIST_DST}"
echo "→ Installed plist to ${PLIST_DST}"

echo "→ Reloading launchd..."
launchctl bootout "gui/$(id -u)/com.muzlife.library-prod" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}" 2>/dev/null || \
  launchctl load -w "${PLIST_DST}"

echo "✅  Prod plist deployed and loaded"
