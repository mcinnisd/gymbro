"""
GYMBro MCP Server Adapter.

Exposes the domain tool catalog (`app/tools/registry.py`) over the
Model Context Protocol for external agents (Grokbot, Cursor, Claude Desktop).

Transports: stdio (`python -m app.mcp`) and authenticated HTTP (`/api/mcp`).

See ADR-0003 and docs/mcp.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

__all__ = ["create_mcp_server", "run_stdio", "mcp_bp"]


def create_mcp_server() -> "Server":
    from app.mcp.server import create_mcp_server as _create

    return _create()


def run_stdio() -> None:
    from app.mcp.server import run_stdio as _run

    return _run()


def __getattr__(name: str):
    if name == "mcp_bp":
        from app.mcp.routes import mcp_bp

        return mcp_bp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
