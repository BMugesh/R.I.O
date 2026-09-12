"""Performance profiling span data structures for R.I.O."""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional


class SpanType(str, Enum):
    """Categorical types of execution spans in the R.I.O. lifecycle."""
    INPUT = "input"
    INTENT = "intent"
    PLANNING = "planning"
    MODEL = "model"
    TOOL = "tool"
    GPU = "gpu"
    CPU = "cpu"
    REMOTE = "remote"
    VERIFICATION = "verification"
    RESPONSE = "response"
    CUSTOM = "custom"


@dataclass
class Span:
    """A discrete, timed unit of execution within a task."""
    name: str
    span_type: SpanType = SpanType.CUSTOM
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self) -> float:
        """Mark span completion and compute duration in milliseconds."""
        if self.duration_ms > 0.0 and self.end_time is None:
            self.end_time = self.start_time + (self.duration_ms / 1000.0)
            return self.duration_ms
        if self.end_time is None:
            self.end_time = time.time()
        self.duration_ms = max(0.0, (self.end_time - self.start_time) * 1000.0)
        return self.duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.span_type.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 3),
            "metadata": self.metadata,
        }


@dataclass
class TaskProfileTrace:
    """Full hierarchical execution profile trace for a task."""
    task_id: str
    goal: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration_ms: float = 0.0
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self) -> float:
        """Finish the trace and compute total duration."""
        if self.end_time is None:
            self.end_time = time.time()
        self.total_duration_ms = max(0.0, (self.end_time - self.start_time) * 1000.0)
        return self.total_duration_ms

    def add_span(self, span: Span) -> None:
        if span.end_time is None:
            span.finish()
        self.spans.append(span)

    def get_breakdown(self) -> Dict[str, float]:
        """Aggregate total duration in ms grouped by span type."""
        breakdown: Dict[str, float] = {}
        for s in self.spans:
            stype = s.span_type.value
            breakdown[stype] = breakdown.get(stype, 0.0) + s.duration_ms
        return {k: round(v, 2) for k, v in breakdown.items()}

    def get_spans_by_type(self, span_type: SpanType) -> List[Span]:
        return [s for s in self.spans if s.span_type == span_type]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "breakdown_ms": self.get_breakdown(),
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }
