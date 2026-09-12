"""Compute execution result data structures for R.I.O."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.compute.workload import ComputeTarget


@dataclass
class ComputeResult:
    """Execution output from a compute executor."""
    output: Any
    target_used: ComputeTarget
    latency_ms: float
    vram_used_mb: int = 0
    fallback_triggered: bool = False
    success: bool = True
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "target_used": self.target_used.value,
            "latency_ms": round(self.latency_ms, 3),
            "vram_used_mb": self.vram_used_mb,
            "fallback_triggered": self.fallback_triggered,
            "error": self.error,
            "metrics": self.metrics,
        }
