"""Timeout-aware tool registry; unregistered tools can never execute."""

from __future__ import annotations

import asyncio
from typing import Any

from packages.tools.base import Tool, ToolResult
from packages.tools.calculator import CalculatorTool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None, timeout_seconds: float = 5.0) -> None:
        builtins: list[Tool] = [CalculatorTool()]
        self._tools = {tool.name: tool for tool in (tools if tools is not None else builtins)}
        self.timeout_seconds = timeout_seconds

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {"type": "object", "additionalProperties": True},
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error_code="tool_not_allowed", output=name)
        try:
            return await asyncio.wait_for(tool.invoke(arguments), timeout=self.timeout_seconds)
        except TimeoutError:
            return ToolResult(ok=False, error_code="tool_timeout", output=name)
        except Exception as exc:  # isolate third-party tool failures at the registry boundary
            return ToolResult(
                ok=False,
                error_code="tool_failure",
                output=f"{type(exc).__name__}: {exc}",
            )
