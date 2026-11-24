#!/usr/bin/env bash
# Create .venv if needed and install requirements.txt. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ensure_venv: python3 is not on PATH" >&2
  exit 1
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "ensure_venv: need root (or sudo) to install python3-venv" >&2
    return 1
  fi
}

install_venv_pkg() {
  echo "ensure_venv: installing python3-venv"
  if command -v apt-get >/dev/null 2>&1; then
    as_root env DEBIAN_FRONTEND=noninteractive apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf install -y python3
  elif command -v yum >/dev/null 2>&1; then
    as_root yum install -y python3
  elif command -v apk >/dev/null 2>&1; then
    as_root apk add --no-cache py3-virtualenv
  else
    echo "ensure_venv: install python3-venv with the system package manager, then rerun" >&2
    return 1
  fi
}

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  rm -rf "$ROOT/.venv"
  echo "ensure_venv: creating $ROOT/.venv"
  if ! "$PY" -m venv "$ROOT/.venv"; then
    install_venv_pkg
    rm -rf "$ROOT/.venv"
    "$PY" -m venv "$ROOT/.venv"
  fi
else
  echo "ensure_venv: using existing $ROOT/.venv"
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT/requirements.txt"
echo "ensure_venv: requirements installed"
