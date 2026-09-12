"""Metrics and telemetry collection for ComputeRouter."""

from dataclasses import dataclass, field
import threading
from typing import Any, Dict, List

from services.compute.workload import ComputeTarget


@dataclass
class ComputeMetricsCollector:
    """Thread-safe telemetry accumulator for compute execution."""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    total_executions: int = 0
    cpu_executions: int = 0
    gpu_executions: int = 0
    remote_executions: int = 0
    fallback_events: int = 0
    total_latency_ms: float = 0.0

    def record(self, target: ComputeTarget, latency_ms: float, fallback: bool = False) -> None:
        with self._lock:
            self.total_executions += 1
            self.total_latency_ms += latency_ms
            if fallback:
                self.fallback_events += 1

            if target == ComputeTarget.CPU:
                self.cpu_executions += 1
            elif target == ComputeTarget.GPU:
                self.gpu_executions += 1
            elif target == ComputeTarget.REMOTE:
                self.remote_executions += 1

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            avg_lat = round(self.total_latency_ms / max(1, self.total_executions), 2)
            return {
                "total_executions": self.total_executions,
                "cpu_executions": self.cpu_executions,
                "gpu_executions": self.gpu_executions,
                "remote_executions": self.remote_executions,
                "fallback_events": self.fallback_events,
                "average_latency_ms": avg_lat,
            }


_metrics_collector = ComputeMetricsCollector()


def get_compute_metrics() -> ComputeMetricsCollector:
    return _metrics_collector
