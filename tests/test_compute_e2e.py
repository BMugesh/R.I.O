"""End-to-End Tests for Compute Fabric & Profiling in R.I.O. (Milestone 4)."""

import pytest
from packages.schemas.chat import ChatRequest
from services.orchestrator.orchestrator import RIOOrchestrator


@pytest.mark.asyncio
async def test_e2e_compute_fabric_chat_with_trace():
    orchestrator = RIOOrchestrator()
    request = ChatRequest(
        message="What is the time complexity of quicksort?",
        developer_mode=True,
    )

    response = await orchestrator.process_chat(request)

    assert response.status == "completed"
    assert response.developer_trace is not None

    dev_trace = response.developer_trace
    assert dev_trace.compute_trace is not None
    assert "spans" in dev_trace.compute_trace
    assert "breakdown_ms" in dev_trace.compute_trace

    span_names = [s["name"] for s in dev_trace.compute_trace["spans"]]
    assert "input_processing" in span_names
    assert "intent_detection" in span_names
    assert "response_synthesis" in span_names


@pytest.mark.asyncio
async def test_e2e_compute_fabric_task_execution():
    orchestrator = RIOOrchestrator()
    request = ChatRequest(
        message="Open Chrome on my laptop",
        developer_mode=True,
    )

    response = await orchestrator.process_chat(request)
    assert response.developer_trace is not None
    assert response.developer_trace.compute_trace is not None

    trace_data = response.developer_trace.compute_trace
    assert trace_data["total_duration_ms"] >= 0.0
