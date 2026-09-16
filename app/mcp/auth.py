"""
MCP session authentication.

Resolves the authenticated athlete `user_id` from process environment
credentials. Client-supplied `user_id` tool arguments are never trusted
(ADR-0003 §3).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import jwt

from app.config import Config

logger = logging.getLogger(__name__)


class MCPAuthError(Exception):
    """Raised when MCP credentials are missing or invalid."""


@dataclass(frozen=True)
class MCPAuthContext:
    user_id: str
    auth_method: str  # "jwt" | "api_key"


def _decode_jwt(token: str) -> str:
    """Decode a Flask-JWT-Extended style access token and return identity."""
    try:
        payload = jwt.decode(
            token,
            Config.JWT_SECRET_KEY,
            algorithms=[Config.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        raise MCPAuthError(f"Invalid JWT: {exc}") from exc

    # flask_jwt_extended stores identity in `sub`
    user_id = payload.get("sub") or payload.get("identity")
    if user_id is None or user_id == "":
        raise MCPAuthError("JWT missing subject (user identity).")
    return str(user_id)


def resolve_auth_context(
    *,
    token: Optional[str] = None,
    api_key: Optional[str] = None,
    user_id: Optional[str] = None,
) -> MCPAuthContext:
    """
    Resolve athlete identity from MCP session credentials.

    Precedence:
      1. JWT via `token` / `GYMBRO_MCP_TOKEN`
      2. API key via `api_key` / `GYMBRO_MCP_API_KEY` paired with
         `user_id` / `GYMBRO_MCP_USER_ID`
    """
    token = token if token is not None else os.getenv("GYMBRO_MCP_TOKEN")
    api_key = api_key if api_key is not None else os.getenv("GYMBRO_MCP_API_KEY")
    user_id = user_id if user_id is not None else os.getenv("GYMBRO_MCP_USER_ID")

    if token:
        resolved = _decode_jwt(token.strip())
        return MCPAuthContext(user_id=resolved, auth_method="jwt")

    expected_key = os.getenv("GYMBRO_MCP_API_KEY")
    if api_key or expected_key:
        if not expected_key:
            raise MCPAuthError(
                "GYMBRO_MCP_API_KEY is not configured on the server."
            )
        provided = (api_key or "").strip()
        # For stdio, the client typically inherits the same env; accept when
        # the process env already holds a matching key + user id.
        if provided and provided != expected_key:
            raise MCPAuthError("Invalid MCP API key.")
        if not provided and not os.getenv("GYMBRO_MCP_API_KEY"):
            raise MCPAuthError("MCP API key required.")
        if not user_id:
            raise MCPAuthError(
                "GYMBRO_MCP_USER_ID is required when authenticating with an API key."
            )
        return MCPAuthContext(user_id=str(user_id).strip(), auth_method="api_key")

    raise MCPAuthError(
        "MCP authentication required. Set GYMBRO_MCP_TOKEN (JWT) or "
        "GYMBRO_MCP_API_KEY + GYMBRO_MCP_USER_ID."
    )


def get_bound_user_id() -> str:
    """Convenience: resolve and return the server-bound athlete id."""
    return resolve_auth_context().user_id
