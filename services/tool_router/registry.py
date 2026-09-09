"""Tool Registry & Router for R.I.O.

Registers, discovers, and safely executes built-in, MCP, and custom tools.
"""

from typing import Any, Callable, Dict, List, Optional
from packages.schemas.tools import ToolCall, ToolDefinition, ToolProviderType, ToolResult
from services.tool_router.builtin_tools import BuiltInTools


class ToolRegistry:
    """Registry managing all tools available to R.I.O. agents."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._custom_executors: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        for tool_def in BuiltInTools.get_definitions():
            self.register_tool(tool_def)

    def register_tool(
        self,
        tool: ToolDefinition,
        executor: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        """Register a new tool definition and optional executor function."""
        self._tools[tool.id] = tool
        if executor:
            self._custom_executors[tool.id] = executor

    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a tool from the registry."""
        self._custom_executors.pop(tool_id, None)
        return self._tools.pop(tool_id, None) is not None

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def list_tools(self, provider_type: Optional[ToolProviderType] = None) -> List[ToolDefinition]:
        """List all active tools, optionally filtered by provider type."""
        tools = [t for t in self._tools.values() if t.enabled]
        if provider_type:
            tools = [t for t in tools if t.provider_type == provider_type]
        return tools

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call safely."""
        tool = self.get_tool(tool_call.tool_id)
        if not tool:
            return ToolResult(
                tool_id=tool_call.tool_id,
                call_id=tool_call.id,
                success=False,
                error=f"Tool not found in registry: {tool_call.tool_id}",
            )

        # Check for custom python executor
        if tool_call.tool_id in self._custom_executors:
            try:
                fn = self._custom_executors[tool_call.tool_id]
                res = fn(tool_call.arguments)
                return ToolResult(tool_id=tool.id, call_id=tool_call.id, success=True, output=res)
            except Exception as e:
                return ToolResult(tool_id=tool.id, call_id=tool_call.id, success=False, error=str(e))

        # Builtin tool execution
        if tool.provider_type == ToolProviderType.BUILTIN:
            res = await BuiltInTools.execute(tool.id, tool_call.arguments)
            res.call_id = tool_call.id
            return res

        return ToolResult(
            tool_id=tool.id,
            call_id=tool_call.id,
            success=False,
            error=f"Execution handler not found for provider type: {tool.provider_type}",
        )
