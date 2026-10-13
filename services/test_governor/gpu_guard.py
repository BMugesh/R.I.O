"""GPU VRAM Safety Guard for R.I.O. Test Infrastructure (Milestone 4.5).

Protects the 6 GB RTX 4050 ceiling by enforcing the 800 MB safety headroom,
validating allocation budgets, and providing explicit GPU memory reclamation.
"""

import gc
import logging
from typing import Any, Dict, Optional

try:
    import torch
except ImportError:
    torch = None

from services.gpu.cuda import detect_gpu
from services.gpu.memory import get_vram_manager
from services.test_governor.policy import TestResourcePolicy

logger = logging.getLogger("rio.test_governor.gpu")


class GPUVRAMCriticalError(RuntimeError):
    """Raised when GPU VRAM headroom is breached or in CRITICAL state."""
    pass


class GPUGuard:
    """Oversees GPU VRAM allocation safety and test model eviction."""

    def __init__(self, policy: Optional[TestResourcePolicy] = None):
        self.policy = policy or TestResourcePolicy.from_env()
        self.vram_manager = get_vram_manager()

    def get_gpu_status(self) -> Dict[str, Any]:
        """Query current GPU VRAM allocation state."""
        info = detect_gpu()
        if not info.get("available"):
            return {"available": False, "status": "NO_GPU"}

        total_mb = float(info.get("vram_total_mb", 6141))
        free_mb = float(info.get("vram_free_mb", total_mb))
        used_mb = float(info.get("vram_used_mb", 0))

        status = self.policy.get_vram_status(free_vram_mb=free_mb, total_vram_mb=total_mb)
        return {
            "available": True,
            "device": info.get("device_name", "NVIDIA GPU"),
            "total_mb": total_mb,
            "free_mb": free_mb,
            "used_mb": used_mb,
            "status": status,
            "headroom_safe": self.policy.is_vram_safe(free_mb),
        }

    def check_vram_safety(self, required_mb: int = 100) -> None:
        """Verify GPU has safe capacity to run workload without OOM.
        Raises GPUVRAMCriticalError if headroom would be violated.
        """
        status = self.get_gpu_status()
        if not status.get("available"):
            return

        free_mb = status["free_mb"]
        total_mb = status["total_mb"]
        vram_state = status["status"]

        if vram_state == "CRITICAL" or not self.policy.is_vram_safe(free_mb - required_mb):
            logger.warning(
                f"[GPU GUARD] VRAM in {vram_state} state ({free_mb:.0f} MB free). "
                "Triggering immediate CUDA cache evacuation..."
            )
            self.cleanup_gpu()
            status_after = self.get_gpu_status()
            free_after = status_after.get("free_mb", 0)
            if not self.policy.is_vram_safe(free_after - required_mb):
                msg = (
                    f"GPU VRAM SAFETY STOP: Insufficient VRAM headroom ({free_after:.0f} MB free, "
                    f"headroom required {self.policy.gpu_safety_headroom_mb} MB). "
                    "Skipping or aborting GPU test to prevent CUDA OOM."
                )
                logger.error(msg)
                raise GPUVRAMCriticalError(msg)

    def cleanup_gpu(self, executor: Optional[Any] = None) -> None:
        """Evict loaded test models and release PyTorch CUDA caches."""
        if executor and hasattr(executor, "shutdown"):
            try:
                executor.shutdown()
            except Exception as e:
                logger.debug(f"Executor shutdown note: {e}")

        # 1. Force Python garbage collection
        gc.collect()

        # 2. Release PyTorch CUDA caching allocator
        if torch is not None and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
                logger.debug("PyTorch CUDA cache evacuated and synchronized.")
            except Exception as e:
                logger.debug(f"CUDA cache cleanup note: {e}")
