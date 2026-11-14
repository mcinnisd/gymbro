#!/usr/bin/env bash
# Recreate the repo-local .venv when it is missing (Hephaestus resets wipe it)
# and install requirements.txt. Safe to re-run. Exits non-zero on failure.
#
# Usage (from the gymbro repo root, or via path):
#   scripts/ensure_venv.sh
#
# Then:
#   PYTHONPATH=. .venv/bin/python -m app.mcp
#   PYTHONPATH=. .venv/bin/python -m app.garmin.cli sync --user-id 2 --mode incremental

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"
REQ="${ROOT}/requirements.txt"
PYTHON="${PYTHON:-python3}"

if [[ ! -f "${REQ}" ]]; then
  echo "error: requirements.txt not found at ${REQ}" >&2
  exit 1
fi

if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "error: ${PYTHON} not found (set PYTHON= to a Python 3.12+ interpreter)" >&2
  exit 1
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "creating venv at ${VENV} (interpreter missing)"
  rm -rf "${VENV}"
  "${PYTHON}" -m venv "${VENV}"
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "error: venv python still missing at ${VENV}/bin/python" >&2
  exit 1
fi

"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/python" -m pip install -r "${REQ}"

echo "venv ready: ${VENV}/bin/python"
