"""Tool & MCP Schemas for R.I.O.

Standardized interfaces for built-in tools, custom extensions, and Model Context Protocol (MCP) integrations.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from packages.schemas.agents import AgentRiskLevel


class ToolProviderType(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    DEVICE = "device"
    PLUGIN = "plugin"
    REST = "rest"


class ToolParameter(BaseModel):
    name: str
    type: str  # 'string', 'number', 'boolean', 'array', 'object'
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class ToolDefinition(BaseModel):
    """Specification of an executable tool."""
    id: str
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)  # JSON Schema
    required_permissions: List[str] = Field(default_factory=list)
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW
    provider_type: ToolProviderType = ToolProviderType.BUILTIN
    provider_id: Optional[str] = None  # e.g., 'mcp-playwright', 'desktop-agent'
    is_sandboxed: bool = True
    enabled: bool = True


class ToolCall(BaseModel):
    """Invocation of a tool with specific arguments."""
    id: str
    tool_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Output returned by a tool execution."""
    tool_id: str
    call_id: Optional[str] = None
    success: bool = True
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    evidence: Optional[Dict[str, Any]] = None


class MCPManifest(BaseModel):
    """MCP Server metadata and tool discovery."""
    id: str
    name: str
    version: str = "1.0.0"
    transport: str = "stdio"  # 'stdio' or 'sse'
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    tools: List[ToolDefinition] = Field(default_factory=list)
    is_active: bool = True
