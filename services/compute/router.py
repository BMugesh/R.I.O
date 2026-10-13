"""Compute Router — The Decision Engine of R.I.O.'s Compute Fabric (Milestone 4).

Decides where workloads execute across CPU, GPU (RTX 4050), and Remote Cloud (Groq),
enforcing VRAM limits, privacy boundaries, safety constraints, and automated fallback.
"""

import logging
import time
from typing import Any, Dict, Optional

from services.compute.cpu_executor import CPUExecutor
from services.compute.detector import ComputeDetector
from services.compute.gpu_executor import GPUExecutor
from services.compute.metrics import get_compute_metrics
from services.compute.policy import ComputePolicy
from services.compute.remote_executor import RemoteExecutor
from services.compute.result import ComputeResult
from services.compute.workload import ComputeDecision, ComputeTarget, Workload
from services.profiler.spans import SpanType
from services.profiler.tracer import get_tracer

logger = logging.getLogger("rio.compute.router")


class ComputeRouter:
    """The central compute decision and execution router in R.I.O."""

    def __init__(
        self,
        policy: Optional[ComputePolicy] = None,
        detector: Optional[ComputeDetector] = None,
        cpu_executor: Optional[CPUExecutor] = None,
        gpu_executor: Optional[GPUExecutor] = None,
        remote_executor: Optional[RemoteExecutor] = None,
    ):
        self.policy = policy or ComputePolicy()
        self.detector = detector or ComputeDetector()
        self.cpu_executor = cpu_executor or CPUExecutor()
        self.gpu_executor = gpu_executor or GPUExecutor()
        self.remote_executor = remote_executor or RemoteExecutor()
        self.metrics = get_compute_metrics()
        self.tracer = get_tracer()

    def decide(self, workload: Workload) -> ComputeDecision:
        """Evaluate workload and resolve optimal compute target."""
        gpu_ready = self.detector.is_gpu_ready()
        free_vram = self.detector.get_free_vram_mb()

        return self.policy.evaluate(
            workload=workload,
            gpu_available=gpu_ready,
            free_vram_mb=free_vram,
        )

    async def execute(self, workload: Workload) -> ComputeResult:
        """Route and execute workload on target, with automatic fallback and telemetry."""
        decision = self.decide(workload)
        target = decision.target
        start_time = time.perf_counter()

        logger.info(
            f"ComputeRouter dispatch: workload='{workload.type}', target='{target.value}', "
            f"reason='{decision.reason}', fallback='{decision.fallback}'"
        )

        span_name = f"compute_{target.value}:{workload.type}"
        span_type = (
            SpanType.GPU if target == ComputeTarget.GPU else
            (SpanType.REMOTE if target == ComputeTarget.REMOTE else SpanType.CPU)
        )

        with self.tracer.span(name=span_name, span_type=span_type, metadata={"target": target.value}):
            result = await self._dispatch_target(target, workload)

        # Automated Fallback Chain
        if not result.success and decision.fallback:
            fallback_target = decision.fallback

            # Privacy gate verification for fallback
            if workload.privacy == "local_only" and fallback_target == ComputeTarget.REMOTE:
                logger.warning("Rejecting fallback to REMOTE due to 'local_only' privacy constraint.")
                fallback_target = ComputeTarget.CPU

            logger.warning(
                f"Workload '{workload.type}' failed on {target.value} ({result.error}). "
                f"Falling back to {fallback_target.value}."
            )

            fallback_span_name = f"fallback_{fallback_target.value}:{workload.type}"
            fallback_span_type = (
                SpanType.GPU if fallback_target == ComputeTarget.GPU else
                (SpanType.REMOTE if fallback_target == ComputeTarget.REMOTE else SpanType.CPU)
            )

            with self.tracer.span(name=fallback_span_name, span_type=fallback_span_type, metadata={"target": fallback_target.value, "fallback": True}):
                fallback_result = await self._dispatch_target(fallback_target, workload)

            fallback_result.fallback_triggered = True
            total_lat = (time.perf_counter() - start_time) * 1000.0
            self.metrics.record(fallback_target, total_lat, fallback=True)
            return fallback_result

        total_lat = (time.perf_counter() - start_time) * 1000.0
        self.metrics.record(target, total_lat, fallback=False)
        return result

    async def _dispatch_target(self, target: ComputeTarget, workload: Workload) -> ComputeResult:
        """Internal dispatch to designated executor."""
        if target == ComputeTarget.GPU:
            return await self.gpu_executor.execute(workload)
        elif target == ComputeTarget.REMOTE:
            return await self.remote_executor.execute(workload)
        else:
            return await self.cpu_executor.execute(workload)

    def register_gpu_worker(self, workload_type: str, worker: Any) -> None:
        self.gpu_executor.register_worker(workload_type, worker)

    def register_cpu_handler(self, workload_type: str, handler: Any) -> None:
        self.cpu_executor.register_handler(workload_type, handler)

    def register_remote_handler(self, workload_type: str, handler: Any) -> None:
        self.remote_executor.register_handler(workload_type, handler)

    def get_status(self) -> Dict[str, Any]:
        """Aggregate status of all compute targets."""
        hw = self.detector.get_hardware_status()
        metrics_summary = self.metrics.get_summary()

        return {
            "gpu": hw,
            "cpu": {"threads": 4, "status": "READY"},
            "remote": {"provider": "groq", "status": "READY"},
            "metrics": metrics_summary,
        }

    def shutdown(self) -> None:
        """Shutdown CPU thread pool and evict GPU workers."""
        try:
            self.cpu_executor.shutdown()
        except Exception:
            pass
        try:
            self.gpu_executor.shutdown()
        except Exception:
            pass


# Global singleton
_compute_router: Optional[ComputeRouter] = None


def get_compute_router() -> ComputeRouter:
    global _compute_router
    if _compute_router is None:
        _compute_router = ComputeRouter()
    return _compute_router
