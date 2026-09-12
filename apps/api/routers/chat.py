"""Chat API Router."""

import re
from fastapi import APIRouter, Depends, Request
from packages.schemas.chat import ChatRequest, ChatResponse
from packages.schemas.devices import OriginContext
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_req: Request,
    container: Container = Depends(get_container),
):
    """Process a conversational message or high-level task request."""
    # Infer mobile device origin from HTTP User-Agent header if not explicitly supplied
    ua = http_req.headers.get("user-agent", "").lower()
    is_mobile_client = bool(re.search(r"android|iphone|ipad|ipod|mobile|webos", ua))

    if not request.origin_device_id:
        if is_mobile_client:
            request.origin_device_id = "android-01"
            request.interface_type = "mobile"
        elif not request.interface_type and "cli" not in (request.session_id or "").lower():
            request.origin_device_id = "laptop-01"
            request.interface_type = "web"

    if not request.interface_type:
        request.interface_type = "mobile" if is_mobile_client else "web"

    if not request.origin_context:
        request.origin_context = OriginContext(
            session_id=request.session_id or "default_session",
            interface_type=request.interface_type,
            origin_device_id=request.origin_device_id,
            origin_platform="android" if (request.origin_device_id and "android" in request.origin_device_id.lower() or is_mobile_client) else "windows",
        )

    return await container.orchestrator.process_chat(request)

