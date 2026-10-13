"""Resource Report Generator and Persistence Engine (Milestone 4.5).

Produces formatted terminal summary tables and persists structured JSON reports
to benchmarks/reports/test_resources.json and test_resources_latest.json.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.test_governor.resource_tracker import ResourceSnapshot

logger = logging.getLogger("rio.test_governor.report")


class TestResourceReporter:
    """Formats and writes test resource reports."""

    __test__ = False

    def __init__(self, reports_dir: Optional[Path] = None):
        self.reports_dir = reports_dir or Path("benchmarks") / "reports"

    def format_terminal_box(
        self,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        start_snap: ResourceSnapshot,
        peak_metrics: Dict[str, Any],
        end_snap: ResourceSnapshot,
        leak_summary: Dict[str, Any],
    ) -> str:
        """Format double-line ASCII table matching R.I.O. specification."""
        start_ram_gb = start_snap.process_rss_mb / 1024.0
        peak_ram_gb = peak_metrics.get("peak_rss_mb", start_snap.process_rss_mb) / 1024.0
        end_ram_gb = end_snap.process_rss_mb / 1024.0

        start_vram_gb = (start_snap.gpu_used_mb or 0.0) / 1024.0
        peak_vram_gb = (peak_metrics.get("peak_vram_mb", 0.0)) / 1024.0
        end_vram_gb = (end_snap.gpu_used_mb or 0.0) / 1024.0

        lines = [
            "╔══════════════════════════════════════════════╗",
            "║        R.I.O. TEST RESOURCE REPORT          ║",
            "╠══════════════════════════════════════════════╣",
            f"║ Tests                 {total_tests:<22} ║",
            f"║ Passed                {passed_tests:<22} ║",
            f"║ Failed                {failed_tests:<22} ║",
            "║                                              ║",
            f"║ RAM Start             {start_ram_gb:4.1f} GB                ║",
            f"║ RAM Peak              {peak_ram_gb:4.1f} GB                ║",
            f"║ RAM End               {end_ram_gb:4.1f} GB                ║",
            "║                                              ║",
            f"║ VRAM Start            {start_vram_gb:4.1f} GB                ║",
            f"║ VRAM Peak             {peak_vram_gb:4.1f} GB                ║",
            f"║ VRAM End              {end_vram_gb:4.1f} GB                ║",
            "║                                              ║",
            f"║ Threads Start         {start_snap.thread_count:<22} ║",
            f"║ Threads Peak          {peak_metrics.get('peak_threads', start_snap.thread_count):<22} ║",
            f"║ Threads End           {end_snap.thread_count:<22} ║",
            "║                                              ║",
            f"║ Processes Start       {start_snap.process_count:<22} ║",
            f"║ Processes Peak        {peak_metrics.get('peak_processes', start_snap.process_count):<22} ║",
            f"║ Processes End         {end_snap.process_count:<22} ║",
            "║                                              ║",
            f"║ Async Tasks Start     {start_snap.asyncio_task_count:<22} ║",
            f"║ Async Tasks Peak      {peak_metrics.get('peak_tasks', start_snap.asyncio_task_count):<22} ║",
            f"║ Async Tasks End       {end_snap.asyncio_task_count:<22} ║",
            "╚══════════════════════════════════════════════╝",
            "",
            "RESOURCE LEAK CHECK",
            "",
        ]

        has_leaks = any(leak_summary.values())
        if not has_leaks:
            lines.extend([
                "✓ RAM recovered",
                "✓ VRAM recovered",
                "✓ Threads recovered",
                "✓ Processes recovered",
                "✓ Async tasks recovered",
                "✓ Browser instances closed",
                "✓ GPU workers shut down correctly",
                "✓ Background services terminated",
            ])
        else:
            for category, items in leak_summary.items():
                if items:
                    lines.append(f"⚠ LEAK DETECTED in {category}: {items}")

        return "\n".join(lines)

    def persist_report(self, report_data: Dict[str, Any]) -> Path:
        """Persist structured JSON report."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reports_dir / "test_resources.json"
        latest_path = self.reports_dir / "test_resources_latest.json"

        content = json.dumps(report_data, indent=2)
        report_path.write_text(content, encoding="utf-8")
        latest_path.write_text(content, encoding="utf-8")

        logger.info(f"Test resource reports written to {report_path}")
        return report_path
