# Garmin → Supabase auto-sync

Garmin Connect is the Tier-1 telemetry source. Sync writes `garmin_activities`,
`biometrics_daily`, `garmin_daily`, `garmin_sleep`, and (when activities exist)
`training_events`. Agent/MCP tools now read those tables.

This is **not** official Garmin OAuth. Credentials are Garmin email + password,
encrypted with `ENCRYPTION_KEY` and stored on the athlete row. Do not commit
`.env`, tokens, or passwords.

Authenticated MCP HTTP lives at `app/mcp/` (`POST /api/mcp` and `python -m app.mcp`).
See [`docs/mcp.md`](mcp.md). Verify tools on **localhost** (`127.0.0.1:5001` or
in-process CLI / pytest). Do not use Cloudflare quick tunnel / trycloudflare for
tests — it rate-limits at ~50 requests/hour. Those 429s are the tunnel, not Garmin
or empty-data logic. MCP binds `user_id` from the API token / API key; never invent one.

## How sync is supposed to run

| Path | When it fires | Notes |
| --- | --- | --- |
| `POST /garmin/connect` | Athlete links Garmin in the app | Starts an all-time backfill in a background thread |
| `POST /garmin/sync` and `POST /telemetry/sync` | Manual / Stats re-sync | Honors `force` / `days_back` / `mode` |
| Login + `POST /telemetry/sync-if-needed` | App open | Incremental if previously synced; **requires the Flask process to be running** |
| In-process APScheduler (`create_app` → `init_telemetry_scheduler`) | Every `TELEMETRY_SYNC_INTERVAL_HOURS` (default 6h) | Incremental (`mode=incremental`, 7-day window). Needs an always-on process |
| `POST /internal/jobs/telemetry-sync` | External cron / Cloud Scheduler | Durable when Cloud Run scales to zero. Requires `INTERNAL_JOB_TOKEN` |

## Environment (no secrets in git)

```env
ENCRYPTION_KEY=...          # must match the key used to encrypt stored Garmin passwords
ENABLE_TELEMETRY_SCHEDULER=true
TELEMETRY_SYNC_INTERVAL_HOURS=6
GYMBRO_GARMIN_SYNC_USER_IDS=2   # optional; scopes scheduler/CLI when several users have Garmin
```

## Manual / cron trigger

```bash
# Always-on local or tunneled Flask (scheduler starts with the app)
PYTHONPATH=. python app.py

# Cloud Run / scale-to-zero: ping the job (token is a header, not a query param)
curl -X POST "$API_URL/internal/jobs/telemetry-sync" \
  -H "X-Internal-Job-Token: $INTERNAL_JOB_TOKEN"

# CLI (uses stored encrypted credentials; does not print them)
PYTHONPATH=. python -m app.garmin.cli status
PYTHONPATH=. python -m app.garmin.cli sync --user-id 2 --mode incremental
PYTHONPATH=. python -m app.garmin.cli remirror-calendar --user-id 2
PYTHONPATH=. python -m app.garmin.cli remirror-biometrics --user-id 2
```

If `status` shows `garmin_connected: false`, reconnect Garmin in the Expo Stats
screen (`GarminModal` → `POST /garmin/connect`). If it shows `last_error` about
session/init, the stored password cannot be decrypted (`ENCRYPTION_KEY` mismatch)
or Garmin SSO rejected the login (password change, 2FA). Reconnect; do not paste
credentials into issues or chat.

After a successful `python -m app.garmin.cli sync`, live Supabase already allows
`created_by IN ('user','coach','agent','garmin','strava')` (migration
`20260916_training_events_created_by_garmin.sql` applied). Earlier activity
syncs that ran **before** that CHECK change left `training_events` empty even
when `garmin_activities` is populated. Remirror from rows already in Supabase
(no Garmin API, no passwords):

```bash
PYTHONPATH=. python -m app.garmin.cli remirror-calendar --user-id 2
PYTHONPATH=. python -m app.garmin.cli remirror-biometrics --user-id 2
PYTHONPATH=. python -m app.garmin.cli verify-tools --user-id 2 --days-wellness 30 --days-activities 90
```

If remirror errors with `column training_events.metrics does not exist` (42703),
the code retries without that column. Apply
`migrations/20260916_training_events_metrics.sql` when convenient so `metrics`
jsonb exists (canonical schema). Remirror stays idempotent via a
`[garmin_activity_id=…]` marker in `description`.

A later `sync --user-id 2 --force` also remirrors as it re-upserts activities.
Prefer `remirror-calendar` when `garmin_activities` is already current.

## Wellness remirror (`biometrics_daily`)

`get_wellness_metrics` and `get_readiness` read `biometrics_daily`, not
`garmin_daily` / `garmin_sleep`. Those raw tables can move ahead of the
athlete-facing table: sync upserts them in batches, and a failed
`biometrics_daily` upsert used to be logged and ignored.

Verified on the live project for user 2: every `garmin_daily.resting_hr` value
is a JSON number with a decimal (`48.0`, four characters). Days that had that
value and were written on the 2026-09-16 sync have no matching
`biometrics_daily` row. Days with a null resting heart rate from that same sync
do. `resting_hr` (and `hrv_ms`, `sleep_score`, `body_battery`) are integers.
Sending `48.0` makes PostgREST reject the row (`22P02`) while `garmin_daily` /
`garmin_sleep`, which store JSON, still commit. Sync now coerces those fields
to integers before upsert. If a day still fails, the user row is
`garmin_sync_status=error` instead of `synced` with an empty `garmin_last_sync_error`.

