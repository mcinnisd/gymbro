# GYMBro MCP Server

Expose GYMBro domain tools to external MCP clients (Grokbot, Cursor, Claude Desktop) without changing the Flask app or domain tool core.

**ADR:** [0003 — Agent MCP protocol & tool surface](adr/0003-agent-mcp-protocol-and-tool-surface-design.md)

## What it is

A thin **stdio MCP adapter** under `app/mcp/` that wraps `TOOLS_REGISTRY` / `TOOL_IMPLEMENTATIONS` from `app/tools/registry.py`.

```
Grokbot / Cursor / Claude Desktop
        │  MCP (stdio)
        ▼
python -m app.mcp
        │
        ▼
app/tools/*  (unchanged)
```

Flask stays the primary HTTP API. This PR does **not** add `/api/mcp` (deferred) and does **not** migrate to FastAPI.

## Prerequisites

```bash
pip install -r requirements.txt   # includes mcp>=1.28,<2
```

## Authentication

Athlete `user_id` is **always** bound server-side (ADR-0003). Client tool args never supply tenant identity; any `user_id` argument is stripped.

Choose **one** of:

### Option A — JWT (same tokens as the Flask API)

```bash
export GYMBRO_MCP_TOKEN="<access_token from /auth/login>"
export JWT_SECRET_KEY="<same as Flask>"
```

### Option B — Personal API key (local stdio)

```bash
export GYMBRO_MCP_API_KEY="a-long-random-secret"
export GYMBRO_MCP_USER_ID="<your athlete user id>"
```

Also set the usual app env (`SUPABASE_URL`, `SUPABASE_KEY`, or `MOCK_DB=true` for offline).

## Run the server

From the repo root (with venv activated):

```bash
python -m app.mcp
```

The process speaks MCP on **stdio** (stdin/stdout). Do not print debug logs to stdout when attached to a client.

## Connect Cursor

Add to Cursor MCP settings (`.cursor/mcp.json` or Cursor Settings → MCP):

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

## Connect Grokbot

Point Grokbot’s MCP tool/server config at the same stdio command:

| Field | Value |
|-------|--------|
| Command | `python` (or venv python) |
| Args | `-m`, `app.mcp` |
| Working directory | gymbro repo root |
| Env | `GYMBRO_MCP_TOKEN` **or** `GYMBRO_MCP_API_KEY` + `GYMBRO_MCP_USER_ID`, plus Supabase/JWT secrets |

Grokbot should list tools such as `get_wellness_metrics`, `get_calendar_events`, `log_meal`, etc., then call them **without** a `user_id` argument.

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

## Deferred

- Authenticated HTTP `/api/mcp` (SSE / streamable HTTP) for remote Grokbot
- Full `ToolResult` migration of every domain tool
- Live Supabase/Garmin smoke against production data (orthogonal to this adapter)
