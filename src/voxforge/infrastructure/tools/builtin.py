import ast
import operator
from datetime import UTC, datetime
from typing import Any

_SAFE_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_math(expression: str) -> float:
    node = ast.parse(expression.strip(), mode="eval")

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int | float):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.operand))
        raise ValueError("Unsupported expression")

    return _eval(node)


class BuiltinGetTimeTool:
    name = "get_current_time"
    description = "Get the current UTC date and time."
    required_scopes: list[str] = []
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def invoke(self, arguments: dict[str, Any]) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


class BuiltinCalculatorTool:
    name = "calculate"
    description = "Evaluate a basic math expression (numbers, +, -, *, /, parentheses)."
    required_scopes: list[str] = []
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression e.g. (2 + 3) * 4",
            }
        },
        "required": ["expression"],
    }

    async def invoke(self, arguments: dict[str, Any]) -> str:
        expression = str(arguments.get("expression", "")).strip()
        if not expression:
            raise ValueError("expression is required")
        return str(_safe_eval_math(expression))


class BuiltinEchoTool:
    name = "echo"
    description = "Echo back a message (useful for testing)."
    required_scopes: list[str] = []
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message to echo"},
        },
        "required": ["message"],
    }

    async def invoke(self, arguments: dict[str, Any]) -> str:
        return str(arguments.get("message", ""))


BUILTIN_TOOLS: list[Any] = [
    BuiltinGetTimeTool(),
    BuiltinCalculatorTool(),
    BuiltinEchoTool(),
]
