"""Unit tests for R.I.O. M5.8 Observability & Execution Traces."""

import pytest
pytestmark = [pytest.mark.unit]

from services.observability.execution_trace import ExecutionTrace
from services.observability.metrics_collector import MetricsCollector


def test_execution_trace_creation():
    trace = ExecutionTrace(
        task_id="t1",
        goal="Compare GPUs",
        planning_time_ms=45.0,
        execution_time_ms=450.0,
        verification_time_ms=30.0,
        total_duration_ms=525.0,
        node_count=4,
        parallel_stages=3,
        max_concurrency=2,
        agents_used=["research_agent", "computer_agent", "document_agent"],
        models_used=["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        compute_targets=["gpu", "cpu"],
        final_status="completed",
    )

    assert trace.task_id == "t1"
    assert trace.node_count == 4
    assert trace.max_concurrency == 2
    assert "gpu" in trace.compute_targets


def test_metrics_collector_aggregation():
    collector = MetricsCollector(max_history=10)

    t1 = ExecutionTrace(
        task_id="t1",
        goal="Goal 1",
        planning_time_ms=10.0,
        execution_time_ms=100.0,
        total_duration_ms=110.0,
        max_concurrency=2,
        final_status="completed",
    )
    t2 = ExecutionTrace(
        task_id="t2",
        goal="Goal 2",
        planning_time_ms=20.0,
        execution_time_ms=200.0,
        total_duration_ms=220.0,
        max_concurrency=1,
        final_status="failed",
    )

    collector.record_trace(t1)
    collector.record_trace(t2)

    summary = collector.get_summary()
    assert summary["total_tasks"] == 2
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["avg_concurrency"] == 1.5
    assert summary["avg_duration_ms"] == 165.0
