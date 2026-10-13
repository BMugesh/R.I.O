"""Test Performance Profiler and Task Trace Subsystem (Milestone 4)."""
import pytest
pytestmark = pytest.mark.unit



import asyncio
import time
import pytest
from services.profiler.report import render_ascii_report, to_json_report
from services.profiler.spans import Span, SpanType, TaskProfileTrace
from services.profiler.tracer import ProfileTracer


def test_span_lifecycle():
    span = Span(name="test_operation", span_type=SpanType.INPUT)
    time.sleep(0.01)
    duration = span.finish()

    assert duration > 0.0
    data = span.to_dict()
    assert data["name"] == "test_operation"
    assert data["type"] == "input"
    assert data["duration_ms"] > 0.0


def test_task_profile_trace():
    trace = TaskProfileTrace(task_id="task_123", goal="YouTube Search")
    trace.add_span(Span(name="input", span_type=SpanType.INPUT, duration_ms=8.0))
    trace.add_span(Span(name="planning", span_type=SpanType.PLANNING, duration_ms=240.0))
    trace.add_span(Span(name="gpu_vision", span_type=SpanType.GPU, duration_ms=185.0))
    trace.finish()

    assert trace.total_duration_ms >= 0.0
    breakdown = trace.get_breakdown()
    assert "input" in breakdown
    assert "planning" in breakdown
    assert "gpu" in breakdown
    assert breakdown["gpu"] == 185.0


def test_tracer_context_manager():
    tracer = ProfileTracer()
    trace = tracer.start_trace("task_cm", goal="Test Span")

    with tracer.span("test_step", SpanType.TOOL):
        time.sleep(0.005)

    completed = tracer.end_trace("task_cm")
    assert completed is not None
    assert len(completed.spans) == 1
    assert completed.spans[0].name == "test_step"
    assert completed.spans[0].duration_ms > 0.0


@pytest.mark.asyncio
async def test_tracer_async_context_manager():
    tracer = ProfileTracer()
    tracer.start_trace("async_task")

    async with tracer.async_span("async_step", SpanType.GPU):
        await asyncio.sleep(0.005)

    completed = tracer.end_trace("async_task")
    assert completed is not None
    assert len(completed.spans) == 1
    assert completed.spans[0].span_type == SpanType.GPU


def test_report_generation():
    trace = TaskProfileTrace(task_id="task_rep", goal="Find Chrome Icon")
    trace.add_span(Span(name="Input processing", span_type=SpanType.INPUT, duration_ms=8.0))
    trace.add_span(Span(name="Vision", span_type=SpanType.GPU, duration_ms=185.0))
    trace.finish()

    report_str = render_ascii_report(trace)
    assert "R.I.O. PERFORMANCE TRACE" in report_str
    assert "Find Chrome Icon" in report_str
    assert "TOTAL" in report_str

    json_str = to_json_report(trace)
    assert '"task_id": "task_rep"' in json_str
