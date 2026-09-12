"""Remote Cloud Executor (Groq LLM/Whisper) for R.I.O. (Milestone 4)."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional

from services.compute.result import ComputeResult
from services.compute.workload import ComputeTarget, Workload

logger = logging.getLogger("rio.compute.remote")


class RemoteExecutor:
    """Dispatches workloads to remote high-throughput cloud endpoints (Groq)."""

    def __init__(self, model_router: Optional[Any] = None):
        self.model_router = model_router
        self._handlers: Dict[str, Callable[[Any], Any]] = {}

    def register_handler(self, workload_type: str, handler: Callable[[Any], Any]) -> None:
        self._handlers[workload_type] = handler

    async def execute(self, workload: Workload) -> ComputeResult:
        """Execute workload via remote cloud API."""
        start_time = time.perf_counter()

        # Strict safety check: Never route local_only data to remote
        if workload.privacy == "local_only":
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ComputeResult(
                output=None,
                target_used=ComputeTarget.REMOTE,
                latency_ms=latency_ms,
                success=False,
                error="Security Violation: Workload with 'local_only' privacy cannot be routed to Remote Executor.",
            )

        handler = self._handlers.get(workload.type)
        try:
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    output = await handler(workload.input)
                else:
                    loop = asyncio.get_running_loop()
                    output = await loop.run_in_executor(None, handler, workload.input)
            elif self.model_router and hasattr(self.model_router, "generate"):
                # Default call to model router
                prompt = str(workload.input)
                output = await self.model_router.generate(prompt=prompt)
            else:
                # Mock or generic remote payload echo
                output = f"Remote processed: {str(workload.input)[:100]}"

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ComputeResult(
                output=output,
                target_used=ComputeTarget.REMOTE,
                latency_ms=latency_ms,
                vram_used_mb=0,
                success=True,
                metrics={"provider": "groq", "type": workload.type},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Remote execution failure: {e}", exc_info=True)
            return ComputeResult(
                output=None,
                target_used=ComputeTarget.REMOTE,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )
