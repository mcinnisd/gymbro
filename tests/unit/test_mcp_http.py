"""Unit tests for authenticated MCP Streamable HTTP on Flask (/api/mcp)."""

from __future__ import annotations

import json

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


def _mcp_headers(**extra):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    headers.update(extra)
    return headers


def _initialize_body(req_id=1):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        },
    }


def _parse_jsonrpc_response(response):
    raw = response.get_data(as_text=True)
    assert response.status_code == 200, raw
    data = json.loads(raw)
    # Some transports wrap a single message; accept either.
    if isinstance(data, list):
        assert data, "empty JSON-RPC batch"
        return data[0]
    return data


def test_resolve_http_auth_bearer_jwt(monkeypatch):
    monkeypatch.delenv("GYMBRO_MCP_API_KEY", raising=False)
    token = jwt.encode(
        {"sub": "77"},
        Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM,
    )
    ctx = resolve_http_auth(authorization=f"Bearer {token}")
    assert ctx.user_id == "77"
    assert ctx.auth_method == "jwt"


def test_resolve_http_auth_api_key(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "secret")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "9")
    ctx = resolve_http_auth(api_key="secret")
    assert ctx.user_id == "9"
    assert ctx.auth_method == "api_key"


def test_resolve_http_auth_rejects_missing():
    with pytest.raises(MCPAuthError):
        resolve_http_auth()


def test_resolve_http_auth_from_headers_x_api_key(monkeypatch):
    monkeypatch.setenv("GYMBRO_MCP_API_KEY", "secret")
    monkeypatch.setenv("GYMBRO_MCP_USER_ID", "9")
    ctx = resolve_http_auth_from_headers({"X-Api-Key": "secret"})
    assert ctx.user_id == "9"


def test_mcp_http_rejects_unauthenticated(client):
    resp = client.post(
        "/api/mcp",
        headers=_mcp_headers(),
        data=json.dumps(_initialize_body()),
    )
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["error"] == "authentication_required"


def test_mcp_http_rejects_bad_api_key(client):
    resp = client.post(
        "/api/mcp",
        headers=_mcp_headers(**{"X-Api-Key": "wrong"}),
        data=json.dumps(_initialize_body()),
    )
    assert resp.status_code == 401


def test_mcp_http_initialize_and_list_tools(client, mcp_app):
    # Ensure runtime is up
    get_mcp_http_runtime(mcp_app)

    init_resp = client.post(
        "/api/mcp",
        headers=_mcp_headers(**{"X-Api-Key": "test-mcp-secret"}),
        data=json.dumps(_initialize_body()),
    )
    init_msg = _parse_jsonrpc_response(init_resp)
    assert init_msg.get("jsonrpc") == "2.0"
    assert "result" in init_msg
    assert init_msg["result"].get("serverInfo", {}).get("name") == "gymbro"

    session_id = init_resp.headers.get("mcp-session-id") or init_resp.headers.get(
        "Mcp-Session-Id"
    )

    # notifications/initialized (no response body required; may be 202)
    notif_headers = _mcp_headers(**{"X-Api-Key": "test-mcp-secret"})
    if session_id:
        notif_headers["Mcp-Session-Id"] = session_id
    client.post(
        "/api/mcp",
        headers=notif_headers,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        ),
    )

    list_headers = _mcp_headers(**{"X-Api-Key": "test-mcp-secret"})
    if session_id:
        list_headers["Mcp-Session-Id"] = session_id
    list_resp = client.post(
        "/api/mcp",
        headers=list_headers,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        ),
    )
    list_msg = _parse_jsonrpc_response(list_resp)
    assert "result" in list_msg
    tools = list_msg["result"].get("tools") or []
    names = {t["name"] for t in tools}
    assert "get_wellness_metrics" in names
    assert "get_calendar_events" in names
    assert "delete_calendar_event" in names


def test_mcp_http_jwt_auth_smoke(client, mcp_app, monkeypatch):
    token = jwt.encode(
        {"sub": "athlete-jwt"},
        Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM,
    )
    # API key still configured on server but JWT path should win via Bearer
    get_mcp_http_runtime(mcp_app)
    resp = client.post(
        "/api/mcp",
        headers=_mcp_headers(Authorization=f"Bearer {token}"),
        data=json.dumps(_initialize_body(req_id=9)),
    )
    msg = _parse_jsonrpc_response(resp)
    assert msg["result"]["serverInfo"]["name"] == "gymbro"
