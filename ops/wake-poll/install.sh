#!/usr/bin/env bash
# Copy these scripts into /workspace/gymbro-ops and (re)install the crontab.
# Run from a pulled /workspace/gymbro-prod. Backs up what it replaces.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS="${GYMBRO_OPS_DIR:-/workspace/gymbro-ops}"
bak="$OPS/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$bak"
for f in wake_poll_cron.sh wake_poll_catchup.sh ensure_cron.sh crontab.installed; do
  [[ -e "$OPS/$f" ]] && cp -p "$OPS/$f" "$bak/"
done
install -m 755 "$SRC/wake_poll_cron.sh" "$SRC/wake_poll_catchup.sh" "$SRC/ensure_cron.sh" "$OPS/"
install -m 644 "$SRC/crontab" "$OPS/crontab.installed"
"$OPS/ensure_cron.sh"
crontab -l
echo "installed; previous files in $bak"
