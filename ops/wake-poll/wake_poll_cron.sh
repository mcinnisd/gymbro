#!/usr/bin/env bash
# Production wake poll for Chiron. Runs wake-poll for users.id=2 from
# /workspace/gymbro-prod and, at most once per local sleep date, POSTs a
# wake_up event to CHIRON_WAKE_WEBHOOK_URL when that result is state=up.
#
# Every invocation logs a START line with its 15-minute slot before anything
# else, and an END line with the exit code, so a skipped slot shows up as a
# missing START. wake_poll_catchup.sh re-runs a slot cron missed. See
# ops/wake-poll/README.md. Usage:
#   wake_poll_cron.sh [--trigger cron|catchup|manual] [--slot HH:MM]
set -euo pipefail

ROOT="${GYMBRO_PROD_ROOT:-/workspace/gymbro-prod}"
OPS="${GYMBRO_OPS_DIR:-/workspace/gymbro-ops}"
LOG="$OPS/wake-poll.log"
LOCK="$OPS/wake_poll_cron.lock"
ENV_FILE="$OPS/wake.env"
MARKER_DIR="$OPS/markers"
SLOT_DIR="$OPS/slots"
USER_ID=2

trigger=manual
slot=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --trigger) trigger="$2"; shift 2 ;;
    --slot) slot="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$MARKER_DIR" "$OPS" "$SLOT_DIR"
ts="$(TZ=America/Detroit date +'%Y-%m-%d %H:%M:%S %Z')"
today="$(TZ=America/Detroit date +%F)"
if [[ -z "$slot" ]]; then
  # Floor to the 15-minute slot this run belongs to.
  read -r h m < <(TZ=America/Detroit date +'%H %M')
  slot="$(printf '%02d:%02d' "$((10#$h))" "$(( (10#$m / 15) * 15 ))")"
fi
slot_key="$SLOT_DIR/$today/${slot/:/}"
mkdir -p "$SLOT_DIR/$today"

echo "[$ts] START slot=$today $slot trigger=$trigger pid=$$" >>"$LOG"
# A paused box does not advance its boot clock, so btime moves later by the
# time it was frozen. Log the jump so missed slots have an explanation.
btime="$(awk '/^btime/{print $2}' /proc/stat 2>/dev/null || true)"
if [[ -n "$btime" && -f "$OPS/.last_btime" ]]; then
  prev="$(cat "$OPS/.last_btime" 2>/dev/null || echo "$btime")"
  if [[ "$prev" =~ ^[0-9]+$ ]] && (( btime - prev > 120 )); then
    echo "[$ts] box was frozen ~$(( (btime - prev) / 60 )) min since the previous run" >>"$LOG"
  fi
fi
[[ -n "$btime" ]] && echo "$btime" >"$OPS/.last_btime"
: >"$slot_key.started"

finish() {
  local rc="${1:-$?}"
  echo "$rc" >"$slot_key.done"
  echo "[$(TZ=America/Detroit date +'%Y-%m-%d %H:%M:%S %Z')] END slot=$today $slot trigger=$trigger exit=$rc" >>"$LOG"
}
trap 'finish $?' EXIT

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$ts] skipped: another poll is running" >>"$LOG"
  exit 0
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "[$ts] error: missing $ROOT/.venv/bin/python" >>"$LOG"
  exit 1
fi
if [[ ! -f "$ROOT/.env" ]]; then
  echo "[$ts] error: missing $ROOT/.env" >>"$LOG"
  exit 1
fi

set -a
# Prod secrets for Garmin decrypt + Supabase. Do not echo.
# shellcheck disable=SC1091
source "$ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1091
  source "$ENV_FILE"
fi
set +a

tmp_out="$(mktemp)"
tmp_err="$(mktemp)"
tmp_vars="$(mktemp)"
cleanup() { rm -f "$tmp_out" "$tmp_err" "$tmp_vars"; }
trap 'rc=$?; cleanup; finish "$rc"' EXIT

set +e
(
  cd "$ROOT"
  PYTHONPATH=. .venv/bin/python -m app.garmin.cli wake-poll --user-id "$USER_ID" --json
) >"$tmp_out" 2>"$tmp_err"
rc=$?
set -e

{
  echo "[$ts] exit=$rc"
  if [[ -s "$tmp_err" ]]; then
    # Flask limiter warning is noise; keep anything else.
    grep -v 'flask_limiter' "$tmp_err" | sed 's/^/  stderr: /' || true
  fi
  sed 's/^/  /' "$tmp_out"
} >>"$LOG"

if [[ "$rc" -ne 0 ]]; then
  exit "$rc"
fi

# Parse the JSON object from stdout (ignore any leading non-JSON lines).
"$ROOT/.venv/bin/python" - "$tmp_out" "$tmp_vars" <<'PY'
import json, shlex, sys
from pathlib import Path
raw = Path(sys.argv[1]).read_text()
start = raw.find("{")
end = raw.rfind("}")
if start < 0 or end < start:
    raise SystemExit("no JSON in wake-poll output")
data = json.loads(raw[start:end + 1])

def emit(key, value):
    if value is None:
        value = ""
    return f"{key}={shlex.quote(str(value))}"

Path(sys.argv[2]).write_text("\n".join([
    emit("WAKE_STATE", data.get("state") or ""),
    emit("WAKE_SIGNAL", data.get("signal") or ""),
    emit("WAKE_TIME", data.get("wake_time") or ""),
    emit("WAKE_DATE", data.get("sleep_date") or ""),
]) + "\n")
PY
# shellcheck disable=SC1090
source "$tmp_vars"

if [[ "${WAKE_STATE:-}" != "up" ]]; then
  exit 0
fi

day="${WAKE_DATE:-}"
if [[ -z "$day" ]]; then
  day="$(TZ=America/Detroit date +%F)"
fi
marker="$MARKER_DIR/wake-up-$day"

if [[ -e "$marker" ]]; then
  echo "[$ts] already notified for $day (marker exists)" >>"$LOG"
  exit 0
fi

url="${CHIRON_WAKE_WEBHOOK_URL:-}"
key="${CHIRON_WAKE_WEBHOOK_KEY:-}"
if [[ -z "$url" ]]; then
  echo "[$ts] state=up date=$day; webhook unset, skipping POST" >>"$LOG"
  exit 0
fi

payload="$(
  WAKE_DATE="$day" WAKE_SIGNAL="${WAKE_SIGNAL:-}" WAKE_TIME="${WAKE_TIME:-}" \
  "$ROOT/.venv/bin/python" - <<'PY'
import json, os
print(json.dumps({
    "event": "wake_up",
    "date": os.environ.get("WAKE_DATE") or "",
    "signal": os.environ.get("WAKE_SIGNAL") or "",
    "wake_time": os.environ.get("WAKE_TIME") or "",
}))
PY
)"

http_code="$(
  curl -sS -o /tmp/wake-webhook-body.txt -w '%{http_code}' \
    -X POST "$url" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $key" \
    --max-time 15 \
    --data "$payload"
)" || {
  echo "[$ts] webhook POST failed to start for $day" >>"$LOG"
  exit 1
}

if [[ "$http_code" != 200 && "$http_code" != 201 && "$http_code" != 202 && "$http_code" != 204 ]]; then
  echo "[$ts] webhook POST failed date=$day http=$http_code" >>"$LOG"
  exit 1
fi

printf '%s\n' "$ts" >"$marker"
echo "[$ts] posted wake_up date=$day signal=${WAKE_SIGNAL:-} wake_time=${WAKE_TIME:-} http=$http_code" >>"$LOG"
exit 0
