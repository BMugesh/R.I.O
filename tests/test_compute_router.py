"""Test ComputeRouter execution, decisions, and fallbacks (Milestone 4)."""
import pytest
pytestmark = pytest.mark.unit



import pytest
from services.compute.cpu_executor import CPUExecutor
from services.compute.gpu_executor import GPUExecutor
from services.compute.policy import ComputePolicy
from services.compute.remote_executor import RemoteExecutor
from services.compute.router import ComputeRouter
from services.compute.workload import ComputeTarget, Workload


@pytest.mark.asyncio
async def test_compute_router_decide():
    router = ComputeRouter()
    workload = Workload(type="vision_inference", input="image_data")
    decision = router.decide(workload)

    assert decision.target in {ComputeTarget.GPU, ComputeTarget.CPU}


@pytest.mark.asyncio
async def test_compute_router_execute_cpu():
    router = ComputeRouter()
    router.register_cpu_handler("general_compute", lambda x: x * 2)

    workload = Workload(type="general_compute", input=21)
    res = await router.execute(workload)

    assert res.success
    assert res.target_used == ComputeTarget.CPU
    assert res.output == 42


@pytest.mark.asyncio
async def test_compute_router_fallback_to_cpu_on_gpu_failure():
    """Verify GPU execution failure triggers automatic CPU fallback."""
    cpu_exec = CPUExecutor()
    gpu_exec = GPUExecutor()

    # Define a GPU worker that intentionally raises an error
    def failing_gpu_worker(data):
        raise RuntimeError("CUDA Out of Core Error")

    # Define a CPU fallback handler that succeeds
    def working_cpu_handler(data):
        return f"CPU recovered: {data}"

    gpu_exec.register_worker("vision_inference", failing_gpu_worker)
    cpu_exec.register_handler("vision_inference", working_cpu_handler)

    router = ComputeRouter(cpu_executor=cpu_exec, gpu_executor=gpu_exec)

    workload = Workload(type="vision_inference", input="screenshot.png")
    res = await router.execute(workload)

    assert res.success
    assert res.fallback_triggered
    assert res.target_used == ComputeTarget.CPU
    assert "CPU recovered" in res.output


@pytest.mark.asyncio
async def test_privacy_local_only_enforcement():
    """Verify router guarantees local execution for local_only workloads."""
    router = ComputeRouter()
    workload = Workload(
        type="complex_reasoning",  # type: ignore
        input="confidential user info",
        privacy="local_only",
    )
    decision = router.decide(workload)
    assert decision.target != ComputeTarget.REMOTE
