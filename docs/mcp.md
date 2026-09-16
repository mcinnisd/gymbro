# GYMBro MCP Server

Expose GYMBro domain tools to external MCP clients (Grokbot, Cursor, Claude Desktop) without changing domain tool cores or migrating Flask → FastAPI.

**ADR:** [0003 — Agent MCP protocol & tool surface](adr/0003-agent-mcp-protocol-and-tool-surface-design.md)

## What it is

A thin MCP adapter under `app/mcp/` that wraps `TOOLS_REGISTRY` / `TOOL_IMPLEMENTATIONS` from `app/tools/registry.py`.

| Transport | How | Best for |
|-----------|-----|----------|
| **stdio** | `python -m app.mcp` | Desktop Cursor / local Grokbot on the same machine |
| **HTTP** (Streamable, JSON) | Flask route `POST/GET/DELETE /api/mcp` | Phone Grokbot via Cloudflare Tunnel / ngrok |

```
Phone Grokbot ──HTTPS──▶ Cloudflare Tunnel / ngrok
                              │
                              ▼
                     Flask :5001 /api/mcp
                              │  (Bearer JWT or X-Api-Key)
                              ▼
                     app/tools/*  (unchanged)
```

Flask stays the primary HTTP API. Superpowers skills are untouched.

## Prerequisites

```bash
pip install -r requirements.txt   # includes mcp>=1.28,<2
```

## Authentication

Athlete `user_id` is **always** bound server-side (ADR-0003). Client tool args never supply tenant identity; any `user_id` argument is stripped.

### Stdio (process env)

Choose **one** of:

**Option A — JWT**

```bash
export GYMBRO_MCP_TOKEN="<access_token from /auth/login>"
export JWT_SECRET_KEY="<same as Flask>"
```

**Option B — Personal API key**

```bash
export GYMBRO_MCP_API_KEY="a-long-random-secret"
export GYMBRO_MCP_USER_ID="<your athlete user id>"
```

### HTTP (`/api/mcp` request headers)

Every request must authenticate. Env fallbacks for `GYMBRO_MCP_TOKEN` are **not** used on the HTTP path.

| Header | Value |
|--------|--------|
| `Authorization: Bearer <jwt>` | Access token from `/auth/login` (same `JWT_SECRET_KEY`) |
| **or** `X-Api-Key: <secret>` | Must match server `GYMBRO_MCP_API_KEY`; binds `GYMBRO_MCP_USER_ID` |

Also set the usual app env (`SUPABASE_URL`, `SUPABASE_KEY`, or `MOCK_DB=true` for offline).

## Run locally

### Stdio (desktop)

```bash
python -m app.mcp
```

### HTTP (same Flask process)

```bash
# Same env you already use for Flask, plus MCP API key binding:
export GYMBRO_MCP_API_KEY="a-long-random-secret"
export GYMBRO_MCP_USER_ID="YOUR_USER_ID"

python app.py
# → http://127.0.0.1:5001/api/mcp
```

Smoke (API key — or use `Authorization: Bearer <jwt>` instead of `X-Api-Key`):

```bash
curl -sS -X POST "http://127.0.0.1:5001/api/mcp" \
  -H "X-Api-Key: $GYMBRO_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Unauthenticated calls return **401**.

Optional env:

| Var | Purpose |
|-----|---------|
| `GYMBRO_MCP_STATELESS=true` | No session stickiness (better for multi-worker) |
| `GYMBRO_MCP_DNS_REBINDING_PROTECTION=true` | Enforce Host allowlist |
| `GYMBRO_MCP_ALLOWED_HOSTS` | Comma-separated hosts when DNS rebinding protection is on |
| `GYMBRO_MCP_HTTP_DISABLE=true` | Skip starting the HTTP runtime (tests / emergency) |

## Remote access (phone) — Cloudflare Tunnel or ngrok

Keep Flask local. Expose HTTPS to `/api/mcp` only if you can; otherwise expose the whole `:5001` and rely on MCP auth.

### Cloudflare Tunnel (recommended)

```bash
# Terminal 1 — Flask
python app.py

# Terminal 2 — quick tunnel (ephemeral URL)
cloudflared tunnel --url http://127.0.0.1:5001
```

Copy the `https://*.trycloudflare.com` URL. MCP endpoint:

`https://<your-subdomain>.trycloudflare.com/api/mcp`

For a stable hostname, create a named tunnel in the Cloudflare Zero Trust dashboard and point it at `http://127.0.0.1:5001`.

### ngrok

```bash
ngrok http 5001
```

Use `https://<id>.ngrok-free.app/api/mcp`.

**Security:** never expose MCP without auth; rotate `GYMBRO_MCP_API_KEY` / JWT if a URL leaks; prefer HTTPS-only tunnels.

## Connect Grokbot (phone)

Point mobile Grokbot at the **URL**, not a local `command`/`args` spawn.

| Field | Example |
|-------|---------|
| Transport | HTTP / Streamable MCP (JSON) |
| URL | `https://gymbro.<tunnel>.trycloudflare.com/api/mcp` |
| Auth | `Authorization: Bearer <JWT>` **or** API key header `X-Api-Key: …` |
| Server name | `gymbro` |

Desktop Grokbot / Cursor can keep using stdio (`python -m app.mcp`).

## Connect Cursor (stdio)

```json
{
  "mcpServers": {
    "gymbro": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "cwd": "/absolute/path/to/gymbro",
      "env": {
        "GYMBRO_MCP_API_KEY": "a-long-random-secret",
        "GYMBRO_MCP_USER_ID": "YOUR_USER_ID",
        "JWT_SECRET_KEY": "your_jwt_secret_key",
        "SUPABASE_URL": "https://YOUR_PROJECT.supabase.co",
        "SUPABASE_KEY": "YOUR_KEY",
        "MOCK_DB": "false"
      }
    }
  }
}
```

Prefer the same Python interpreter as your venv, e.g. `"/absolute/path/to/gymbro/venv/bin/python"`.

## Mutation policy (MCP)

| Category | Tools | Behavior |
|----------|-------|----------|
| Read / analytics | `get_*`, `generate_chart` | Run immediately |
| Direct edits | calendar create/update, `log_meal`, `log_manual_workout`, `reschedule_workout`, `update_goal` | Run on explicit tool call |
| Requires `confirm=true` | `delete_calendar_event`, `generate_training_plan` | First call returns `confirmation_required`; re-call with `confirm: true` |

## Exposed tools (v1)

From `TOOL_IMPLEMENTATIONS`:

- Calendar: `create_calendar_event`, `get_calendar_events`, `update_calendar_event`, `delete_calendar_event`
- Telemetry: `get_recent_activities`, `get_wellness_metrics`, `generate_chart`, `get_biomarkers`, `get_biomarker_trends`
- Coach: `generate_training_plan`, `update_goal`, `reschedule_workout`, `log_manual_workout`, `log_meal`

Widget-only Expo envelopes and Garmin credential writes stay off MCP.

## Deferred / out of scope here

- Cloud Run always-on deploy notes (optional follow-up)
- Full `ToolResult` migration of every domain tool
- Live Supabase/Garmin smoke against production data (orthogonal to this adapter)
