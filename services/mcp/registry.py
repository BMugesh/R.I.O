"""MCP Registry and Server Manager for R.I.O.

Enables dynamic registration of MCP servers (e.g. Playwright MCP, GitHub MCP, Notion MCP)
and exposes their tools to R.I.O.'s central Tool Registry.
"""

from typing import Dict, List, Optional
from packages.schemas.tools import MCPManifest, ToolDefinition
from services.mcp.client import MCPClient
from services.tool_router.registry import ToolRegistry


class MCPRegistry:
    """Registry of connected MCP Servers."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or ToolRegistry()
        self._servers: Dict[str, MCPManifest] = {}
        self._clients: Dict[str, MCPClient] = {}
        self._initialize_default_servers()

    def _initialize_default_servers(self) -> None:
        """Register default MCP server specifications (e.g. Playwright MCP)."""
        playwright_mcp = MCPManifest(
            id="mcp_playwright",
            name="Playwright Browser MCP",
            transport="stdio",
            command="npx",
            args=["@playwright/mcp@latest"],
            tools=[
                ToolDefinition(
                    id="playwright_navigate",
                    name="navigate",
                    description="Navigate browser to a specified URL using Playwright MCP.",
                    parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                    provider_type="mcp",
                    provider_id="mcp_playwright",
                ),
                ToolDefinition(
                    id="playwright_click",
                    name="click",
                    description="Click an element on the active page via CSS selector or text.",
                    parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
                    provider_type="mcp",
                    provider_id="mcp_playwright",
                ),
                ToolDefinition(
                    id="playwright_type",
                    name="type_text",
                    description="Type text into an input element.",
                    parameters={
                        "type": "object",
                        "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
                        "required": ["selector", "text"],
                    },
                    provider_type="mcp",
                    provider_id="mcp_playwright",
                ),
                ToolDefinition(
                    id="playwright_screenshot",
                    name="take_screenshot",
                    description="Capture a screenshot of the browser page.",
                    parameters={"type": "object", "properties": {"full_page": {"type": "boolean", "default": False}}},
                    provider_type="mcp",
                    provider_id="mcp_playwright",
                ),
            ],
        )
        self.register_server(playwright_mcp)

    def register_server(self, manifest: MCPManifest) -> None:
        """Register a new MCP server and its exposed tools."""
        self._servers[manifest.id] = manifest
        client = MCPClient(manifest)
        self._clients[manifest.id] = client

        # Register tools in R.I.O. tool registry
        for tool in manifest.tools:
            self.tool_registry.register_tool(
                tool,
                executor=lambda args, m_id=manifest.id, t_name=tool.name: client.call_tool(t_name, args),
            )

    def unregister_server(self, server_id: str) -> bool:
        """Unregister an MCP server and its tools."""
        server = self._servers.pop(server_id, None)
        client = self._clients.pop(server_id, None)
        if server:
            for tool in server.tools:
                self.tool_registry.unregister_tool(tool.id)
            return True
        return False

    def list_servers(self) -> List[MCPManifest]:
        return list(self._servers.values())

    def get_client(self, server_id: str) -> Optional[MCPClient]:
        return self._clients.get(server_id)
