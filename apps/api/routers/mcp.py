"""MCP Registry API Router."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from packages.schemas.tools import MCPManifest
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("", response_model=List[MCPManifest])
async def list_mcp_servers(container: Container = Depends(get_container)):
    """List registered Model Context Protocol (MCP) servers."""
    return container.mcp_registry.list_servers()


@router.post("/register", response_model=MCPManifest)
async def register_mcp_server(manifest: MCPManifest, container: Container = Depends(get_container)):
    """Register a new MCP server and discover its tools."""
    container.mcp_registry.register_server(manifest)
    return manifest


@router.delete("/{server_id}")
async def unregister_mcp_server(server_id: str, container: Container = Depends(get_container)):
    """Unregister an MCP server and unbind its tools."""
    success = container.mcp_registry.unregister_server(server_id)
    if not success:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return {"status": "unregistered", "server_id": server_id}
