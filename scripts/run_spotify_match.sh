#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -x .venv/bin/python3 ]]; then
  PYTHON_BIN=".venv/bin/python3"
else
  PYTHON_BIN="python3"
fi

exec "${PYTHON_BIN}" scripts/spotify_batch_match_daemon.py
