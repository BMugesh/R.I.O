"""Resource Policy and Thresholds for R.I.O. Test Execution (Milestone 4.5).

Enforces strict memory, GPU, process, and thread boundaries for test execution
on a 16 GB RAM / 6 GB RTX 4050 Windows laptop.
"""

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class TestResourcePolicy:
    """Configurable resource thresholds and boundaries for testing."""

    __test__ = False

    min_available_ram_mb: int = 1024
    ram_warning_percent: float = 88.0
    ram_critical_percent: float = 95.0

    gpu_safety_headroom_mb: int = 800
    max_gpu_utilization_percent: float = 90.0

    max_test_workers: int = 1
    max_browser_instances: int = 2

    @classmethod
    def from_env(cls) -> "TestResourcePolicy":
        """Load policy overrides from environment variables."""
        return cls(
            min_available_ram_mb=int(os.getenv("RIO_TEST_MIN_RAM_MB", "1024")),
            ram_warning_percent=float(os.getenv("RIO_TEST_RAM_WARNING_PERCENT", "88.0")),
            ram_critical_percent=float(os.getenv("RIO_TEST_RAM_CRITICAL_PERCENT", "95.0")),
            gpu_safety_headroom_mb=int(os.getenv("RIO_TEST_GPU_HEADROOM_MB", "800")),
            max_gpu_utilization_percent=float(os.getenv("RIO_TEST_MAX_GPU_UTIL", "90.0")),
            max_test_workers=int(os.getenv("RIO_TEST_MAX_WORKERS", "1")),
            max_browser_instances=int(os.getenv("RIO_TEST_MAX_BROWSERS", "2")),
        )

    def is_ram_critical(self, available_mb: float, total_mb: float) -> bool:
        """Check if system RAM is critically exhausted."""
        if available_mb < self.min_available_ram_mb:
            return True
        if total_mb > 0:
            used_percent = ((total_mb - available_mb) / total_mb) * 100.0
            if used_percent >= self.ram_critical_percent:
                return True
        return False

    def is_ram_warning(self, available_mb: float, total_mb: float) -> bool:
        """Check if system RAM has entered caution/warning territory."""
        if total_mb > 0:
            used_percent = ((total_mb - available_mb) / total_mb) * 100.0
            return used_percent >= self.ram_warning_percent
        return False

    def is_vram_safe(self, free_vram_mb: float) -> bool:
        """Check if VRAM satisfies minimum safety headroom (default 800 MB)."""
        return free_vram_mb >= self.gpu_safety_headroom_mb

    def get_vram_status(self, free_vram_mb: float, total_vram_mb: float) -> str:
        """Classify VRAM status based on 6GB allocation bands:
        0 - 4.8 GB used -> SAFE
        4.8 - 5.3 GB used -> CAUTION
        5.3 - 6.0 GB used -> CRITICAL
        """
        if total_vram_mb <= 0:
            return "UNKNOWN"
        used_mb = total_vram_mb - free_vram_mb
        if used_mb >= 5300 or free_vram_mb < self.gpu_safety_headroom_mb:
            return "CRITICAL"
        elif used_mb >= 4800:
            return "CAUTION"
        return "SAFE"
