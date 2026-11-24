#!/usr/bin/env bash
# Install cron if it is missing, then add the wake-poll lines for this user.
# Schedule is the machine's local time: every 15 minutes from 07:00 through
# 10:45, plus 11:00. Set the box timezone to the athlete's IANA zone first.
# Re-running replaces the previous gymbro block and does not duplicate lines.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLL="$ROOT/scripts/wake_poll_cron.sh"
chmod +x "$POLL" "$ROOT/scripts/load_dotenv.sh" "$ROOT/scripts/bootstrap.sh" \
  "$ROOT/scripts/ensure_venv.sh" "$ROOT/scripts/create_athlete.sh"

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "install_cron: need root (or sudo) to install the cron package" >&2
    return 1
  fi
}

if ! command -v crontab >/dev/null 2>&1; then
  echo "install_cron: crontab is missing; installing cron"
  if command -v apt-get >/dev/null 2>&1; then
    as_root env DEBIAN_FRONTEND=noninteractive apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y cron
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf install -y cronie
  elif command -v yum >/dev/null 2>&1; then
    as_root yum install -y cronie
  elif command -v apk >/dev/null 2>&1; then
    as_root apk add --no-cache cronie
  else
    echo "install_cron: install cron (crontab) with the system package manager, then rerun" >&2
    exit 1
  fi
fi

if ! command -v crontab >/dev/null 2>&1; then
  echo "install_cron: crontab is still not on PATH" >&2
  exit 1
fi

if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
  as_root systemctl enable --now cron >/dev/null 2>&1 \
    || as_root systemctl enable --now crond >/dev/null 2>&1 \
    || echo "install_cron: could not start the cron service; the crontab is still installed" >&2
elif command -v service >/dev/null 2>&1; then
  as_root service cron start >/dev/null 2>&1 \
    || as_root service crond start >/dev/null 2>&1 \
    || true
fi

BEGIN="# BEGIN gymbro wake-poll"
END="# END gymbro wake-poll"
BLOCK="$(cat <<EOF
$BEGIN
# Gymbro wake poll. Times are this machine's local timezone.
*/15 7-10 * * * $POLL
0 11 * * * $POLL
$END
EOF
)"

existing="$(crontab -l 2>/dev/null || true)"
stripped="$(printf '%s\n' "$existing" | awk -v begin="$BEGIN" -v end="$END" '
  $0 == begin { skip = 1; next }
  $0 == end { skip = 0; next }
  skip != 1 { print }
')"

{
  if [[ -n "$stripped" ]]; then
    printf '%s\n' "$stripped"
  fi
  printf '%s\n' "$BLOCK"
} | crontab -

echo "install_cron: installed for $(id -un). Local times: 07:00-10:45 every 15 minutes, plus 11:00."
echo "install_cron: $POLL"
crontab -l | awk -v begin="$BEGIN" -v end="$END" '$0 == begin, $0 == end'
