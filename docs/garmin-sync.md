# Garmin → Supabase auto-sync

Garmin Connect is the Tier-1 telemetry source. Sync writes `garmin_activities`,
`biometrics_daily`, `garmin_daily`, `garmin_sleep`, and (when activities exist)
`training_events`. Agent/MCP tools now read those tables.

This is **not** official Garmin OAuth. Credentials are Garmin email + password,
encrypted with `ENCRYPTION_KEY` and stored on the athlete row. Do not commit
`.env`, tokens, or passwords.

`app/mcp/` is not on `main` yet (ADR-0003). Verify tools on **localhost**
(`127.0.0.1:5001` or in-process CLI / pytest). Do not use Cloudflare quick
tunnel / trycloudflare for tests — it rate-limits at ~50 requests/hour. Those
429s are the tunnel, not Garmin or empty-data logic. MCP binds `user_id` from
the API token; never invent one.

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
INTERNAL_JOB_TOKEN=...      # optional; enables the cron HTTP seam
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
PYTHONPATH=. python -m app.garmin.cli sync --mode incremental
```

If `status` shows `garmin_connected: false`, reconnect Garmin in the Expo Stats
screen (`GarminModal` → `POST /garmin/connect`). If it shows `last_error` about
session/init, the stored password cannot be decrypted (`ENCRYPTION_KEY` mismatch)
or Garmin SSO rejected the login (password change, 2FA). Reconnect; do not paste
credentials into issues or chat.

After a successful `python -m app.garmin.cli sync`, apply
`migrations/20260916_training_events_created_by_garmin.sql` once on the live
Supabase project (SQL editor) so `created_by='garmin'` is allowed on
`training_events`. Until that runs, activity rows land in `garmin_activities`
but calendar mirroring fails with `training_events_created_by_check`.

## Verify on localhost (do not use Cloudflare / trycloudflare)

trycloudflare rate-limits at ~50 requests/hour. That 429 is **not** this bug and
is **not** required for verification. `app/mcp/` is not on `main` (ADR-0003);
the domain tools MCP would call are the same Python functions tested below.

### 1. Regression tests (no server, no tunnel, no live Garmin)

```bash
MOCK_DB=true PYTHONPATH=. python -m pytest \
  tests/unit/test_activity_tools.py \
  tests/unit/test_scheduler_wiring.py -v
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
```

`get_wellness_metrics` (7d) `records_count > 0` only if `biometrics_daily` has
rows in that window. `get_recent_activities` (14d) `count > 0` only if unified
Garmin/Strava/manual workouts exist. `get_calendar_events` fills from
`training_events` after activity sync. `get_biomarkers(flagged_only)` is lab
panels, not Garmin — empty is expected until bloodwork is uploaded.

Do not commit `.env`, tokens, or curl transcripts that contain passwords.
