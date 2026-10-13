"""Test GPU hardware detection and health monitor for R.I.O. (Milestone 4)."""
import pytest
pytestmark = pytest.mark.gpu



import pytest
from services.gpu.cuda import GPUInfo, detect_gpu, get_gpu_info, is_cuda_available
from services.gpu.health import GPUHealthMonitor, get_gpu_health_monitor
from services.gpu.memory import VRAMManager, get_vram_manager


def test_gpu_detection():
    """Verify GPU detection returns structured hardware information."""
    info = detect_gpu()
    assert "available" in info
    assert "device" in info
    assert "status" in info
    assert "vram_total_mb" in info

    if info["available"]:
        assert info["vram_total_mb"] > 0
        assert info["status"] in ("READY", "ONLINE")
        assert len(info["device"]) > 0


def test_gpu_info_model():
    """Verify GPUInfo typed dataclass serialization."""
    gpu_info = get_gpu_info()
    assert isinstance(gpu_info, GPUInfo)
    data = gpu_info.to_dict()
    assert data["device"] == gpu_info.device
    assert "vram_free_mb" in data


def test_vram_manager_budget():
    """Verify VRAMManager enforces the 6 GB ceiling and headroom."""
    mgr = VRAMManager(max_vram_mb=6144)
    assert mgr.total_vram_mb == 6144
    assert mgr.safety_headroom_mb == 800
    assert mgr.free_vram_mb == 6144 - 800

    # Allocate 1000 MB
    assert mgr.can_allocate(1000)
    assert mgr.allocate("vision_model", 1000)
    assert mgr.allocated_vram_mb == 1000
    assert mgr.free_vram_mb == (6144 - 800 - 1000)

    # Attempt to allocate more than remaining free VRAM
    assert not mgr.can_allocate(5000)
    assert not mgr.allocate("giant_llm", 5000)

    # Release allocation
    assert mgr.release("vision_model")
    assert mgr.allocated_vram_mb == 0
    assert mgr.free_vram_mb == 6144 - 800


def test_gpu_health_monitor_rendering():
    """Verify health monitor renders ASCII and Rich status cards."""
    monitor = get_gpu_health_monitor()
    health = monitor.get_health()
    assert "vram_total_gb" in health
    assert "compute_state" in health

    ascii_card = monitor.render_ascii_card()
    assert "R.I.O. GPU STATUS" in ascii_card
    assert "VRAM" in ascii_card
    assert "CUDA" in ascii_card
