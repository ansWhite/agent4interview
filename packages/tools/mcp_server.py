"""Optional MCP adapter exposing the same allowlisted local tools."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from packages.tools.registry import ToolRegistry


def create_mcp_server() -> Any:
    """Create an MCP server when the optional `mcp` extra is installed."""
    try:
        fast_mcp = import_module("mcp.server.fastmcp").FastMCP
    except ImportError as exc:  # pragma: no cover - optional integration
        raise RuntimeError("Install InsightAgent with the [mcp] extra") from exc

    registry = ToolRegistry()
    server = fast_mcp("insight-agent-tools")

    async def calculator(expression: str) -> str:
        """Safely calculate a basic arithmetic expression."""
        result = await registry.execute("calculator", {"expression": expression})
        if not result.ok:
            raise ValueError(result.error_code or "calculation_failed")
        return result.output

    server.tool()(calculator)
    return server


if __name__ == "__main__":  # pragma: no cover - manual process entrypoint
    create_mcp_server().run()
