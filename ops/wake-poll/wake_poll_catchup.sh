#!/usr/bin/env bash
# Runs the most recent 07:00–11:00 slot if cron never started it, e.g. after
# the box was frozen or cron was down. Quiet when there is nothing to do.
# Cron calls this every minute 07:00–11:59 and at @reboot.
set -euo pipefail

OPS="${GYMBRO_OPS_DIR:-/workspace/gymbro-ops}"
SLOT_DIR="$OPS/slots"
MARKER_DIR="$OPS/markers"
trigger="${1:-catchup}"

# WAKE_POLL_NOW ("YYYY-MM-DD HH:MM") is for tests.
read -r today h m < <(TZ=America/Detroit date -d "${WAKE_POLL_NOW:-now}" +'%F %H %M')
mins=$(( 10#$h * 60 + 10#$m ))
# Window: slots 07:00 through 11:00, catch-up allowed until 11:59.
(( mins >= 7 * 60 && mins < 12 * 60 )) || exit 0
# The slot minute itself belongs to cron's own entry.
if (( 10#$m % 15 == 0 && mins <= 11 * 60 )) && [[ "$trigger" == catchup ]]; then
  exit 0
fi
slot_min=$(( mins / 15 * 15 ))
(( slot_min > 11 * 60 )) && slot_min=$(( 11 * 60 ))
slot="$(printf '%02d:%02d' $(( slot_min / 60 )) $(( slot_min % 60 )))"

[[ -e "$MARKER_DIR/wake-up-$today" ]] && exit 0
[[ -e "$SLOT_DIR/$today/${slot/:/}.started" ]] && exit 0
exec "$OPS/wake_poll_cron.sh" --trigger "$trigger" --slot "$slot"
