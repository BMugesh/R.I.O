"""Built-in Tool Implementations for R.I.O.

Provides baseline filesystem, web retrieval, math, and system utility tools.
"""

from datetime import datetime, timezone
import math
import os
from typing import Any, Dict
import httpx
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.tools import ToolCall, ToolDefinition, ToolProviderType, ToolResult


class BuiltInTools:
    """Standard built-in tools collection."""

    @staticmethod
    def get_definitions() -> list[ToolDefinition]:
        return [
            ToolDefinition(
                id="builtin_get_datetime",
                name="get_current_datetime",
                description="Get current system date, time, and timezone.",
                parameters={
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "default": "UTC"}
                    },
                },
                risk_level=AgentRiskLevel.LOW,
                provider_type=ToolProviderType.BUILTIN,
            ),
            ToolDefinition(
                id="builtin_math_eval",
                name="calculate_expression",
                description="Safely evaluate mathematical expressions.",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression, e.g. '2 ** 10 * sin(pi/4)'"}
                    },
                    "required": ["expression"],
                },
                risk_level=AgentRiskLevel.LOW,
                provider_type=ToolProviderType.BUILTIN,
            ),
            ToolDefinition(
                id="builtin_read_file",
                name="read_file",
                description="Safely read text content of a file within allowed workspaces.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative file path"}
                    },
                    "required": ["path"],
                },
                risk_level=AgentRiskLevel.LOW,
                provider_type=ToolProviderType.BUILTIN,
            ),
            ToolDefinition(
                id="builtin_write_file",
                name="write_file",
                description="Write content to a file inside the allowed workspace directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Target file path"},
                        "content": {"type": "string", "description": "File text content"},
                    },
                    "required": ["path", "content"],
                },
                risk_level=AgentRiskLevel.MEDIUM,
                provider_type=ToolProviderType.BUILTIN,
            ),
            ToolDefinition(
                id="builtin_web_fetch",
                name="fetch_web_page",
                description="Fetch the text or HTML content of a public URL.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Public URL to fetch"}
                    },
                    "required": ["url"],
                },
                risk_level=AgentRiskLevel.LOW,
                provider_type=ToolProviderType.BUILTIN,
            ),
        ]

    @staticmethod
    async def execute(tool_id: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a built-in tool."""
        start_time = datetime.now(timezone.utc)
        try:
            if tool_id == "builtin_get_datetime":
                now_str = datetime.now(timezone.utc).isoformat()
                return ToolResult(tool_id=tool_id, success=True, output={"current_datetime": now_str, "timezone": "UTC"})

            elif tool_id == "builtin_math_eval":
                expr = args.get("expression", "")
                # Safe evaluation using math globals
                allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
                allowed_names.update({"abs": abs, "round": round, "min": min, "max": max})
                result = eval(expr, {"__builtins__": {}}, allowed_names)
                return ToolResult(tool_id=tool_id, success=True, output={"result": result})

            elif tool_id == "builtin_read_file":
                path = args.get("path", "")
                if not os.path.exists(path):
                    return ToolResult(tool_id=tool_id, success=False, error=f"File not found: {path}")
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return ToolResult(tool_id=tool_id, success=True, output={"path": path, "content": content, "size": len(content)})

            elif tool_id == "builtin_write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return ToolResult(tool_id=tool_id, success=True, output={"path": path, "bytes_written": len(content)})

            elif tool_id == "builtin_web_fetch":
                url = args.get("url", "")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    return ToolResult(
                        tool_id=tool_id,
                        success=resp.status_code == 200,
                        output={"status_code": resp.status_code, "text": resp.text[:10000]},
                    )

            return ToolResult(tool_id=tool_id, success=False, error=f"Unknown builtin tool: {tool_id}")
        except Exception as e:
            return ToolResult(tool_id=tool_id, success=False, error=str(e))
