"""A calculator that evaluates a strict arithmetic AST allowlist."""

from __future__ import annotations

import ast
from typing import Any, cast

from packages.tools.base import ToolResult


class CalculatorTool:
    name = "calculator"
    description = "计算不包含变量和函数调用的算术表达式"

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            return ToolResult(
                ok=False, error_code="invalid_arguments", output="expression 必须是字符串"
            )
        if len(expression) > 200:
            return ToolResult(ok=False, error_code="expression_too_long")
        try:
            tree = ast.parse(expression, mode="eval")
            value = self._evaluate(tree.body)
            return ToolResult(ok=True, output=str(value))
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            return ToolResult(ok=False, error_code="unsafe_or_invalid_expression", output=str(exc))

    def _evaluate(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return cast(int | float, node.value)
        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                if abs(right) > 12:
                    raise ValueError("exponent exceeds safe limit")
                return cast(int | float, left**right)
        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
        raise ValueError(f"unsupported syntax: {type(node).__name__}")
