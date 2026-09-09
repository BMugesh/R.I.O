"""MCP Audit Logger for tracking tool calls and security events."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rio.mcp.audit")


class MCPAuditLogger:
    """Audit logger for recording all MCP invocations and observations."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []

    def log_call(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: Optional[str] = "default_user",
        task_id: Optional[str] = None,
    ) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_id": server_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "user_id": user_id,
            "task_id": task_id,
            "status": "invoked",
        }
        self._entries.append(entry)
        logger.info(f"[MCP Audit] Call: {server_id}/{tool_name} by {user_id}")
        return entry["timestamp"]

    def log_result(
        self,
        server_id: str,
        tool_name: str,
        success: bool,
        output_summary: str,
        execution_time_ms: float,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_id": server_id,
            "tool_name": tool_name,
            "success": success,
            "output_summary": output_summary,
            "execution_time_ms": execution_time_ms,
            "status": "completed",
        }
        self._entries.append(entry)
        logger.info(f"[MCP Audit] Result: {server_id}/{tool_name} success={success} in {execution_time_ms}ms")

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._entries[-limit:]
