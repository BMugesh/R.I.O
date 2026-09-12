"""Test CPU Executor for local processing in R.I.O. (Milestone 4)."""

import pytest
from services.compute.cpu_executor import CPUExecutor
from services.compute.workload import ComputeTarget, Workload


@pytest.mark.asyncio
async def test_cpu_executor_basic():
    executor = CPUExecutor()
    workload = Workload(type="general_compute", input=lambda: 10 + 20)
    res = await executor.execute(workload)

    assert res.success
    assert res.target_used == ComputeTarget.CPU
    assert res.output == 30
    assert res.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_cpu_executor_handler():
    executor = CPUExecutor()
    executor.register_handler("general_compute", lambda x: f"Processed {x}")

    workload = Workload(type="general_compute", input="file.txt")
    res = await executor.execute(workload)

    assert res.success
    assert res.output == "Processed file.txt"


@pytest.mark.asyncio
async def test_cpu_executor_error_handling():
    executor = CPUExecutor()

    def faulty(x):
        raise ValueError("Intentional CPU error")

    executor.register_handler("general_compute", faulty)
    workload = Workload(type="general_compute", input="test")
    res = await executor.execute(workload)

    assert not res.success
    assert "Intentional CPU error" in str(res.error)
