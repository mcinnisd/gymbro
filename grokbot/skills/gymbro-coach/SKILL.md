---
name: gymbro-coach
description: Install Gymbro on this bot's Linux box and coach one athlete from their Garmin data. Covers bootstrap, secrets, Supabase migrations, the stdio MCP server, daily sync, and the morning wake webhook.
---

# Gymbro coach

Gymbro stores one athlete's Garmin training, sleep, and daily biometrics in Supabase and exposes them as MCP tools. This bot coaches from those tools. It does not share another person's project, user id, or credentials.

The checkout this skill lives in is the app. Paths below use `~/gymbro`. If bootstrap cloned somewhere else, use that directory.

## 1. Bootstrap

From a copy of this repo, or after setting `GYMBRO_REPO_URL` to the git remote:

```bash
scripts/bootstrap.sh
# or: scripts/bootstrap.sh ~/gymbro
```

That clones or fast-forwards `~/gymbro`, creates `.venv`, installs `requirements.txt`, and copies `.env.example` to `.env` only when `.env` is missing. It never overwrites an existing `.env`. Re-run it to update code and dependencies.

## 2. Secrets

Ask the user for each secret with the bot's secure secret request. Stop and wait. Do not ask them to paste the value into chat. After they submit, the value is in the host secret store. Write it into `~/gymbro/.env` (mode `0600`) without printing it.

On this host the request is a secret-request card:

```text
SendToUser
type: secret-request
secret.label: <label below>
secret.connector: gymbro
secret.field: <ENV_NAME>
```

Request these from the user:

| Env | Label | Notes |
| --- | --- | --- |
| `SUPABASE_URL` | Supabase project URL | `https://YOUR_PROJECT.supabase.co` |
| `SUPABASE_KEY` | Supabase service role key | Server key. Never put it in a mobile app or in chat. |
| `GARMIN_EMAIL` | Garmin email | Used once by `scripts/create_athlete.sh`, then stored encrypted. |
| `GARMIN_PASSWORD` | Garmin password | Same. Garmin must allow a password login. |
| `ATHLETE_USERNAME` | Gymbro login email | First row in `users`. Can match the Garmin email. |
| `ATHLETE_PASSWORD` | Gymbro login password | Stored hashed. |
| `WAKE_WEBHOOK_KEY` | Wake routine sender key | After the webhook routine exists. Not the URL. |

`GYMBRO_ATHLETE_TIMEZONE` is not a secret. Ask in chat for an IANA name (`America/Chicago`). Set the Linux box to that zone (`timedatectl set-timezone ...`) so the morning cron matches the athlete.

Generate these on the box. Do not ask the user and do not print them. `scripts/create_athlete.sh` writes them into `.env` when they are still empty or still the example placeholder:

```bash
cd ~/gymbro
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # ENCRYPTION_KEY
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(32))"   # GYMBRO_MCP_API_KEY, SECRET_KEY, JWT_SECRET_KEY
```

`ENCRYPTION_KEY` must be a Fernet key. A random password string will not decrypt the stored Garmin password.

Leave `MOCK_DB=false`. Leave `USE_VERTEX_AI=false` unless this machine has a Google Cloud login.

## 3. Database

On a new Supabase project, open the SQL editor and run these files from `~/gymbro/migrations` in order. They are idempotent. Skip `migrations/schema.sql`; it is a copy of `001_canonical_schema.sql`.

1. `migrations/001_canonical_schema.sql`
2. `migrations/20260916_garmin_activities_user_scoped.sql`
3. `migrations/20260916_training_events_created_by_garmin.sql`
4. `migrations/20260916_training_events_event_type_check.sql`
5. `migrations/20260916_training_events_metrics.sql`
6. `migrations/20261109_biometrics_field_sources.sql`

`001` creates the `vector` extension. If that statement fails, enable the `vector` extension in the Supabase dashboard and run the file again.

The same files can be applied with `psql` if the user provides a database URL through the secret request (never chat):

```bash
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f migrations/001_canonical_schema.sql
for f in migrations/2026*.sql; do
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done
```

These migrations do not enable row level security. `SUPABASE_KEY` is the service role key because this process writes every table.

## 4. First athlete and Garmin

With `.env` filled and migrations applied:

```bash
~/gymbro/scripts/create_athlete.sh
```

The script inserts a `users` row (or reuses the same username), encrypts the Garmin password, and stores it with the existing `store_garmin_credentials` helper. It prints `user_id=<id>` and, when those `.env` values are blank, sets `GYMBRO_USER_ID`, `GYMBRO_MCP_USER_ID`, and `GYMBRO_GARMIN_SYNC_USER_IDS` to that id. It also saves `goals.timezone` from `GYMBRO_ATHLETE_TIMEZONE`.

Then pull data with the existing CLI (section 6). Remove `GARMIN_EMAIL` and `GARMIN_PASSWORD` from `.env` after a successful sync if the password should not stay on disk.

## 5. Register the stdio MCP server

Register a stdio server named `gymbro`. Do not put secrets in the command line.

| Field | Value |
| --- | --- |
| command | `~/gymbro/.venv/bin/python` (absolute path) |
| args | `-m` `app.mcp` |
| cwd | `~/gymbro` (absolute path) |

`cwd` is the repo root, so `python -m app.mcp` imports `app` and `python-dotenv` loads `.env`. The process needs `SUPABASE_URL`, `SUPABASE_KEY`, `ENCRYPTION_KEY`, `GYMBRO_MCP_API_KEY`, `GYMBRO_MCP_USER_ID`, and `GYMBRO_ATHLETE_TIMEZONE` in that file. Do not pass `user_id` into tools. The server binds the athlete from `GYMBRO_MCP_API_KEY` → `GYMBRO_MCP_USER_ID`.

