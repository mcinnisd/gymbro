"""
Execute domain tools for MCP callers with server-enforced user binding.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from app.mcp.auth import MCPAuthContext, resolve_auth_context
from app.mcp.policies import CONFIRM_PARAM, get_mutation_policy, requires_confirm
from app.tools.models import ToolExecutionContext, ToolResult
from app.tools.registry import get_tool_implementation

logger = logging.getLogger(__name__)


def _to_tool_result(raw: Any, tool_name: str) -> ToolResult:
    """Normalize domain tool returns into ToolResult for MCP consumers."""
    if isinstance(raw, ToolResult):
        return raw

    if isinstance(raw, dict):
        status = raw.get("status")
        if "error" in raw and status is None:
            success = False
        else:
            success = status != "error"
        observation = (
            raw.get("observation")
            or raw.get("message")
            or (raw.get("error") if not success else None)
            or f"Tool '{tool_name}' completed."
        )
        if not isinstance(observation, str):
            observation = json.dumps(observation, default=str)

        error = None
        if not success:
            err_val = raw.get("error") or raw.get("message")
            error = json.dumps(err_val, default=str) if isinstance(err_val, dict) else (
                str(err_val) if err_val is not None else "error"
            )

        data_payload: Dict[str, Any]
        if isinstance(raw.get("data"), dict) and set(raw.keys()) <= {
            "status", "message", "observation", "error", "data", "ui_payload", "count", "events"
        }:
            data_payload = raw
        else:
            data_payload = raw

        return ToolResult(
            success=success,
            observation=observation,
            ui_payload=raw.get("ui_payload"),
            data=data_payload,
            error=error,
        )

    return ToolResult(
        success=True,
        observation=str(raw),
        data={"result": raw},
    )


def _approval_blocked_result(tool_name: str) -> ToolResult:
    policy = get_mutation_policy(tool_name)
    message = policy.confirmation_message or (
        f"Tool '{tool_name}' requires confirm=true before execution."
    )
    return ToolResult(
        success=False,
        observation=message,
        data={
            "tool": tool_name,
            "mutation_policy": policy.model_dump(),
            "requires_confirm": True,
        },
        error="confirmation_required",
    )


def _is_confirmed(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}:
        return True
    return False


def strip_and_bind_user(
    arguments: Optional[Dict[str, Any]],
    user_id: str,
) -> Tuple[Dict[str, Any], Any]:
    """
    Remove client-supplied user_id / confirm, return (call_args, confirm_value).

    `user_id` in the returned call_args is always the server-bound identity.
    """
    raw = dict(arguments or {})
    raw.pop("user_id", None)
    confirm_value = raw.pop(CONFIRM_PARAM, None)
    call_args = dict(raw)
    call_args["user_id"] = user_id
    return call_args, confirm_value


def execute_tool(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    auth: Optional[MCPAuthContext] = None,
) -> ToolResult:
    """
    Run a registered domain tool under MCP auth + mutation policy.

    Auth failures raise MCPAuthError (from resolve_auth_context).
    Domain failures are returned as ToolResult(success=False).
    """
    if auth is None:
        auth = resolve_auth_context()

    func = get_tool_implementation(tool_name)
    if not func:
        return ToolResult(
            success=False,
            observation=f"Unknown tool: {tool_name}",
            error=f"Unknown tool: {tool_name}",
        )

    call_args, confirm_value = strip_and_bind_user(arguments, auth.user_id)

    if requires_confirm(tool_name) and not _is_confirmed(confirm_value):
        return _approval_blocked_result(tool_name)

    # confirm is adapter-only; do not forward to domain tools
    ctx = ToolExecutionContext(
        user_id=auth.user_id,
        client_platform="mcp_agent",
    )
    assert call_args["user_id"] == ctx.user_id

    try:
        result = func(**call_args)
        return _to_tool_result(result, tool_name)
    except TypeError as exc:
        logger.warning("Tool %s argument error: %s", tool_name, exc)
        return ToolResult(
            success=False,
            observation=f"Invalid arguments for '{tool_name}': {exc}",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        return ToolResult(
            success=False,
            observation=f"Tool '{tool_name}' failed: {exc}",
            error=str(exc),
        )


def tool_result_as_mcp_payload(result: ToolResult) -> Dict[str, Any]:
    """Serialize ToolResult for MCP structured content."""
    return result.model_dump(exclude_none=True)