Catch up from rows already in Supabase (no Garmin API, no passwords):

```bash
PYTHONPATH=. python -m app.garmin.cli remirror-biometrics --user-id 2
PYTHONPATH=. python -m app.garmin.cli verify-tools --user-id 2 --days-wellness 30
```

Remirror is idempotent. It rebuilds each date from `garmin_daily` (resting heart
rate, stress, summed steps) and `garmin_sleep` (sleep score, hours, stages,
overnight HRV, respiration, end-of-sleep body battery). It does not null out
`vo2_max` or other fields those raw tables do not store. Duplicate
`(user_id, date)` rows are collapsed to the fullest row before upsert.

Run this locally with `SUPABASE_URL` and `SUPABASE_KEY` pointed at the project.
It does not call Garmin and does not need `ENCRYPTION_KEY`. Apply it from the
operator environment after merge; do not run it against production from a
cloud agent.

**User-scoped sync:** `garmin_activities.activity_id` used to be UNIQUE globally.
Syncing a second account (user 100) with the same Garmin workouts **moved** those
rows off user 2 (`on_conflict=activity_id` updates `user_id`). Apply
`migrations/20260916_garmin_activities_user_scoped.sql` (UNIQUE(user_id, activity_id)).
Always pass `--user-id 2`; if several users have Garmin, CLI refuses unless
`--all-users` or `GYMBRO_GARMIN_SYNC_USER_IDS=2`.

**Duplicate Garmin email:** several test users can store the same Garmin login.
Deep sync then fans the same account onto every id (activities landed on 100,
biometrics stayed on 2). CLI/scheduler keep **one user per Garmin email**
(allowlist, then lowest numeric id). `--user-id 100` is refused when it shares
an account with the canonical athlete. Logs and errors use user ids only — never
emails.

**Calendar event_type:** live CHECK is
`run|strength|rest|race|other|cross_train|ride|swim|walk|hike` (migration
`20260916_training_events_event_type_check.sql`). Garmin writers still emit only
`run|strength|rest|race|other`; unknown typeKeys (`hiking`, `cycling`,
`cross_train`, `resort_snowboarding`, …) map to `other` so the enum does not
grow for every Garmin activity. Onboarding may still write `cross_train`.

## Verify on localhost (do not use Cloudflare / trycloudflare)

trycloudflare rate-limits at ~50 requests/hour. That 429 is **not** this bug and
is **not** required for verification. The domain tools MCP calls are the same
Python functions tested below; `/api/mcp` is documented in [`docs/mcp.md`](mcp.md).

### 1. Regression tests (no server, no tunnel, no live Garmin)

```bash
MOCK_DB=true PYTHONPATH=. python -m pytest \
  tests/unit/test_activity_tools.py \
  tests/unit/test_scheduler_wiring.py \
  tests/unit/test_mcp_adapter.py \
  tests/unit/test_mcp_http.py \
  tests/unit/test_garmin_biometrics_mirror.py -v
```

These seed **fixture** Garmin rows in the in-memory mock DB only. They prove the
tools read `biometrics_daily` / `garmin_activities`. They do not write fake
athlete data to production Supabase.

### 2. In-process tool probe (same functions as MCP)

Binds `user_id` from Garmin-connected rows already in the database. Does not
invent an id. Empty counts are valid when those tables have no rows in-window.

```bash
PYTHONPATH=. python -m app.garmin.cli verify-tools
PYTHONPATH=. python -m app.garmin.cli verify-tools --days-wellness 7 --days-activities 14
```

### 3. Optional local Flask (127.0.0.1 only)

```bash
# Do NOT pass --tunnel / do not start cloudflared or trycloudflare
ENABLE_TELEMETRY_SCHEDULER=true PYTHONPATH=. python app.py
# listens on http://127.0.0.1:5001
```

Login, then call the JWT-bound MCP-equivalent routes (athlete id comes from the
token, never from a query parameter):

```bash
TOKEN=$(curl -s http://127.0.0.1:5001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<your-username>","password":"<your-password>"}' \
  | python -c "import sys,json; print(json.load(sys.stdin).get('access_token') or '')")

curl -s "http://127.0.0.1:5001/telemetry/tools/wellness-metrics?days=7" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://127.0.0.1:5001/telemetry/tools/recent-activities?days=14" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://127.0.0.1:5001/telemetry/tools/readiness" \
  -H "Authorization: Bearer $TOKEN"
```

`get_wellness_metrics` (7d) `records_count > 0` only if `biometrics_daily` has
rows in that window. `get_recent_activities` (14d) `count > 0` only if unified
Garmin/Strava/manual workouts exist. `get_readiness` returns `score: null` when
those windows are empty (it does not invent values; see [`docs/readiness.md`](readiness.md)).
`get_calendar_events` fills from `training_events` after activity sync or
`remirror-calendar`. `get_biomarkers(flagged_only)` is lab panels, not Garmin —
empty is expected until bloodwork is uploaded.

Do not commit `.env`, tokens, or curl transcripts that contain passwords.
