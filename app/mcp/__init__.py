"""
GYMBro MCP Server Adapter.

Exposes the domain tool catalog (`app/tools/registry.py`) over the
Model Context Protocol for external agents (Grokbot, Cursor, Claude Desktop).

See ADR-0003 and docs/mcp.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

__all__ = ["create_mcp_server", "run_stdio"]


def create_mcp_server() -> "Server":
    from app.mcp.server import create_mcp_server as _create

    return _create()


def run_stdio() -> None:
    from app.mcp.server import run_stdio as _run

    return _run()
