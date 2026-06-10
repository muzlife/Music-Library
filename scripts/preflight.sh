#!/usr/bin/env bash
# preflight.sh — lint + test 게이트. 배포 전 실행. 실패 시 비정상 종료(exit 1).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# Python 바이너리 해석
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "ERROR: python3 not found" >&2
  exit 1
fi

echo "=== preflight: ruff ==="
if ! "${PYTHON_BIN}" -m ruff check app/ tests/; then
  echo "FAIL: ruff lint 실패" >&2
  exit 1
fi
echo "OK: ruff"

echo ""
echo "=== preflight: pytest ==="
if ! "${PYTHON_BIN}" -m pytest --tb=short -q; then
  echo "FAIL: pytest 실패" >&2
  exit 1
fi
echo "OK: pytest"

echo ""
echo "=== preflight: ALL PASSED ==="
