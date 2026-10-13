"""Metrics Collector & Performance Aggregator for R.I.O. (Milestone 5).

Aggregates operational metrics across planning, execution, verification,
model routing, and caching.
"""

from collections import deque
import logging
from typing import Any, Dict, List, Optional

from services.observability.execution_trace import ExecutionTrace

logger = logging.getLogger("rio.observability.metrics")


class MetricsCollector:
    """Central metrics aggregator tracking runtime performance and SLA statistics."""

    def __init__(self, max_history: int = 500):
        self._traces: deque[ExecutionTrace] = deque(maxlen=max_history)

    def record_trace(self, trace: ExecutionTrace) -> None:
        """Store an execution trace for aggregate analysis."""
        self._traces.append(trace)

    def get_summary(self) -> Dict[str, Any]:
        """Generate high-level operational statistics."""
        if not self._traces:
            return {
                "total_tasks": 0,
                "completed": 0,
                "failed": 0,
                "avg_duration_ms": 0.0,
                "avg_planning_ms": 0.0,
                "avg_execution_ms": 0.0,
                "avg_concurrency": 1.0,
            }

        total = len(self._traces)
        completed = sum(1 for t in self._traces if t.final_status == "completed")
        failed = sum(1 for t in self._traces if t.final_status in ("failed", "cancelled"))
        avg_dur = sum(t.total_duration_ms for t in self._traces) / total
        avg_plan = sum(t.planning_time_ms for t in self._traces) / total
        avg_exec = sum(t.execution_time_ms for t in self._traces) / total
        avg_conc = sum(t.max_concurrency for t in self._traces) / total

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total) if total > 0 else 0.0,
            "avg_duration_ms": round(avg_dur, 2),
            "avg_planning_ms": round(avg_plan, 2),
            "avg_execution_ms": round(avg_exec, 2),
            "avg_concurrency": round(avg_conc, 2),
        }


# Global singleton
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Retrieve global MetricsCollector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
