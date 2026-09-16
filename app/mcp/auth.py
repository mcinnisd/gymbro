"""
MCP session authentication.

Resolves the authenticated athlete `user_id` from process environment
credentials (stdio) or per-request HTTP headers. Client-supplied `user_id`
tool arguments are never trusted (ADR-0003 §3).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator, Mapping, Optional

import jwt

from app.config import Config

logger = logging.getLogger(__name__)

# Request-scoped auth for HTTP MCP (set on the ASGI/event-loop task).
_request_auth: ContextVar[Optional["MCPAuthContext"]] = ContextVar(
    "gymbro_mcp_request_auth", default=None
)


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


def bind_request_auth(ctx: MCPAuthContext) -> Token:
    """Bind athlete identity for the current async/HTTP task."""
    return _request_auth.set(ctx)


def reset_request_auth(token: Token) -> None:
    """Restore the previous request-auth binding."""
    _request_auth.reset(token)


@contextmanager
def request_auth_scope(ctx: MCPAuthContext) -> Iterator[MCPAuthContext]:
    """Context manager form of bind_request_auth / reset_request_auth."""
    token = bind_request_auth(ctx)
    try:
        yield ctx
    finally:
        reset_request_auth(token)


def resolve_http_auth(
    *,
    authorization: Optional[str] = None,
    api_key: Optional[str] = None,
) -> MCPAuthContext:
    """
    Resolve athlete identity from HTTP request credentials only.

    Does **not** fall back to `GYMBRO_MCP_TOKEN` / process-inherited API key
    presentation — remote callers must send headers on every request.

    Accepts:
      - ``Authorization: Bearer <jwt>``
      - ``X-Api-Key`` / ``X-MCP-API-Key`` matching server ``GYMBRO_MCP_API_KEY``
        (binds ``GYMBRO_MCP_USER_ID``)
    """
    if authorization:
        scheme, _, remainder = authorization.strip().partition(" ")
        if scheme.lower() == "bearer" and remainder.strip():
            resolved = _decode_jwt(remainder.strip())
            return MCPAuthContext(user_id=resolved, auth_method="jwt")
        if scheme.lower() == "bearer":
            raise MCPAuthError("Empty Bearer token.")

    provided = (api_key or "").strip()
    if provided:
        expected_key = os.getenv("GYMBRO_MCP_API_KEY")
        if not expected_key:
            raise MCPAuthError(
                "GYMBRO_MCP_API_KEY is not configured on the server."
            )
        if provided != expected_key:
            raise MCPAuthError("Invalid MCP API key.")
        user_id = os.getenv("GYMBRO_MCP_USER_ID")
        if not user_id:
            raise MCPAuthError(
                "GYMBRO_MCP_USER_ID is required when authenticating with an API key."
            )
        return MCPAuthContext(user_id=str(user_id).strip(), auth_method="api_key")

    raise MCPAuthError(
        "MCP authentication required. Send Authorization: Bearer <jwt> or X-Api-Key."
    )


def resolve_http_auth_from_headers(headers: Mapping[str, str]) -> MCPAuthContext:
    """Resolve HTTP auth from a case-insensitive header mapping."""
    # Flask/Werkzeug headers are case-insensitive; plain dicts may not be.
    lowered = {str(k).lower(): v for k, v in headers.items()}
    authorization = lowered.get("authorization")
    api_key = lowered.get("x-api-key") or lowered.get("x-mcp-api-key")
    return resolve_http_auth(authorization=authorization, api_key=api_key)


def resolve_auth_context(
    *,
    token: Optional[str] = None,
    api_key: Optional[str] = None,
    user_id: Optional[str] = None,
) -> MCPAuthContext:
    """
    Resolve athlete identity from MCP session credentials.

    Precedence:
      0. Request-bound HTTP auth (contextvar), if set
      1. JWT via `token` / `GYMBRO_MCP_TOKEN`
      2. API key via `api_key` / `GYMBRO_MCP_API_KEY` paired with
         `user_id` / `GYMBRO_MCP_USER_ID`
    """
    bound = _request_auth.get()
    if bound is not None:
        return bound

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
