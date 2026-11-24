#!/usr/bin/env bash
# Create the first Gymbro user (or reuse the same username) and store Garmin
# credentials encrypted with ENCRYPTION_KEY.
# Reuses the users table, encrypt_data, and store_garmin_credentials.
# Does not print passwords, keys, or the Garmin email.
#
# Reads ATHLETE_USERNAME, ATHLETE_PASSWORD, GARMIN_EMAIL, GARMIN_PASSWORD,
# and GYMBRO_ATHLETE_TIMEZONE from the environment or from .env. Prompts
# without echo for passwords when a value is missing and stdin is a tty.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/scripts/load_dotenv.sh"
umask 077

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "create_athlete: missing $ROOT/.venv. Run scripts/bootstrap.sh first." >&2
  exit 1
fi

gymbro_load_dotenv "$ROOT/.env"

clear_placeholder() {
  local var="$1"
  case "${!var:-}" in
    your-garmin-password|replace-with-a-password|athlete@example.com|your_supabase_service_role_key|https://YOUR_PROJECT.supabase.co|replace-with-fernet-key|replace-with-a-long-random-string)
      unset "$var"
      ;;
  esac
}
clear_placeholder SUPABASE_URL
clear_placeholder SUPABASE_KEY
clear_placeholder ENCRYPTION_KEY
clear_placeholder ATHLETE_USERNAME
clear_placeholder ATHLETE_PASSWORD
clear_placeholder GARMIN_EMAIL
clear_placeholder GARMIN_PASSWORD
clear_placeholder GYMBRO_MCP_API_KEY
clear_placeholder SECRET_KEY
clear_placeholder JWT_SECRET_KEY

upsert_env() {
  local key="$1" value="$2"
  [[ -n "$value" && -f "$ROOT/.env" ]] || return 0
  GYMBRO_ENV_FILE="$ROOT/.env" GYMBRO_ENV_KEY="$key" GYMBRO_ENV_VALUE="$value" \
    "$ROOT/.venv/bin/python" - <<'PY'
import os
path = os.environ["GYMBRO_ENV_FILE"]
key = os.environ["GYMBRO_ENV_KEY"]
value = os.environ["GYMBRO_ENV_VALUE"]
prefix = key + "="
lines = open(path).read().splitlines()
found = False
out = []
for line in lines:
    if line.startswith(prefix):
        out.append(prefix + value)
        found = True
    else:
        out.append(line)
if not found:
    out.append(prefix + value)
open(path, "w").write("\n".join(out) + "\n")
os.chmod(path, 0o600)
PY
}

env_value() {
  local key="$1"
  if [[ -f "$ROOT/.env" ]] && grep -q "^${key}=" "$ROOT/.env"; then
    grep "^${key}=" "$ROOT/.env" | tail -n 1 | cut -d= -f2-
  fi
}

blank_secret() {
  case "$1" in
    ""|replace-with-a-long-random-string|replace-with-fernet-key|your_secret_key|your_jwt_secret_key)
      return 0
      ;;
  esac
  return 1
}

fill_generated() {
  local key="$1" py="$2" current generated
  current="$(env_value "$key")"
  if blank_secret "${!key:-}"; then
    if blank_secret "$current"; then
      generated="$("$ROOT/.venv/bin/python" -c "$py")"
      export "$key=$generated"
    else
      export "$key=$current"
      return 0
    fi
  else
    generated="${!key}"
  fi
  if [[ "$current" != "$generated" ]]; then
    upsert_env "$key" "$generated"
    echo "create_athlete: wrote $key into .env (value not shown)"
  fi
}

fill_generated ENCRYPTION_KEY "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
fill_generated GYMBRO_MCP_API_KEY "import secrets; print(secrets.token_urlsafe(32))"
fill_generated SECRET_KEY "import secrets; print(secrets.token_urlsafe(32))"
fill_generated JWT_SECRET_KEY "import secrets; print(secrets.token_urlsafe(32))"

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_KEY:-}" ]]; then
  echo "create_athlete: set SUPABASE_URL and SUPABASE_KEY in .env" >&2
  exit 1
fi

