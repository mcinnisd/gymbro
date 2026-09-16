"""
Flask blueprint: authenticated MCP Streamable HTTP at ``/api/mcp``.
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request

from app.extensions import limiter
from app.mcp.auth import MCPAuthError, resolve_http_auth_from_headers

logger = logging.getLogger(__name__)

mcp_bp = Blueprint("mcp_http", __name__)


@mcp_bp.route("/api/mcp", methods=["GET", "POST", "DELETE", "OPTIONS"])
@mcp_bp.route("/api/mcp/", methods=["GET", "POST", "DELETE", "OPTIONS"])
@limiter.exempt
def mcp_http_endpoint():
    """
    Streamable HTTP MCP endpoint (JSON responses).

    Auth (required on every request except OPTIONS):
      - ``Authorization: Bearer <jwt>`` (same tokens as ``/auth/login``), or
      - ``X-Api-Key: <GYMBRO_MCP_API_KEY>`` (binds ``GYMBRO_MCP_USER_ID``)
    """
    if request.method == "OPTIONS":
        # Flask-CORS usually handles this; keep an explicit 204 for tunnels.
        return ("", 204)

    try:
        auth = resolve_http_auth_from_headers(request.headers)
    except MCPAuthError as exc:
        logger.info("MCP HTTP auth rejected: %s", exc)
        return jsonify({"error": "authentication_required", "message": str(exc)}), 401

    try:
        from app.mcp.http_transport import get_mcp_http_runtime

        runtime = get_mcp_http_runtime(current_app._get_current_object())
        return runtime.dispatch(request, auth)
    except RuntimeError as exc:
        logger.error("MCP HTTP runtime unavailable: %s", exc)
        return jsonify({"error": "mcp_unavailable", "message": str(exc)}), 503
