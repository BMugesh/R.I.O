"""GPU Health Monitoring and Telemetry for R.I.O. (Milestone 4)."""

import logging
from typing import Any, Dict, Optional

from services.gpu.cuda import detect_gpu
from services.gpu.memory import get_vram_manager

logger = logging.getLogger("rio.gpu.health")

try:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class GPUHealthMonitor:
    """Monitors live thermals, utilization, memory, and operational readiness."""

    def __init__(self):
        self.vram_manager = get_vram_manager()

    def get_health(self) -> Dict[str, Any]:
        """Poll and return current health metrics."""
        raw_gpu = detect_gpu()
        vram_stat = self.vram_manager.get_status()

        is_avail = raw_gpu.get("available", False)
        total_vram = raw_gpu.get("vram_total_mb", 6141)
        used_vram = raw_gpu.get("vram_used_mb", 0) + vram_stat.get("allocated_vram_mb", 0)
        free_vram = max(0, total_vram - used_vram)

        return {
            "available": is_avail,
            "device": raw_gpu.get("device", "None"),
            "status": "READY" if is_avail else "OFFLINE",
            "compute_state": "GPU ACTIVE" if is_avail else "CPU FALLBACK",
            "vram_total_gb": round(total_vram / 1024.0, 1),
            "vram_used_gb": round(used_vram / 1024.0, 1),
            "vram_free_gb": round(free_vram / 1024.0, 1),
            "vram_total_mb": total_vram,
            "vram_used_mb": used_vram,
            "vram_free_mb": free_vram,
            "utilization_pct": raw_gpu.get("gpu_utilization_pct", 0.0),
            "temperature_c": raw_gpu.get("temperature_c"),
            "power_draw_w": raw_gpu.get("power_draw_w"),
            "cuda_version": raw_gpu.get("cuda_version", "N/A"),
            "active_models": vram_stat.get("active_models", {}),
        }

    def render_ascii_card(self) -> str:
        """Render clean ASCII status card."""
        h = self.get_health()
        dev_short = h['device'].replace("NVIDIA GeForce ", "").replace(" Laptop GPU", " Laptop")
        if len(dev_short) > 18:
            dev_short = dev_short[:18]

        vram_str = f"{h['vram_used_gb']} / {h['vram_total_gb']} GB"
        util_str = f"{int(h['utilization_pct'])}%"
        temp_str = f"{int(h['temperature_c'])}°C" if h['temperature_c'] is not None else "N/A"
        cuda_str = "READY" if h['available'] else "OFFLINE"
        comp_str = h['compute_state']

        lines = [
            "╭──────────────────────────────╮",
            "│       R.I.O. GPU STATUS      │",
            "├──────────────────────────────┤",
            f"│ GPU       {dev_short:<18} │",
            f"│ VRAM      {vram_str:<18} │",
            f"│ Util      {util_str:<18} │",
            f"│ Temp      {temp_str:<18} │",
            f"│ CUDA      {cuda_str:<18} │",
            f"│ Compute   {comp_str:<18} │",
            "╰──────────────────────────────╯",
        ]
        return "\n".join(lines)

    def render_rich_card(self) -> Any:
        """Render Rich panel for terminal visualization."""
        if not HAS_RICH:
            return self.render_ascii_card()

        h = self.get_health()
        dev_name = h['device'].replace("NVIDIA GeForce ", "")
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan", justify="left")
        table.add_column(style="white", justify="left")

        table.add_row("Device", dev_name)
        table.add_row("VRAM", f"{h['vram_used_gb']} GB / {h['vram_total_gb']} GB ({h['vram_free_gb']} GB free)")
        table.add_row("Utilization", f"{h['utilization_pct']}%")
        if h['temperature_c'] is not None:
            table.add_row("Temperature", f"{h['temperature_c']}°C")
        if h['power_draw_w'] is not None:
            table.add_row("Power Draw", f"{h['power_draw_w']} W")
        table.add_row("CUDA", "[bold green]READY[/bold green]" if h['available'] else "[dim]OFFLINE[/dim]")
        table.add_row("Compute Mode", f"[bold green]{h['compute_state']}[/bold green]")

        return Panel(
            table,
            title="[bold green]R.I.O. GPU ACCELERATOR STATUS[/bold green]",
            border_style="green" if h['available'] else "yellow",
            padding=(1, 2),
        )


_monitor: Optional[GPUHealthMonitor] = None


def get_gpu_health_monitor() -> GPUHealthMonitor:
    global _monitor
    if _monitor is None:
        _monitor = GPUHealthMonitor()
    return _monitor