prompt() {
  local var="$1" label="$2" secret="$3" required="$4" value
  if [[ -n "${!var:-}" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    if [[ "$required" == "1" ]]; then
      echo "create_athlete: set $var (no tty to prompt)" >&2
      exit 1
    fi
    return 0
  fi
  if [[ "$secret" == "1" ]]; then
    read -r -s -p "$label: " value
    echo
  else
    read -r -p "$label: " value
  fi
  printf -v "$var" '%s' "$value"
  export "$var"
}

prompt ATHLETE_USERNAME "Athlete username (email)" 0 1
prompt ATHLETE_PASSWORD "Athlete password (blank only if this username already exists)" 1 0
prompt GARMIN_EMAIL "Garmin email" 0 1
prompt GARMIN_PASSWORD "Garmin password" 1 1
prompt GYMBRO_ATHLETE_TIMEZONE "IANA timezone (example: America/New_York)" 0 1

export ENABLE_TELEMETRY_SCHEDULER=false
export GYMBRO_MCP_HTTP_DISABLE=true
export PYTHONPATH="$ROOT"

result="$(
  "$ROOT/.venv/bin/python" - <<'PY'
import os
import sys
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from app.garmin.sync import store_garmin_credentials
from app.supabase_client import supabase
from app.utils.encryption import encrypt_data

username = os.environ["ATHLETE_USERNAME"].strip()
password = os.environ.get("ATHLETE_PASSWORD", "")
garmin_email = os.environ["GARMIN_EMAIL"].strip()
garmin_password = os.environ["GARMIN_PASSWORD"]
tz = os.environ.get("GYMBRO_ATHLETE_TIMEZONE", "").strip()
enc = os.environ["ENCRYPTION_KEY"].strip()

if supabase is None:
    sys.exit("create_athlete: supabase client is not configured")

existing = (
    supabase.table("users")
    .select("id,goals")
    .eq("username", username)
    .limit(1)
    .execute()
)
rows = existing.data or []
if rows:
    user_id = rows[0]["id"]
    created = False
    if tz:
        goals = dict(rows[0].get("goals") or {})
        goals["timezone"] = tz
        supabase.table("users").update({"goals": goals}).eq("id", user_id).execute()
else:
    if not password:
        sys.exit("create_athlete: ATHLETE_PASSWORD is required for a new user")
    goals = {"timezone": tz} if tz else {}
    inserted = (
        supabase.table("users")
        .insert(
            {
                "username": username,
                "password": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "goals": goals,
            }
        )
        .execute()
    )
    if not inserted.data:
        sys.exit("create_athlete: user insert returned no row")
    user_id = inserted.data[0]["id"]
    created = True

store_garmin_credentials(
    str(user_id),
    garmin_email,
    encrypt_data(garmin_password, key=enc),
)
print(f"user_id={user_id} created={'true' if created else 'false'} garmin_connected=true")
PY
)"
printf '%s\n' "$result"

user_id="$(printf '%s\n' "$result" | sed -n 's/^user_id=\([^ ]*\).*/\1/p' | tail -n 1)"
if [[ -z "$user_id" ]]; then
  echo "create_athlete: did not get a user id" >&2
  exit 1
fi

set_id() {
  local key="$1" current
  current="$(env_value "$key")"
  case "$current" in
    ""|your_user_id) upsert_env "$key" "$user_id" ;;
  esac
}
set_id GYMBRO_USER_ID
set_id GYMBRO_MCP_USER_ID
set_id GYMBRO_GARMIN_SYNC_USER_IDS
if [[ -n "${GYMBRO_ATHLETE_TIMEZONE:-}" && "$(env_value GYMBRO_ATHLETE_TIMEZONE)" != "$GYMBRO_ATHLETE_TIMEZONE" ]]; then
  upsert_env GYMBRO_ATHLETE_TIMEZONE "$GYMBRO_ATHLETE_TIMEZONE"
fi

cat <<EOF
Garmin password is stored encrypted on user ${user_id}.
You can remove GARMIN_EMAIL and GARMIN_PASSWORD from .env.
Next:
  cd $ROOT
  PYTHONPATH=. .venv/bin/python -m app.garmin.cli sync --user-id ${user_id} --mode incremental
  PYTHONPATH=. .venv/bin/python -m app.garmin.cli status
EOF
