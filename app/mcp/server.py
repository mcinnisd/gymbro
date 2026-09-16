"""
MCP server wrapping TOOLS_REGISTRY / TOOL_IMPLEMENTATIONS.

Transports:
  - stdio via ``python -m app.mcp`` (local Grokbot / Cursor)
  - authenticated Streamable HTTP at ``/api/mcp`` on Flask (localhost; tunnel optional)
"""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.mcp.auth import MCPAuthError, resolve_auth_context
from app.mcp.executor import execute_tool, tool_result_as_mcp_payload
from app.mcp.policies import CONFIRM_PARAM, get_mutation_policy, requires_confirm
from app.tools.registry import TOOLS_REGISTRY, get_tool_definitions

logger = logging.getLogger(__name__)

SERVER_NAME = "gymbro"
SERVER_INSTRUCTIONS = (
    "GYMBro athletic coaching tools. Athlete identity is bound by server-side "
    "MCP authentication (JWT or API key); never pass user_id. Destructive and "
    "bulk plan tools require confirm=true."
)


def _openai_schema_to_input_schema(parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert OpenAI function parameters object into JSON Schema for MCP."""
    if not parameters:
        return {"type": "object", "properties": {}}
    schema = deepcopy(parameters)
    if "type" not in schema:
        schema["type"] = "object"
    # Ensure user_id is never advertised as a client parameter
    props = schema.get("properties") or {}
    props.pop("user_id", None)
    schema["properties"] = props
    required = [r for r in (schema.get("required") or []) if r != "user_id"]
    if required:
        schema["required"] = required
    elif "required" in schema:
        schema.pop("required")
    return schema


def _augment_schema_for_policy(tool_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Add confirm boolean for tools that require MCP approval."""
    if not requires_confirm(tool_name):
        return schema
    schema = deepcopy(schema)
    props = schema.setdefault("properties", {})
    policy = get_mutation_policy(tool_name)
    props[CONFIRM_PARAM] = {
        "type": "boolean",
        "description": (
            policy.confirmation_message
            or "Set true to confirm this mutating action."
        ),
        "default": False,
    }
    return schema


def build_mcp_tools() -> List[types.Tool]:
    """Map TOOLS_REGISTRY entries to MCP Tool definitions."""
    tools: List[types.Tool] = []
    for entry in get_tool_definitions():
        fn = entry.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        description = fn.get("description") or name
        policy = get_mutation_policy(name)
        if policy.requires_approval:
            description = f"{description} [requires confirm=true]"
        input_schema = _augment_schema_for_policy(
            name, _openai_schema_to_input_schema(fn.get("parameters"))
        )
        tools.append(
            types.Tool(
                name=name,
                description=description,
                inputSchema=input_schema,
                annotations=types.ToolAnnotations(
                    readOnlyHint=policy.category in ("read", "analytics"),
                    destructiveHint=name.startswith("delete_"),
                    idempotentHint=policy.category in ("read", "analytics"),
                    openWorldHint=False,
                ),
            )
        )
    return tools


def create_mcp_server() -> Server:
    """Create and wire the low-level MCP Server over the domain registry."""
    server = Server(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        # Catalog is non-sensitive; auth is enforced on call_tool.
        return build_mcp_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] | None):
        try:
            auth = resolve_auth_context()
        except MCPAuthError as exc:
            payload = {
                "success": False,
                "observation": str(exc),
                "error": "authentication_required",
            }
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload))],
                structuredContent=payload,
                isError=True,
            )

        result = execute_tool(name, arguments or {}, auth=auth)
        payload = tool_result_as_mcp_payload(result)
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, default=str),
                )
            ],
            structuredContent=payload,
            isError=not result.success,
        )

    return server


async def run_stdio_async() -> None:
    """Serve MCP over stdio (default transport for local clients)."""
    server = create_mcp_server()
    # Fail fast with a clear log if auth env is missing (still allow process
    # start so clients can surface the auth error on first request).
    try:
        ctx = resolve_auth_context()
        logger.info(
            "GYMBro MCP ready (auth=%s, user_id=%s)",
            ctx.auth_method,
            ctx.user_id,
        )
    except MCPAuthError as exc:
        logger.warning("GYMBro MCP starting without valid auth yet: %s", exc)

    init_opts = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_opts)


def run_stdio() -> None:
    """Blocking entrypoint used by `python -m app.mcp`."""
    # Keep stdout reserved for MCP JSON-RPC; send logs to stderr.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [gymbro-mcp] %(message)s",
        stream=__import__("sys").stderr,
        force=True,
    )
    asyncio.run(run_stdio_async())


# Expose registry size for smoke checks / docs
REGISTERED_TOOL_COUNT = len(TOOLS_REGISTRY)
