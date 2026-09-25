# GYMBro MCP Server

Expose GYMBro domain tools to external MCP clients (Grok Bot, Cursor, Claude Desktop)
without changing domain tool cores.

**ADR:** [0003 — Agent MCP protocol & tool surface](adr/0003-agent-mcp-protocol-and-tool-surface-design.md)

Grok Bot coaching: [Grok Bot agents](#grok-bot-agents).

Verify and connect on **localhost**. Do not use Cloudflare quick tunnel / trycloudflare
for tests — it rate-limits at ~50 requests/hour (those 429s are the tunnel, not empty
athlete data). `cloudflared` is not required.

## What it is

A thin adapter under `app/mcp/` that wraps `TOOLS_REGISTRY` / `TOOL_IMPLEMENTATIONS`
from `app/tools/registry.py`. Athlete identity is bound **server-side** from JWT or
from `GYMBRO_MCP_API_KEY` → `GYMBRO_MCP_USER_ID`. Client `user_id` tool arguments are
stripped (ADR-0003).

| Transport | How | Best for |
|-----------|-----|----------|
| **stdio** | `python -m app.mcp` | Desktop Cursor / local Grok Bot on the same machine |
| **HTTP** (Streamable, JSON) | Flask `POST/GET/DELETE /api/mcp` | Grok Bot MCP connector on `http://127.0.0.1:5001/api/mcp` |

```
Grok Bot / Cursor ──HTTP──▶ Flask :5001 /api/mcp
                                 │  Bearer JWT or X-Api-Key
                                 ▼
                        app/tools/*  (unchanged; Garmin-first tables)
```

## Prerequisites

```bash
pip install -r requirements.txt   # includes mcp>=1.28,<2
```

Keep secrets in `.env` (gitignored). Never commit API keys, JWTs, or Garmin passwords.

## Authentication

Choose **one** binding. Do not invent `user_id`.

### HTTP (`/api/mcp` request headers)

Every request must authenticate. Process-env `GYMBRO_MCP_TOKEN` is **not** used on HTTP.

| Header | Value |
|--------|--------|
| `Authorization: Bearer <jwt>` | Access token from `/auth/login` (same `JWT_SECRET_KEY`) |
| **or** `X-Api-Key: <secret>` | Must match server `GYMBRO_MCP_API_KEY`; binds `GYMBRO_MCP_USER_ID` |

### Stdio (process env)

```bash
# Option A — JWT
export GYMBRO_MCP_TOKEN="<access_token from /auth/login>"
export JWT_SECRET_KEY="<same as Flask>"

# Option B — personal API key (binds athlete)
export GYMBRO_MCP_API_KEY="a-long-random-secret"
export GYMBRO_MCP_USER_ID="<your athlete user id>"   # e.g. 2
```

Also set the usual app env (`SUPABASE_URL`, `SUPABASE_KEY`, or `MOCK_DB=true` for offline).

## Run on localhost (no Cloudflare)

### 1. HTTP (same Flask process — Grok Bot connector)

```bash
# .env (not in git). Example shape only:
# GYMBRO_MCP_API_KEY=<generate a long random secret>
# GYMBRO_MCP_USER_ID=2
# JWT_SECRET_KEY=<same as Flask>
# MOCK_DB=false
# SUPABASE_URL=...
# SUPABASE_KEY=...

PYTHONPATH=. python app.py
# listens on http://127.0.0.1:5001
# MCP endpoint: http://127.0.0.1:5001/api/mcp
```

Do **not** pass `--tunnel` / do not start `cloudflared`.

Point the Grok Bot MCP connector at:

| Field | Value |
|-------|--------|
| Transport | HTTP / Streamable MCP (JSON) |
| URL | `http://127.0.0.1:5001/api/mcp` |
| Auth | `X-Api-Key: <GYMBRO_MCP_API_KEY>` **or** `Authorization: Bearer <jwt>` |
| Server name | `gymbro` |

Smoke (API key). Unauthenticated calls return **401**.

```bash
curl -sS -X POST "http://127.0.0.1:5001/api/mcp" \
  -H "X-Api-Key: $GYMBRO_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

After initialize, `tools/list` then `tools/call` for `get_wellness_metrics` /
`get_recent_activities` / `get_readiness` (omit `user_id`; the server binds it from the API key).

### 2. Stdio (desktop Cursor / Claude Desktop)

```bash
PYTHONPATH=. python -m app.mcp
```

Cursor `mcp.json` example (paths and secrets stay on the machine, not in git):

```json
{
  "mcpServers": {
    "gymbro": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "cwd": "/absolute/path/to/gymbro",
      "env": {
        "GYMBRO_MCP_API_KEY": "a-long-random-secret",
        "GYMBRO_MCP_USER_ID": "2",
        "JWT_SECRET_KEY": "your_jwt_secret_key",
        "SUPABASE_URL": "https://YOUR_PROJECT.supabase.co",
        "SUPABASE_KEY": "YOUR_KEY",
        "MOCK_DB": "false"
      }
    }
  }
}
```

Prefer the venv interpreter, e.g. `"/absolute/path/to/gymbro/venv/bin/python"`.

### 3. Regression tests (no server, no tunnel)

```bash
MOCK_DB=true PYTHONPATH=. python -m pytest \
  tests/unit/test_mcp_adapter.py \
  tests/unit/test_mcp_http.py \
  tests/unit/test_activity_tools.py \
  tests/unit/test_readiness_tools.py -v