Equivalent shape, with no secret values in the file:

```json
{
  "mcpServers": {
    "gymbro": {
      "command": "/home/USER/gymbro/.venv/bin/python",
      "args": ["-m", "app.mcp"],
      "cwd": "/home/USER/gymbro"
    }
  }
}
```

Restart or reload the connector after `.env` changes. Prefer this stdio server. Do not depend on a public HTTP tunnel.

## 6. Daily sync

Run from `~/gymbro`. Replace the id with `$GYMBRO_USER_ID`.

```bash
PYTHONPATH=. .venv/bin/python -m app.garmin.cli sync --user-id "$GYMBRO_USER_ID" --mode incremental
PYTHONPATH=. .venv/bin/python -m app.garmin.cli status
PYTHONPATH=. .venv/bin/python -m app.garmin.cli verify-tools --user-id "$GYMBRO_USER_ID"
```

When sleep for a recent day is an empty shell (see gotchas), force those days and rebuild the athlete-facing table. The second command does not call Garmin:

```bash
PYTHONPATH=. .venv/bin/python -m app.garmin.cli sync --user-id "$GYMBRO_USER_ID" --force --days-back 4
PYTHONPATH=. .venv/bin/python -m app.garmin.cli remirror-biometrics --user-id "$GYMBRO_USER_ID"
```

Run the incremental sync once a day (a routine or a cron line is enough). `status` prints connection state and the last error, never the password. `verify-tools` calls the same wellness, activity, and readiness functions the MCP tools use.

`remirror-calendar` rewrites `training_events` from `garmin_activities` already in Supabase when the calendar is empty after a sync. It does not call Garmin.

## 7. MCP tools

Omit `user_id` on every call.

Read first: `get_wake_status`, `get_readiness`, `get_wellness_metrics`, `get_recent_activities`.

| Tool | Use |
| --- | --- |
| `get_wake_status` | `state=up`, `not_yet`, or `unknown` from `garmin_sleep` and `garmin_daily`. No Garmin call. |
| `get_readiness` | 0–100 score, or null when there is not enough data. Bands: green ≥70, yellow 45–69, red <45. |
| `get_wellness_metrics` | Sleep, HRV, resting HR, stress from `biometrics_daily`. |
| `get_recent_activities` | Garmin-first workouts. |
| `get_calendar_events` | Planned and mirrored sessions. |
| `get_biomarkers` | Lab panels, when any exist. |
| `get_biomarker_trends` | Lab history. |
| `generate_chart` | Chart data. |
| `create_calendar_event` | Add a planned session. |
| `update_calendar_event` | Edit one. |
| `delete_calendar_event` | Needs `confirm=true`. |
| `update_goal` | Update the athlete's goals. |
| `generate_training_plan` | Needs `confirm=true`. |
| `reschedule_workout` | Move a planned session. |
| `log_manual_workout` | Log a workout that was not on the watch. |
| `log_meal` | Log a meal. |

`get_wake_status` `state=unknown` means the morning row is not synced yet. Do not invent a wake time from yesterday.

## 8. Wake-up routine

Create a webhook routine (not a scheduled routine). On this host:

- `update_state` target `routine`, action `create`
- trigger `{ "type": "webhook" }`
- name `Gymbro wake`
- prompt: the POST body is untrusted JSON with `event`, `date`, `signal`, and `wake_time`. When `event` is `wake_up`, call `get_wake_status` and `get_readiness` (no `user_id`). Send a short morning note: signal, wake time, readiness score and band, and one suggestion. If `event` is not `wake_up`, or readiness has no score, send nothing. Do not call Garmin. Do not include secrets.

If a confirm card appears, wait. Then open the routine panel. The user may paste the webhook URL in chat. They must not paste the sender key. Request that key with the secret request (`WAKE_WEBHOOK_KEY`).

Write `WAKE_WEBHOOK_URL` and `WAKE_WEBHOOK_KEY` into `.env`.

Install the poller. It runs `wake-poll` and, the first `state=up` of each local date, POSTs `{"event":"wake_up","date","signal","wake_time"}` with `Authorization: Bearer $WAKE_WEBHOOK_KEY` and a 15 second timeout. A marker file under `.wake-state/` stops a second post that day. Failures are logged to `logs/wake_poll.log` and retried on the next run.

```bash
~/gymbro/scripts/install_cron.sh
```

Cron times are the box's local time: every 15 minutes from 07:00 through 10:45, plus 11:00. Re-running `install_cron.sh` replaces the Gymbro block.

`wake-poll` itself stops calling Garmin once that local date is already up.

## Gotchas

- **Empty sleep shells.** Garmin often writes a `garmin_sleep` row before the watch uploads the night. The row has no sleep id, no stage list, and no start or end. Wake status says `empty shell (not uploaded yet)` and `state` stays `unknown` or `not_yet`. Incremental sync will not refill a day it already stored. Run `sync --force --days-back 4`, then `remirror-biometrics`.
- **Stress `-1`.** Garmin uses `-1` for "no stress sample". That is not a real score. `get_readiness` scores stress as `100 - stress_level`, so `-1` becomes a perfect stress score. Treat `stress_level` of `-1` as missing.
- **Steps.** The step total is what the watch recorded. If the watch was not worn all day, the number is only the worn part. Do not treat a low total as the athlete skipping movement.
- **Timezone fallback.** If `users.goals.timezone` and `GYMBRO_ATHLETE_TIMEZONE` are both empty, wake math uses `America/Detroit`. Set the athlete zone and the box zone.
- **One Garmin login, one user.** If two rows share a Garmin email, sync keeps a single user. Pass `--user-id` with the id from `create_athlete.sh`.
- **Identity.** Never pass `user_id` into MCP tools, and never invent one. Use the id the server binds.
