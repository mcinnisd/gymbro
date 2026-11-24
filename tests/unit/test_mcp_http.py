"""Authenticated MCP Streamable HTTP on Flask (/api/mcp)."""
from __future__ import annotations

import json
from unittest.mock import patch

import jwt
import pytest

from app import create_app
from app.config import Config
from app.mcp.auth import MCPAuthError, resolve_http_auth, resolve_http_auth_from_headers
from app.mcp.http_transport import MCP_HTTP_EXTENSION, get_mcp_http_runtime

PROTOCOL_VERSION = "2025-03-26"


@pytest.fixture()
def mcp_app(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "test-mcp-secret")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "athlete-42")
    monkeypatch.delenv("GYMBRO_MCP_TOKEN", raising=False)
    monkeypatch.delenv("GYMBRO_MCP_HTTP_DISABLE", raising=False)
    monkeypatch.setenv("MOCK_DB", "true")
    app = create_app()
    app.config["TESTING"] = True
    yield app
    runtime = app.extensions.get(MCP_HTTP_EXTENSION)
    if runtime is not None:
        runtime.stop()


@pytest.fixture()
def client(mcp_app):
    return mcp_app.test_client()


def _headers(**extra):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    headers.update(extra)
    return headers


def _rpc(method, req_id=1, params=None):
    body = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def _parse(response):
    raw = response.get_data(as_text=True)
    assert response.status_code == 200, raw
    data = json.loads(raw)
    return data[0] if isinstance(data, list) else data


def _session(client, mcp_app, **headers):
    get_mcp_http_runtime(mcp_app)
    init = client.post("/api/mcp", headers=_headers(**{"X-Api-Key": "test-mcp-secret", **headers}), data=json.dumps(
        _rpc("initialize", params={"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}})
    ))
    msg = _parse(init)
    assert msg["result"]["serverInfo"]["name"] == "gymbro"
    session_id = init.headers.get("mcp-session-id") or init.headers.get("Mcp-Session-Id")
    extra = {"X-Api-Key": "test-mcp-secret"}
    if session_id:
        extra["Mcp-Session-Id"] = session_id
    client.post("/api/mcp", headers=_headers(**extra), data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    return extra


def test_http_auth_jwt_and_api_key(monkeypatch):
    monkeypatch.delenv("GYMBRO_MCP_API_KEY", raising=False)
    token = jwt.encode({"sub": "77"}, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
    assert resolve_http_auth(authorization=f"Bearer {token}").user_id == "77"
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "secret")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "9")
    assert resolve_http_auth(api_key="secret").auth_method == "api_key"
    assert resolve_http_auth_from_headers({"X-Api-Key": "secret"}).user_id == "9"
    with pytest.raises(MCPAuthError):
        resolve_http_auth()


@pytest.mark.parametrize("key,status", [(None, 401), ("wrong", 401)])
def test_mcp_http_rejects_bad_auth(client, key, status):
    extra = {"X-Api-Key": key} if key else {}
    resp = client.post("/api/mcp", headers=_headers(**extra), data=json.dumps(_rpc("initialize", params={})))
    assert resp.status_code == status


def test_mcp_http_lists_tools_and_binds_user(client, mcp_app):
    headers = _session(client, mcp_app)
    listed = _parse(client.post("/api/mcp", headers=_headers(**headers), data=json.dumps(_rpc("tools/list", 2, {}))))
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"get_wellness_metrics", "get_readiness", "get_wake_status", "get_calendar_events", "delete_calendar_event"} <= names
    calls = []

    def lookup(name):
        def impl(*, user_id, days=14, activity_type=None):
            calls.append((name, user_id, days))
            return {"status": "success"}
        return impl if name in {"get_wellness_metrics", "get_recent_activities"} else None

    with patch("app.mcp.executor.get_tool_implementation", side_effect=lookup):
        for req_id, name, days in ((3, "get_wellness_metrics", 30), (4, "get_recent_activities", 90)):
            msg = _parse(client.post("/api/mcp", headers=_headers(**headers), data=json.dumps(
                _rpc("tools/call", req_id, {"name": name, "arguments": {"user_id": "attacker", "days": days}})
            )))
            assert "result" in msg
    assert ("get_wellness_metrics", "athlete-42", 30) in calls
    assert ("get_recent_activities", "athlete-42", 90) in calls


def test_mcp_http_disabled_returns_503(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_HTTP_DISABLE", "true")
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "test-mcp-secret")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "2")
    app = create_app()
    app.config["TESTING"] = True
    resp = app.test_client().post("/api/mcp", headers=_headers(**{"X-Api-Key": "test-mcp-secret"}), data=json.dumps(_rpc("initialize", params={})))
    assert resp.status_code == 503 and resp.get_json()["error"] == "mcp_unavailable"


def test_mcp_http_jwt_auth_smoke(client, mcp_app):
    token = jwt.encode({"sub": "athlete-jwt"}, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
    get_mcp_http_runtime(mcp_app)
    msg = _parse(client.post(
        "/api/mcp", headers=_headers(Authorization=f"Bearer {token}"),
        data=json.dumps(_rpc("initialize", 9, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}})),
    ))
    assert msg["result"]["serverInfo"]["name"] == "gymbro"
