import pytest

from packages.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_calculator_executes_allowlisted_arithmetic() -> None:
    result = await ToolRegistry().execute("calculator", {"expression": "(2 + 3) * 4"})

    assert result.ok
    assert result.output == "20"


@pytest.mark.asyncio
async def test_registry_rejects_unknown_or_unsafe_tools() -> None:
    registry = ToolRegistry()

    unknown = await registry.execute("shell", {"command": "whoami"})
    unsafe = await registry.execute("calculator", {"expression": "__import__('os')"})

    assert not unknown.ok and unknown.error_code == "tool_not_allowed"
    assert not unsafe.ok and unsafe.error_code == "unsafe_or_invalid_expression"