```

Optional env:

| Var | Purpose |
|-----|---------|
| `GYMBRO_MCP_STATELESS=true` | No session stickiness (better for multi-worker) |
| `GYMBRO_MCP_DNS_REBINDING_PROTECTION=true` | Enforce Host allowlist |
| `GYMBRO_MCP_ALLOWED_HOSTS` | Comma-separated hosts when DNS rebinding protection is on |
| `GYMBRO_MCP_HTTP_DISABLE=true` | Skip starting the HTTP runtime (pytest default / emergency) |

## Optional remote tunnel (not for tests)

If a phone client cannot reach localhost, a named tunnel can expose `:5001`.
Quick `cloudflared tunnel --url` / trycloudflare is **not** recommended (429 at
~50 req/hour). Prefer a named tunnel or ngrok, HTTPS only, and rotate the API
key if a URL leaks. Auth is still required on every `/api/mcp` request.

## Mutation policy (MCP)

| Category | Tools | Behavior |
|----------|-------|----------|
| Read / analytics | `get_*`, `generate_chart` | Run immediately |
| Direct edits | calendar create/update, `log_meal`, `log_manual_workout`, `reschedule_workout`, `update_goal` | Run on explicit tool call |
| Requires `confirm=true` | `delete_calendar_event`, `generate_training_plan` | First call returns `confirmation_required`; re-call with `confirm: true` |

## Exposed tools (v1)

From `TOOL_IMPLEMENTATIONS`:

- Calendar: `create_calendar_event`, `get_calendar_events`, `update_calendar_event`, `delete_calendar_event`
- Telemetry: `get_recent_activities`, `get_wellness_metrics`, `get_readiness`, `generate_chart`, `get_biomarkers`, `get_biomarker_trends`
- Coach: `generate_training_plan`, `update_goal`, `reschedule_workout`, `log_manual_workout`, `log_meal`

`get_wellness_metrics` reads `biometrics_daily`. `get_recent_activities` uses
`get_unified_activities()` (Garmin-first). `get_readiness` is the sparse-aware
composite over those signals plus optional journal/biomarkers
(see [`docs/readiness.md`](readiness.md)). Widget-only Expo envelopes and Garmin
credential writes stay off MCP.

## Grok Bot agents

David's Grok Bot team coaches the sole athlete: `users.id` **2**
(`mcinnisdw@gmail.com`). Tools bind that id server-side (JWT or
`GYMBRO_MCP_API_KEY` → `GYMBRO_MCP_USER_ID`). Omit `user_id` on calls.

Prefer the **stdio** server `gymbro-stdio` (`python -m app.mcp` on the
machine that holds `.env`). The HTTP connector `user-gymbro` may be
`failed_to_load`. Do not rely on it for coaching.

Read `get_readiness` first, then `get_wellness_metrics` and
`get_recent_activities` ([`docs/readiness.md`](readiness.md)).

Live Garmin sync runs on the Hephaestus Grok Bot VM (`/workspace/gymbro`
plus that VM's `.env`). A routine runs daily at **6:20** `America/Los_Angeles`.
`remirror-biometrics` rebuilds `biometrics_daily` from rows already in
Supabase and does not call the Garmin API:

```bash
PYTHONPATH=. python -m app.garmin.cli remirror-biometrics --user-id 2
```

Keep `.env` on that VM. Never copy `.env` secrets into cloud agents or chat.
Cloud Run and public HTTP stay deferred. Sync details:
[`docs/garmin-sync.md`](garmin-sync.md).

## Related

- Garmin auto-sync + localhost tool probe: [`docs/garmin-sync.md`](garmin-sync.md)
- Calendar `created_by=garmin` CHECK is applied on live Supabase
  (`user|coach|agent|garmin|strava`). If `training_events` is still empty after
  a pre-migration sync, remirror from existing `garmin_activities`:
  `PYTHONPATH=. python -m app.garmin.cli remirror-calendar --user-id 2`
  (retries without `metrics` if that column is undeployed; apply
  `migrations/20260916_training_events_metrics.sql` to add `metrics jsonb`).
- If `garmin_daily` / `garmin_sleep` are ahead of `biometrics_daily` (wellness
  and readiness stay stale), remirror without calling Garmin:
  `PYTHONPATH=. python -m app.garmin.cli remirror-biometrics --user-id 2`
  then `verify-tools --user-id 2 --days-wellness 30`.
