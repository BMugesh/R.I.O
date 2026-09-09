"""Unit tests for MCP integration and audit logging."""

import pytest
from packages.schemas.tools import MCPManifest, ToolDefinition
from services.mcp.registry import MCPRegistry
from services.mcp.audit import MCPAuditLogger
from services.tool_router.registry import ToolRegistry


@pytest.mark.asyncio
async def test_mcp_registry_and_tool_binding():
    tool_reg = ToolRegistry()
    mcp_reg = MCPRegistry(tool_registry=tool_reg)

    # Verify Playwright MCP is registered by default
    servers = mcp_reg.list_servers()
    assert len(servers) >= 1
    assert any(s.id == "mcp_playwright" for s in servers)

    # Check that playwright tools exist in tool registry
    playwright_tool = tool_reg.get_tool("playwright_navigate")
    assert playwright_tool is not None
    assert playwright_tool.provider_id == "mcp_playwright"


def test_mcp_audit_logger():
    audit = MCPAuditLogger()
    audit.log_call("mcp_playwright", "navigate", {"url": "https://google.com"}, user_id="user_1")
    audit.log_result("mcp_playwright", "navigate", success=True, output_summary="Loaded", execution_time_ms=120)

    logs = audit.get_logs()
    assert len(logs) == 2
    assert logs[0]["tool_name"] == "navigate"
