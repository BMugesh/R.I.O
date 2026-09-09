"""Agents & Tools Discovery API Routers."""

from typing import List
from fastapi import APIRouter, Depends
from packages.schemas.agents import AgentManifest
from packages.schemas.tools import ToolDefinition
from apps.api.deps import Container, get_container

agents_router = APIRouter(prefix="/agents", tags=["Agents"])
tools_router = APIRouter(prefix="/tools", tags=["Tools"])


@agents_router.get("", response_model=List[AgentManifest])
async def list_agents(container: Container = Depends(get_container)):
    """List all registered agents and their declarations."""
    return [agent.manifest for agent in container.agents.values()]


@tools_router.get("", response_model=List[ToolDefinition])
async def list_tools(container: Container = Depends(get_container)):
    """List all available tools and their schemas."""
    return container.tool_registry.list_tools()
