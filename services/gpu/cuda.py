"""Hardware GPU and CUDA detection for R.I.O. (Milestone 4)."""

from dataclasses import dataclass
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, Optional

# Guard against OpenMP multiple DLL collision on Windows
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

logger = logging.getLogger("rio.gpu.cuda")


@dataclass
class GPUInfo:
    """Detailed hardware and runtime specifications for detected GPU."""
    available: bool = False
    device: str = "None"
    device_id: int = 0
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    vram_used_mb: int = 0
    cuda_version: Optional[str] = None
    pytorch_version: Optional[str] = None
    cudnn_version: Optional[str] = None
    gpu_utilization_pct: float = 0.0
    temperature_c: Optional[float] = None
    power_draw_w: Optional[float] = None
    backend: str = "none"  # "torch_cuda", "nvidia_smi", "simulated", "none"
    status: str = "OFFLINE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "device": self.device,
            "device_id": self.device_id,
            "vram_total_mb": self.vram_total_mb,
            "vram_free_mb": self.vram_free_mb,
            "vram_used_mb": self.vram_used_mb,
            "cuda_version": self.cuda_version,
            "pytorch_version": self.pytorch_version,
            "cudnn_version": self.cudnn_version,
            "gpu_utilization_pct": self.gpu_utilization_pct,
            "temperature_c": self.temperature_c,
            "power_draw_w": self.power_draw_w,
            "backend": self.backend,
            "status": self.status,
        }


def _query_nvidia_smi() -> Optional[Dict[str, Any]]:
    """Query physical NVIDIA GPU hardware via nvidia-smi CLI."""
    if not shutil.which("nvidia-smi"):
        return None

    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3.0,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 6:
                name = parts[0]
                total = int(float(parts[1]))
                free = int(float(parts[2]))
                used = int(float(parts[3]))
                util = float(parts[4])
                temp = float(parts[5])
                power = float(parts[6]) if len(parts) > 6 and parts[6] != "[N/A]" else None
                return {
                    "device": name,
                    "vram_total_mb": total,
                    "vram_free_mb": free,
                    "vram_used_mb": used,
                    "utilization": util,
                    "temperature": temp,
                    "power": power,
                }
    except Exception as e:
        logger.debug(f"nvidia-smi query error: {e}")
    return None


def detect_gpu() -> Dict[str, Any]:
    """Detect GPU hardware and CUDA runtime environment."""
    info = GPUInfo()

    # Step 1: Check PyTorch CUDA runtime
    has_torch_cuda = False
    try:
        import torch
        info.pytorch_version = getattr(torch, "__version__", None)
        if torch.cuda.is_available():
            has_torch_cuda = True
            info.available = True
            info.backend = "torch_cuda"
            info.status = "READY"
            info.device = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info.vram_total_mb = int(props.total_memory // (1024 ** 2))
            info.cuda_version = getattr(torch.version, "cuda", None)
            if hasattr(torch.backends, "cudnn") and torch.backends.cudnn.is_available():
                info.cudnn_version = str(torch.backends.cudnn.version())

            # Current VRAM memory allocations
            info.vram_used_mb = int(torch.cuda.memory_allocated(0) // (1024 ** 2))
            info.vram_free_mb = max(0, info.vram_total_mb - info.vram_used_mb)
    except Exception as e:
        logger.debug(f"PyTorch CUDA detection error: {e}")

    # Step 2: If PyTorch CUDA is not active or for live telemetry, query nvidia-smi
    smi_data = _query_nvidia_smi()
    if smi_data:
        if not has_torch_cuda:
            # Physical GPU is present and detected!
            info.available = True
            info.device = smi_data["device"]
            info.vram_total_mb = smi_data["vram_total_mb"]
            info.vram_free_mb = smi_data["vram_free_mb"]
            info.vram_used_mb = smi_data["vram_used_mb"]
            info.backend = "nvidia_smi"
            info.status = "READY"

        info.gpu_utilization_pct = smi_data["utilization"]
        info.temperature_c = smi_data["temperature"]
        info.power_draw_w = smi_data["power"]
        if not info.cuda_version:
            info.cuda_version = "Driver CUDA"

    if not info.available:
        info.status = "OFFLINE"
        info.backend = "none"

    return info.to_dict()


def get_gpu_info() -> GPUInfo:
    """Return strongly typed GPUInfo instance."""
    data = detect_gpu()
    return GPUInfo(**data)


def is_cuda_available() -> bool:
    """Return True if GPU hardware / CUDA is ready for computation."""
    data = detect_gpu()
    return bool(data.get("available", False))
