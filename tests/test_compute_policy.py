"""Test Compute Routing Policy and rules (Milestone 4)."""

import pytest
from services.compute.policy import ComputePolicy, DEFAULT_COMPUTE_POLICY
from services.compute.workload import ComputeTarget, Workload


def test_default_policy_mappings():
    policy = ComputePolicy()
    assert policy.get_preferred_target("embedding") == "GPU"
    assert policy.get_preferred_target("vision_inference") == "GPU"
    assert policy.get_preferred_target("complex_reasoning") == "REMOTE"
    assert policy.get_preferred_target("browser_control") == "CPU"
    assert policy.get_preferred_target("device_control") == "CPU"


def test_vision_prefers_gpu():
    policy = ComputePolicy()
    workload = Workload(type="vision_inference", input=None, estimated_memory_mb=500)
    decision = policy.evaluate(workload, gpu_available=True, free_vram_mb=4000)

    assert decision.target == ComputeTarget.GPU
    assert decision.fallback == ComputeTarget.CPU


def test_gpu_unavailable_falls_back_to_cpu():
    policy = ComputePolicy()
    workload = Workload(type="vision_inference", input=None, estimated_memory_mb=500)
    decision = policy.evaluate(workload, gpu_available=False, free_vram_mb=0)

    assert decision.target == ComputeTarget.CPU


def test_vram_insufficient_falls_back_to_cpu():
    policy = ComputePolicy()
    workload = Workload(type="embedding", input="text", estimated_memory_mb=2000)
    decision = policy.evaluate(workload, gpu_available=True, free_vram_mb=800)

    assert decision.target == ComputeTarget.CPU


def test_privacy_local_only_forbids_remote():
    """Verify privacy='local_only' NEVER allows remote routing."""
    policy = ComputePolicy()
    # Normally complex_reasoning routes to REMOTE
    workload = Workload(
        type="complex_reasoning",  # type: ignore
        input="private local document",
        privacy="local_only",
    )
    decision = policy.evaluate(workload, gpu_available=True, free_vram_mb=4000)

    # Must be GPU or CPU, NEVER REMOTE
    assert decision.target in {ComputeTarget.GPU, ComputeTarget.CPU}
    assert decision.target != ComputeTarget.REMOTE
    assert decision.fallback != ComputeTarget.REMOTE
