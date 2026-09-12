"""Workload definitions and compute contracts for R.I.O. (Milestone 4)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Literal, Optional

WorkloadType = Literal[
    "embedding",
    "vision_inference",
    "speech_to_text",
    "reranking",
    "ml_inference",
    "quantum_simulation",
    "general_compute",
]


class ComputeTarget(str, Enum):
    """Execution targets for computation."""
    CPU = "cpu"
    GPU = "gpu"
    REMOTE = "remote"


@dataclass
class Workload:
    """Standardized workload envelope allowing R.I.O. to reason about computation."""
    type: WorkloadType
    input: Any

    latency: Literal[
        "ultra_low",
        "low",
        "normal",
        "batch",
    ] = "normal"

    privacy: Literal[
        "local_only",
        "preferred_local",
        "remote_allowed",
    ] = "remote_allowed"

    estimated_memory_mb: int = 0
    allow_gpu: bool = True
    allow_remote: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeDecision:
    """The resolution determined by ComputeRouter for a workload."""
    target: ComputeTarget
    reason: str
    fallback: Optional[ComputeTarget] = None
    target_device: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
