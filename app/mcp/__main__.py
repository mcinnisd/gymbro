"""
stdio entrypoint for MCP clients.

Usage:
    python -m app.mcp

Configure GYMBRO_MCP_TOKEN (JWT) or GYMBRO_MCP_API_KEY + GYMBRO_MCP_USER_ID
before launching. See docs/mcp.md.
"""

from app.mcp.server import run_stdio


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()
