"""API Routers module."""

from apps.api.routers.chat import router as chat_router
from apps.api.routers.tasks import router as tasks_router
from apps.api.routers.approvals import router as approvals_router
from apps.api.routers.devices import router as devices_router
from apps.api.routers.agents import agents_router, tools_router
from apps.api.routers.mcp import router as mcp_router
from apps.api.routers.memory import router as memory_router
from apps.api.routers.voice import router as voice_router
from apps.api.routers.quantum import router as quantum_router
from apps.api.routers.ws import router as ws_router

__all__ = [
    "chat_router",
    "tasks_router",
    "approvals_router",
    "devices_router",
    "agents_router",
    "tools_router",
    "mcp_router",
    "memory_router",
    "voice_router",
    "quantum_router",
    "ws_router",
]
