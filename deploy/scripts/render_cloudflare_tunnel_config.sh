#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/scripts/render_cloudflare_tunnel_config.sh <prod|qa> <tunnel_id> <output_path> [user_name]

Examples:
  ./deploy/scripts/render_cloudflare_tunnel_config.sh prod 1234 ~/.cloudflared/library-prod.yml
  ./deploy/scripts/render_cloudflare_tunnel_config.sh qa 5678 ~/.cloudflared/library-qa.yml myuser
EOF
}

ROLE="${1:-}"
TUNNEL_ID="${2:-}"
OUTPUT_PATH="${3:-}"
USER_NAME="${4:-$(id -un)}"

if [[ -z "${ROLE}" || -z "${TUNNEL_ID}" || -z "${OUTPUT_PATH}" ]]; then
  usage >&2
  exit 1
fi

case "${ROLE}" in
  prod)
    TEMPLATE="${ROOT_DIR}/deploy/templates/cloudflare/library-prod-config.yml"
    ;;
  qa)
    TEMPLATE="${ROOT_DIR}/deploy/templates/cloudflare/library-qa-config.yml"
    ;;
  *)
    echo "Unknown role: ${ROLE}" >&2
    usage >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "${OUTPUT_PATH}")"

sed \
  -e "s|__CLOUDFLARE_TUNNEL_ID__|${TUNNEL_ID}|g" \
  -e "s|__USER__|${USER_NAME}|g" \
  "${TEMPLATE}" > "${OUTPUT_PATH}"

echo "Rendered ${ROLE} Cloudflare Tunnel config to ${OUTPUT_PATH}"
