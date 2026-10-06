"""Tool contracts and validation-friendly results."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    ok: bool
    output: str = ""
    error_code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tool(Protocol):
    name: str
    description: str

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult: ...
