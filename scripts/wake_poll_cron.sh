#!/usr/bin/env bash
# Poll Garmin for this morning and, the first time state=up on this local
# date, POST a wake event. Intended for cron every 15 minutes from 07:00
# through 11:00 in the box's local timezone (see scripts/install_cron.sh).
#
#   python -m app.garmin.cli wake-poll --user-id $GYMBRO_USER_ID
#
# When WAKE_WEBHOOK_URL is set, the body is
#   {"event":"wake_up","date","signal","wake_time"}
# with header Authorization: Bearer $WAKE_WEBHOOK_KEY and a 15s timeout.
# A marker file records a successful post so later polls the same local
# date do not send again. Webhook failures are logged and retried next run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/scripts/load_dotenv.sh"
gymbro_load_dotenv "$ROOT/.env"

LOG_DIR="${GYMBRO_LOG_DIR:-$ROOT/logs}"
STATE_DIR="${GYMBRO_STATE_DIR:-$ROOT/.wake-state}"
mkdir -p "$LOG_DIR" "$STATE_DIR"
LOG_FILE="$LOG_DIR/wake_poll.log"
LOCK_FILE="$STATE_DIR/wake_poll.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') wake-poll already running" >>"$LOG_FILE"
  exit 0
fi

if [[ -z "${GYMBRO_USER_ID:-}" ]]; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') wake-poll: GYMBRO_USER_ID is not set" >>"$LOG_FILE"
  exit 1
fi

if [[ -n "${GYMBRO_PYTHON:-}" ]]; then
  PYTHON="$GYMBRO_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

set +e
OUTPUT="$(PYTHONPATH="$ROOT" "$PYTHON" -m app.garmin.cli wake-poll --user-id "$GYMBRO_USER_ID" 2>&1)"
EXIT=$?
set -e

{
  echo "----- $(date '+%Y-%m-%dT%H:%M:%S%z') exit=$EXIT"
  printf '%s\n' "$OUTPUT"
} >>"$LOG_FILE"

field() {
  local key="$1"
  printf '%s\n' "$OUTPUT" | awk -v key="$key" '
    {
      for (i = 1; i <= NF; i++) {
        eq = index($i, "=")
        if (eq > 1 && substr($i, 1, eq - 1) == key) {
          print substr($i, eq + 1)
        }
      }
    }
  ' | tail -n 1
}

STATE="$(field state)"
if [[ "$STATE" != "up" ]]; then
  exit "$EXIT"
fi

# Box-local calendar date. Set the machine timezone to the athlete's zone.
TODAY="$(date +%F)"
MARKER="$STATE_DIR/wake_up_${TODAY}"
if [[ -f "$MARKER" ]]; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') state=up already sent for $TODAY" >>"$LOG_FILE"
  exit 0
fi

if [[ -z "${WAKE_WEBHOOK_URL:-}" ]]; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') state=up webhook skipped: WAKE_WEBHOOK_URL is unset" >>"$LOG_FILE"
  exit 0
fi
if [[ -z "${WAKE_WEBHOOK_KEY:-}" ]]; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') state=up webhook skipped: WAKE_WEBHOOK_KEY is unset" >>"$LOG_FILE"
  exit 0
fi

DATE_VALUE="$(field sleep_date)"
SIGNAL="$(field signal)"
WAKE_TIME="$(field wake_time)"
if [[ -z "$DATE_VALUE" ]]; then
  DATE_VALUE="$TODAY"
fi

PAYLOAD="$(printf '{"event":"wake_up","date":"%s","signal":"%s","wake_time":"%s"}' \
  "$DATE_VALUE" "$SIGNAL" "$WAKE_TIME")"

set +e
HTTP_CODE="$(
  curl --silent --show-error --max-time 15 \
    -o "$LOG_DIR/wake_webhook_last_body.txt" \
    -w '%{http_code}' \
    -X POST "$WAKE_WEBHOOK_URL" \
    -H "Authorization: Bearer ${WAKE_WEBHOOK_KEY}" \
    -H "Content-Type: application/json" \
    --data "$PAYLOAD" \
    2>>"$LOG_FILE"
)"
CURL_RC=$?
set -e

if [[ "$CURL_RC" -ne 0 ]]; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') webhook failed curl=$CURL_RC (will retry)" >>"$LOG_FILE"
  exit 0
fi
echo "$(date '+%Y-%m-%dT%H:%M:%S%z') webhook http=$HTTP_CODE" >>"$LOG_FILE"
case "$HTTP_CODE" in
  2*)
    printf '%s\n' "$PAYLOAD" >"$MARKER"
    chmod 600 "$MARKER" 2>/dev/null || true
    ;;
  *)
    echo "$(date '+%Y-%m-%dT%H:%M:%S%z') webhook not marked sent (will retry)" >>"$LOG_FILE"
    ;;
esac
exit 0
