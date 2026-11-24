#!/usr/bin/env bash
# Idempotent Gymbro setup for a Grok Bot Linux box.
# Clones or updates the repo, creates .venv, installs requirements, and
# creates .env from .env.example when .env is absent. Never overwrites .env.
#
#   scripts/bootstrap.sh                 # ~/gymbro
#   scripts/bootstrap.sh /path/to/gymbro
#   GYMBRO_REPO_URL=https://... scripts/bootstrap.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: scripts/bootstrap.sh [target_dir]" >&2
  echo "Default target is ~/gymbro. Set GYMBRO_HOME or pass a directory." >&2
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

TARGET="${1:-${GYMBRO_HOME:-$HOME/gymbro}}"
case "$TARGET" in
  "~") TARGET="$HOME" ;;
  "~/"*) TARGET="$HOME/${TARGET:2}" ;;
esac
if [[ "$TARGET" != /* ]]; then
  TARGET="$PWD/$TARGET"
fi

abs_dir() {
  (cd "$1" && pwd)
}

repo_url="${GYMBRO_REPO_URL:-}"
if [[ -z "$repo_url" && -d "$SOURCE_ROOT/.git" ]]; then
  repo_url="$(git -C "$SOURCE_ROOT" remote get-url origin 2>/dev/null || true)"
fi

if [[ -d "$TARGET/.git" ]]; then
  echo "bootstrap: updating $(abs_dir "$TARGET")"
  git -C "$TARGET" fetch --prune origin
  if ! git -C "$TARGET" pull --ff-only; then
    echo "bootstrap: fast-forward failed; continuing with the existing checkout" >&2
  fi
elif [[ -d "$TARGET" ]] && [[ -n "$(ls -A "$TARGET" 2>/dev/null || true)" ]]; then
  if [[ -d "$SOURCE_ROOT/.git" ]] && [[ "$(abs_dir "$TARGET")" == "$(abs_dir "$SOURCE_ROOT")" ]]; then
    echo "bootstrap: using existing checkout $TARGET"
  else
    echo "bootstrap: $TARGET exists and is not a git checkout" >&2
    exit 1
  fi
else
  if [[ -z "$repo_url" ]]; then
    echo "bootstrap: set GYMBRO_REPO_URL to the git remote to clone into $TARGET" >&2
    exit 1
  fi
  echo "bootstrap: cloning into $TARGET"
  mkdir -p "$(dirname "$TARGET")"
  git clone "$repo_url" "$TARGET"
fi

"$TARGET/scripts/ensure_venv.sh"

if [[ ! -f "$TARGET/.env" ]]; then
  cp "$TARGET/.env.example" "$TARGET/.env"
  chmod 600 "$TARGET/.env"
  echo "bootstrap: created $TARGET/.env from .env.example"
else
  echo "bootstrap: left existing $TARGET/.env unchanged"
fi

cat <<EOF

Next steps (details: grokbot/skills/gymbro-coach/SKILL.md):
  1. Fill secrets in $TARGET/.env. Do not paste them into chat.
  2. Apply migrations/001_canonical_schema.sql, then the dated files in migrations/, on a new Supabase project. Skip migrations/schema.sql (it matches 001).
  3. Create the athlete and connect Garmin: $TARGET/scripts/create_athlete.sh
  4. Register the stdio MCP server (command, args, cwd are in the skill).
  5. Install the morning wake cron: $TARGET/scripts/install_cron.sh
EOF
