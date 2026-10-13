"""World State Representation for R.I.O. (Milestone 5).

Provides a timestamped, partially observable state snapshot of the environment,
devices, open windows, active processes, and runtime status.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorldState(BaseModel):
    """Observable operational environment state informing autonomous decisions."""

    devices: Dict[str, Any] = Field(default_factory=dict)
    active_apps: List[str] = Field(default_factory=list)
    browser_state: Dict[str, Any] = Field(default_factory=dict)
    files: Dict[str, Any] = Field(default_factory=dict)
    runtime_state: str = "active"
    network_online: bool = True
    resource_state: Dict[str, Any] = Field(default_factory=dict)
    active_tasks: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)

    def update_resource(self, ram_mb: float, vram_mb: float) -> None:
        """Update system resource telemetry."""
        self.resource_state = {
            "ram_available_mb": ram_mb,
            "vram_free_mb": vram_mb,
            "updated_at": time.time(),
        }

    def update_task_status(self, task_id: str, status: str) -> None:
        """Update active tasks list."""
        if status in ("completed", "failed", "cancelled"):
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
        else:
            if task_id not in self.active_tasks:
                self.active_tasks.append(task_id)

    @classmethod
    def capture_current_snapshot(cls, active_tasks: Optional[List[str]] = None) -> "WorldState":
        """Capture a live physical snapshot of the operating system, windows, and resources."""
        import psutil
        from runtime.app_controller import UniversalAppController

        active_windows = UniversalAppController.enumerate_windows()
        active_apps = list({w.title for w in active_windows if w.title and getattr(w, "is_visible", True)})

        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)

        battery = psutil.sensors_battery()
        battery_info = None
        if battery:
            battery_info = {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
            }

        vram_mb = 0.0
        try:
            from services.gpu.cuda import get_gpu_info
            gpu_info = get_gpu_info()
            if gpu_info.get("available"):
                vram_mb = float(gpu_info.get("vram_total_mb", 0) - gpu_info.get("vram_used_mb", 0))
        except Exception:
            pass

        return cls(
            active_apps=active_apps,
            browser_state={"open": any("chrome" in a.lower() or "edge" in a.lower() or "firefox" in a.lower() for a in active_apps)},
            network_online=True,
            resource_state={
                "ram_available_mb": round(mem.available / (1024 * 1024), 1),
                "ram_used_percent": mem.percent,
                "cpu_percent": cpu_percent,
                "vram_free_mb": vram_mb,
                "battery": battery_info,
            },
            active_tasks=list(active_tasks or []),
            timestamp=time.time(),
        )
