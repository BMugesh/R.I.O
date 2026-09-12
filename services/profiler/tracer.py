"""Execution profiler and span tracer for R.I.O."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import contextvars
import logging
import time
from typing import Any, Dict, List, Optional

from services.profiler.spans import Span, SpanType, TaskProfileTrace

logger = logging.getLogger("rio.profiler")

_current_task_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_task_id", default=None
)


class ProfileTracer:
    """Thread-safe and async-safe performance tracer for R.I.O. tasks."""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._traces: Dict[str, TaskProfileTrace] = {}
        self._active_spans: Dict[str, List[Span]] = {}

    def start_trace(self, task_id: str, goal: str = "", metadata: Optional[Dict[str, Any]] = None) -> TaskProfileTrace:
        """Initialize a new task execution profile trace."""
        trace = TaskProfileTrace(
            task_id=task_id,
            goal=goal,
            metadata=metadata or {},
        )
        self._traces[task_id] = trace
        self._active_spans[task_id] = []
        _current_task_id.set(task_id)

        # Evict oldest if exceeding max history
        if len(self._traces) > self.max_history:
            oldest = next(iter(self._traces))
            self._traces.pop(oldest, None)
            self._active_spans.pop(oldest, None)

        return trace

    def end_trace(self, task_id: Optional[str] = None) -> Optional[TaskProfileTrace]:
        """Finish a trace and return the completed profile."""
        tid = task_id or _current_task_id.get()
        if not tid or tid not in self._traces:
            return None

        trace = self._traces[tid]
        trace.finish()
        self._active_spans.pop(tid, None)
        return trace

    def get_trace(self, task_id: str) -> Optional[TaskProfileTrace]:
        return self._traces.get(task_id)

    def get_all_traces(self) -> List[TaskProfileTrace]:
        return list(self._traces.values())

    def record_span(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        duration_ms: float = 0.0,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Directly record an already measured span."""
        tid = task_id or _current_task_id.get()
        span = Span(
            name=name,
            span_type=span_type,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        if tid and tid in self._traces:
            self._traces[tid].add_span(span)
        return span

    @contextmanager
    def span(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Synchronous context manager for measuring a code block."""
        tid = task_id or _current_task_id.get()
        s = Span(name=name, span_type=span_type, metadata=metadata or {})
        try:
            yield s
        finally:
            s.finish()
            if tid and tid in self._traces:
                self._traces[tid].add_span(s)

    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Asynchronous context manager for measuring async operations."""
        tid = task_id or _current_task_id.get()
        s = Span(name=name, span_type=span_type, metadata=metadata or {})
        try:
            yield s
        finally:
            s.finish()
            if tid and tid in self._traces:
                self._traces[tid].add_span(s)


# Global default tracer singleton
_default_tracer: Optional[ProfileTracer] = None


def get_tracer() -> ProfileTracer:
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = ProfileTracer()
    return _default_tracer
