#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.local"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

cd "${ROOT_DIR}"

APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"

if [[ -x "${ROOT_DIR}/.venv/bin/python3" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
else
  if [[ -f "${ROOT_DIR}/.venv/pyvenv.cfg" ]]; then
    VENV_HOME="$(/usr/bin/grep -E '^home = ' "${ROOT_DIR}/.venv/pyvenv.cfg" | /usr/bin/head -n 1 | /usr/bin/sed 's/^home = //')"
    if [[ -n "${VENV_HOME}" && -x "${VENV_HOME}/python3" ]]; then
      PYTHON_BIN="${VENV_HOME}/python3"
    fi
  fi

  if [[ -z "${PYTHON_BIN:-}" ]]; then
    if [[ -x "/opt/homebrew/Caskroom/miniforge/base/bin/python3" ]]; then
      PYTHON_BIN="/opt/homebrew/Caskroom/miniforge/base/bin/python3"
    elif [[ -x "/opt/homebrew/bin/python3" ]]; then
      PYTHON_BIN="/opt/homebrew/bin/python3"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3)"
    else
      echo "python3 not found. Activate venv or install dependencies." >&2
      exit 1
    fi
  fi
fi

if [[ "${APP_RELOAD:-0}" == "1" ]]; then
  exec "${PYTHON_BIN}" -m uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" --reload
fi

exec "${PYTHON_BIN}" -m uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}"
