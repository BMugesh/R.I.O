"""R.I.O. Python Client SDK.

Enables seamless programmatic interaction with the R.I.O. personal AI OS via REST and WebSockets.
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
import websockets
from packages.schemas.chat import ChatRequest, ChatResponse, ChatStreamChunk
from packages.schemas.input import InputType
from packages.schemas.tasks import Task
from packages.schemas.safety import ApprovalDecision, ApprovalStatus


class RIOClient:
    """Async Client SDK for R.I.O."""

    def __init__(self, base_url: str = "http://localhost:8000", ws_url: str = "ws://localhost:8000/ws", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def chat(self, message: str, session_id: Optional[str] = None, developer_mode: bool = False) -> ChatResponse:
        """Send a message to R.I.O. and receive a response."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = ChatRequest(
                message=message,
                session_id=session_id,
                developer_mode=developer_mode,
            ).model_dump()
            res = await client.post(f"{self.base_url}/api/v1/chat", json=payload, headers=self._headers)
            res.raise_for_status()
            return ChatResponse(**res.json())

    async def stream_chat(self, message: str, session_id: Optional[str] = None, developer_mode: bool = False) -> AsyncGenerator[ChatStreamChunk, None]:
        """Stream conversational tokens and task updates over WebSocket."""
        async with websockets.connect(f"{self.ws_url}") as ws:
            req = {
                "type": "user_message",
                "message": message,
                "session_id": session_id,
                "developer_mode": developer_mode,
            }
            await ws.send(json.dumps(req))

            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    chunk = ChatStreamChunk(**data)
                    yield chunk
                    if chunk.chunk_type in ("done", "error"):
                        break
                except websockets.exceptions.ConnectionClosed:
                    break

    async def get_task(self, task_id: str) -> Task:
        """Get the current execution graph and status of a task."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{self.base_url}/api/v1/tasks/{task_id}", headers=self._headers)
            res.raise_for_status()
            return Task(**res.json())

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{self.base_url}/api/v1/tasks/{task_id}/cancel", headers=self._headers)
            return res.status_code == 200

    async def submit_approval(self, request_id: str, approved: bool, reason: Optional[str] = None) -> bool:
        """Approve or deny a pending action."""
        decision = ApprovalDecision(
            request_id=request_id,
            decision=ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED,
            reason=reason,
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{self.base_url}/api/v1/approvals/{request_id}",
                json=decision.model_dump(),
                headers=self._headers,
            )
            return res.status_code == 200
