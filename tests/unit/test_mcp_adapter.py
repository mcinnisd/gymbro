"""Unit tests for the MCP adapter (auth, policies, executor, schema mapping)."""

from unittest.mock import patch

import jwt
import pytest

from app.config import Config
from app.mcp.auth import MCPAuthError, resolve_auth_context
from app.mcp.executor import execute_tool, strip_and_bind_user
from app.mcp.policies import requires_confirm
from app.mcp.server import build_mcp_tools, create_mcp_server
from app.tools.registry import TOOL_IMPLEMENTATIONS


def test_build_mcp_tools_covers_registry():
    tools = build_mcp_tools()
    names = {t.name for t in tools}
    assert names == set(TOOL_IMPLEMENTATIONS.keys())
    # confirm added for gated tools
    delete_tool = next(t for t in tools if t.name == "delete_calendar_event")
    assert "confirm" in delete_tool.inputSchema["properties"]
    # user_id never advertised
    for t in tools:
        assert "user_id" not in (t.inputSchema.get("properties") or {})


def test_create_mcp_server_constructs():
    server = create_mcp_server()
    assert server.name == "gymbro"


def test_resolve_auth_jwt(monkeypatch):
    token = jwt.encode(
        {"sub": "42"},
        Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM,
    )
    monkeypatch.delenv("GYMBRO_MCP_API_KEY", raising=False)
    monkeypatch.delenv("GYMBRO_MCP_USER_ID", raising=False)
    monkeypatch.setenv("GYMBRO_MCP_TOKEN", token)
    ctx = resolve_auth_context()
    assert ctx.user_id == "42"
    assert ctx.auth_method == "jwt"


def test_resolve_auth_api_key(monkeypatch):
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "secret-key")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "99")
    ctx = resolve_auth_context()
    assert ctx.user_id == "99"
    assert ctx.auth_method == "api_key"


def test_resolve_auth_rejects_bad_api_key(monkeypatch):
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "secret-key")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "99")
    with pytest.raises(MCPAuthError):
        resolve_auth_context(api_key="wrong", user_id="99")


def test_resolve_auth_missing(monkeypatch):
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)
    monkeypatch.delenv("GYMBRO_MCP_API_KEY", raising=False)
    monkeypatch.delenv("GYMBRO_MCP_USER_ID", raising=False)
    with pytest.raises(MCPAuthError):
        resolve_auth_context()


def test_strip_client_user_id():
    call_args, confirm = strip_and_bind_user(
        {"user_id": "attacker", "days": 7, "confirm": True},
        "bound-user",
    )
    assert call_args["user_id"] == "bound-user"
    assert "confirm" not in call_args
    assert confirm is True
    assert call_args["days"] == 7


def test_requires_confirm_policy():
    assert requires_confirm("generate_training_plan")
    assert requires_confirm("delete_calendar_event")
    assert not requires_confirm("get_wellness_metrics")
    assert not requires_confirm("log_meal")


def test_execute_blocks_without_confirm(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "k")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "1")
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)

    called = {"n": 0}

    def impl(**kw):
        called["n"] += 1
        return {"status": "success", "message": "deleted"}

    with patch("app.mcp.executor.get_tool_implementation", return_value=impl):
        blocked = execute_tool("delete_calendar_event", {"event_id": 1})
        assert blocked.success is False
        assert blocked.error == "confirmation_required"
        assert called["n"] == 0

        ok = execute_tool(
            "delete_calendar_event",
            {"event_id": 1, "confirm": True, "user_id": "hacker"},
        )
        assert ok.success is True
        assert called["n"] == 1


def test_execute_overrides_user_id(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "k")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "athlete-7")
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)

    seen = {}

    def fake_tool(**kwargs):
        seen.update(kwargs)
        return {"status": "success", "message": "ok", "activities": []}

    with patch(
        "app.mcp.executor.get_tool_implementation",
        return_value=fake_tool,
    ):
        result = execute_tool(
            "get_recent_activities",
            {"user_id": "attacker", "days": 3},
        )
    assert result.success is True
    assert seen["user_id"] == "athlete-7"
    assert seen["days"] == 3
