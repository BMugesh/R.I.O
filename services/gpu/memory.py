"""VRAM Memory Management and Budget Tracking for R.I.O. (Milestone 4).

Guards the 6 GB physical VRAM ceiling of the NVIDIA RTX 4050 Laptop GPU,
preventing Out-Of-Memory (OOM) exceptions and allocating memory per model.
"""

from dataclasses import dataclass, field
import logging
import threading
from typing import Any, Dict, Optional

from services.gpu.cuda import detect_gpu

logger = logging.getLogger("rio.gpu.memory")


@dataclass
class ModelAllocation:
    model_name: str
    allocated_mb: int
    loaded_at: float


class VRAMManager:
    """Thread-safe VRAM budget manager and safety allocator."""

    # Default VRAM allocations tailored for 6 GB VRAM ceiling
    DEFAULT_SAFETY_HEADROOM_MB = 800  # Reserved for PyTorch context and OS display

    def __init__(self, max_vram_mb: Optional[int] = None):
        self._lock = threading.Lock()
        gpu_info = detect_gpu()
        self.total_vram_mb = max_vram_mb or (gpu_info.get("vram_total_mb") or 6141)
        self.safety_headroom_mb = self.DEFAULT_SAFETY_HEADROOM_MB
        self._allocations: Dict[str, int] = {}

    @property
    def allocated_vram_mb(self) -> int:
        """Total VRAM actively reserved by loaded models."""
        with self._lock:
            return sum(self._allocations.values())

    @property
    def free_vram_mb(self) -> int:
        """Available VRAM remaining for new allocations."""
        with self._lock:
            available = self.total_vram_mb - sum(self._allocations.values()) - self.safety_headroom_mb
            return max(0, available)

    def can_allocate(self, required_mb: int) -> bool:
        """Check if requested memory fits within safe VRAM limits."""
        if required_mb <= 0:
            return True
        return self.free_vram_mb >= required_mb

    def allocate(self, model_name: str, mb: int) -> bool:
        """Reserve VRAM for a model. Returns True if allocated, False if insufficient."""
        with self._lock:
            if model_name in self._allocations:
                # Already allocated
                return True

            available = self.total_vram_mb - sum(self._allocations.values()) - self.safety_headroom_mb
            if mb > available:
                logger.warning(
                    f"VRAM allocation failed for '{model_name}': requested {mb} MB, "
                    f"but only {available} MB available (Total: {self.total_vram_mb} MB, "
                    f"Headroom: {self.safety_headroom_mb} MB)."
                )
                return False

            self._allocations[model_name] = mb
            logger.info(f"VRAM allocated: '{model_name}' -> {mb} MB. Total active: {sum(self._allocations.values())} MB.")
            return True

    def release(self, model_name: str) -> bool:
        """Release reserved VRAM for a model."""
        with self._lock:
            if model_name in self._allocations:
                freed = self._allocations.pop(model_name)
                logger.info(f"VRAM released: '{model_name}' ({freed} MB).")
                return True
            return False

    def clear(self) -> None:
        """Clear all active model allocations."""
        with self._lock:
            self._allocations.clear()

    def get_status(self) -> Dict[str, Any]:
        """Summary of current VRAM usage."""
        with self._lock:
            allocated = sum(self._allocations.values())
            usable_free = max(0, self.total_vram_mb - allocated - self.safety_headroom_mb)
            return {
                "total_vram_mb": self.total_vram_mb,
                "allocated_vram_mb": allocated,
                "safety_headroom_mb": self.safety_headroom_mb,
                "usable_free_mb": usable_free,
                "active_models": dict(self._allocations),
            }


# Global singleton VRAMManager
_vram_manager: Optional[VRAMManager] = None


def get_vram_manager() -> VRAMManager:
    global _vram_manager
    if _vram_manager is None:
        _vram_manager = VRAMManager()
    return _vram_manager
