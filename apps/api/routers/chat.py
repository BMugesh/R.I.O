"""Chat API Router."""

from fastapi import APIRouter, Depends
from packages.schemas.chat import ChatRequest, ChatResponse
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, container: Container = Depends(get_container)):
    """Process a conversational message or high-level task request."""
    return await container.orchestrator.process_chat(request)
