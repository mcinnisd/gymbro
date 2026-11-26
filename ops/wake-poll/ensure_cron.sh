#!/usr/bin/env bash
# Make sure cron is installed, running, and has the Gymbro crontab. Idempotent;
# safe to call from any routine or shell. Logs to cron-health.log only when it
# has to fix something.
set -euo pipefail
OPS="${GYMBRO_OPS_DIR:-/workspace/gymbro-ops}"
LOG="$OPS/cron-health.log"
ts="$(TZ=America/Detroit date +'%Y-%m-%d %H:%M:%S %Z')"

if ! command -v crontab >/dev/null; then
  sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cron
  echo "[$ts] installed cron package" >>"$LOG"
fi
if ! pgrep -x cron >/dev/null; then
  sudo /usr/sbin/cron
  echo "[$ts] cron daemon was not running; started it" >>"$LOG"
fi
if ! diff -q <(crontab -l 2>/dev/null) "$OPS/crontab.installed" >/dev/null; then
  crontab "$OPS/crontab.installed"
  echo "[$ts] crontab drifted or missing; reinstalled" >>"$LOG"
fi
