#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.local"

load_env_file() {
  local env_file="$1"
  local line key value

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" != *=* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"

    if [[ ! "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      continue
    fi
    # ── Skip if already set (e.g., from launchd EnvironmentVariables) ──
    if [[ -n "${!key:-}" ]]; then
      continue
    fi

    if [[ "${value}" =~ ^\".*\"$ || "${value}" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi

    printf -v "${key}" '%s' "${value}"
    export "${key}"
  done < "${env_file}"
}

resolve_runtime_path() {
  local raw_path="$1"
  if [[ -z "${raw_path}" ]]; then
    return 1
  fi
  case "${raw_path}" in
    /*) printf '%s\n' "${raw_path}" ;;
    *) printf '%s\n' "${ROOT_DIR}/${raw_path}" ;;
  esac
}

validate_runtime_role() {
  local root_name expected_port expected_db_path actual_db_path
  root_name="$(basename "${ROOT_DIR}")"
  case "${root_name}" in
    hahahoho-prod)
      expected_port="8000"
      expected_db_path="${ROOT_DIR}/runtime/data/library.db"
      ;;
    hahahoho-qa)
      expected_port="8100"
      expected_db_path="${ROOT_DIR}/runtime/data/library.db"
      ;;
    *)
      return 0
      ;;
  esac

  if [[ "${APP_PORT}" != "${expected_port}" ]]; then
    echo "APP_PORT must be ${expected_port} for ${root_name} (current: ${APP_PORT})" >&2
    exit 1
  fi

  if ! actual_db_path="$(resolve_runtime_path "${LIBRARY_DB_PATH:-}")"; then
    echo "LIBRARY_DB_PATH is required for ${root_name}" >&2
    exit 1
  fi

  if [[ "${actual_db_path}" != "${expected_db_path}" ]]; then
    echo "LIBRARY_DB_PATH must point to ${expected_db_path} for ${root_name} (current: ${actual_db_path})" >&2
    exit 1
  fi
}

if [[ -f "${ENV_FILE}" ]]; then
  load_env_file "${ENV_FILE}"
fi

cd "${ROOT_DIR}"

APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"

validate_runtime_role

if [[ "${RUN_API_VALIDATE_ONLY:-0}" == "1" ]]; then
  printf 'runtime validation ok\n'
  exit 0
fi

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
