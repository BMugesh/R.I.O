"""Compute detector wrapping GPU and hardware telemetry for ComputeRouter."""

from typing import Any, Dict

from services.gpu.cuda import detect_gpu, is_cuda_available
from services.gpu.memory import get_vram_manager


class ComputeDetector:
    """Provides ComputeRouter with hardware readiness and live capacity."""

    def __init__(self):
        self.vram_manager = get_vram_manager()

    def get_hardware_status(self) -> Dict[str, Any]:
        raw_gpu = detect_gpu()
        vram = self.vram_manager.get_status()

        return {
            "gpu_available": raw_gpu.get("available", False),
            "device": raw_gpu.get("device", "None"),
            "backend": raw_gpu.get("backend", "none"),
            "vram_total_mb": raw_gpu.get("vram_total_mb", 0),
            "vram_free_mb": vram.get("usable_free_mb", raw_gpu.get("vram_free_mb", 0)),
            "vram_allocated_mb": vram.get("allocated_vram_mb", 0),
            "status": raw_gpu.get("status", "OFFLINE"),
        }

    def is_gpu_ready(self) -> bool:
        return is_cuda_available()

    def get_free_vram_mb(self) -> int:
        return self.vram_manager.free_vram_mb
