# Garmin → Supabase auto-sync

Garmin Connect is the Tier-1 telemetry source. Sync writes `garmin_activities`,
`biometrics_daily`, `garmin_daily`, `garmin_sleep`, and (when activities exist)
`training_events`. Agent/MCP tools now read those tables.

This is **not** official Garmin OAuth. Credentials are Garmin email + password,
encrypted with `ENCRYPTION_KEY` and stored on the athlete row. Do not commit
`.env`, tokens, or passwords.

`app/mcp/` is not on `main` yet (ADR-0003). Live MCP in Cursor talks to the
Cloudflare-tunneled Flask server and binds `user_id` from the API token.
Cloudflare 429s (50/hour) are tunnel rate limits, not Garmin or empty-data logic.

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

## Verify (MCP, after a successful sync)

Athlete `user_id` is bound from the MCP/API token. Do not pass a guessed id.

1. `get_wellness_metrics` with `days=7` — `records_count > 0` and non-null
   sleep/HRV/RHR averages **only if** `biometrics_daily` has Garmin rows in that window.
2. `get_recent_activities` with `days=14` — `count > 0` **only if**
   `garmin_activities` (or unified Strava/manual) has workouts in that window.
3. `get_calendar_events` — Garmin completions appear after activities sync into
   `training_events`. Empty is valid when there are no planned/completed events.
4. `get_biomarkers(flagged_only=true)` — lab panels, not Garmin. Empty is expected
   until bloodwork is uploaded.

Empty short-window MCP reads after a confirmed sync still mean missing rows for
that athlete in Supabase, not a Cloudflare 429. Longer lookbacks against the
trycloudflare tunnel may 429 independently.
