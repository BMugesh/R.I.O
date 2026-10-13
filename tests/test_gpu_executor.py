"""Test GPU Executor and persistent model workers (Milestone 4)."""
import pytest
pytestmark = pytest.mark.gpu



import pytest
from services.compute.gpu_executor import GPUExecutor
from services.compute.workload import ComputeTarget, Workload


@pytest.mark.asyncio
async def test_gpu_executor_execution():
    executor = GPUExecutor(device="cuda:0")
    executor.register_worker("embedding", lambda x: [0.1, 0.2, 0.3])

    workload = Workload(type="embedding", input="hello world", estimated_memory_mb=100)
    res = await executor.execute(workload)

    assert res.success
    assert res.target_used == ComputeTarget.GPU
    assert res.output == [0.1, 0.2, 0.3]
    assert res.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_gpu_executor_unregistered_worker():
    executor = GPUExecutor()
    workload = Workload(type="quantum_simulation", input=None)
    res = await executor.execute(workload)

    assert not res.success
    assert "No GPU worker registered" in str(res.error)


@pytest.mark.asyncio
async def test_gpu_executor_vram_limit():
    executor = GPUExecutor()
    executor.register_worker("embedding", lambda x: [0.0])

    # Request more VRAM than the 6 GB ceiling
    workload = Workload(type="embedding", input="test", estimated_memory_mb=10000)
    res = await executor.execute(workload)

    assert not res.success
    assert "VRAM ceiling reached" in str(res.error)
