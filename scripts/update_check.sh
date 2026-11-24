#!/usr/bin/env bash
# Fast-forward this checkout to origin/main. Refuses any other branch.
# Reinstalls only when a requirements file changed. Rolls back if health fails.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

report() {
  printf 'old_sha=%s new_sha=%s result=%s subjects=%s\n' "$1" "$2" "$3" "$4"
}

old="$(git rev-parse HEAD)"
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "main" ]]; then
  echo "update_check: on $branch; not checking out another branch"
  report "$old" "$old" up_to_date ""
  exit 0
fi

if ! git fetch origin main; then
  echo "update_check: git fetch origin main failed"
  report "$old" "$old" up_to_date ""
  exit 1
fi

remote="$(git rev-parse origin/main)"
if [[ "$old" == "$remote" ]]; then
  echo "update_check: already at origin/main"
  report "$old" "$old" up_to_date ""
  exit 0
fi
if ! git merge-base --is-ancestor HEAD origin/main; then
  echo "update_check: main has diverged from origin/main; not forcing"
  report "$old" "$old" up_to_date ""
  exit 0
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "update_check: working tree is dirty; not fast-forwarding"
  report "$old" "$old" up_to_date ""
  exit 0
fi

git merge --ff-only origin/main
new="$(git rev-parse HEAD)"
subjects="$(git log --reverse --format=%s "$old".."$new" | awk 'NR>1 { printf " | " } { printf "%s", $0 }')"
echo "update_check: pulled"
printf '%s\n' "$subjects" | sed 's/ | /\n/g'

rollback() {
  echo "update_check: rolling back to $old"
  git reset --hard "$old"
  "$ROOT/scripts/ensure_venv.sh" || true
  report "$old" "$old" rolled_back "$subjects"
  exit 0
}

if git diff --name-only "$old" "$new" | grep -q '^requirements'; then
  "$ROOT/scripts/ensure_venv.sh" || rollback
fi

py="${GYMBRO_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$py" ]] || py=python3
set +e
PYTHONPATH="$ROOT" "$py" -c "import app.mcp"
imp=$?
PYTHONPATH="$ROOT" "$py" -m app.garmin.cli status
st=$?
set -e
if [[ "$imp" -ne 0 || "$st" -ne 0 ]]; then
  echo "update_check: health check failed"
  rollback
fi
echo "update_check: health check passed"
report "$old" "$new" updated "$subjects"
