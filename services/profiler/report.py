"""Report generators for R.I.O. task performance profiling traces."""

import json
from typing import Any, Dict, Optional

from services.profiler.spans import TaskProfileTrace

try:
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def render_ascii_report(trace: TaskProfileTrace) -> str:
    """Generate clean, formatted ASCII performance breakdown for a task."""
    lines = []
    lines.append("R.I.O. PERFORMANCE TRACE")
    lines.append("─" * 40)
    
    label = trace.goal if trace.goal else f"Task: {trace.task_id}"
    lines.append(f"Task: {label}")
    lines.append("─" * 40)

    for span in trace.spans:
        duration_str = f"{span.duration_ms:,.1f} ms"
        lines.append(f"{span.name:<25} {duration_str:>12}")

    lines.append("─" * 40)
    total_str = f"{trace.total_duration_ms:,.1f} ms"
    lines.append(f"{'TOTAL':<25} {total_str:>12}")
    lines.append("─" * 40)

    # Optional compute breakdown
    breakdown = trace.get_breakdown()
    if any(k in breakdown for k in ["gpu", "cpu", "remote"]):
        lines.append("Compute Breakdown:")
        for target in ["gpu", "cpu", "remote"]:
            if target in breakdown:
                lines.append(f"  • {target.upper():<8}: {breakdown[target]:,.1f} ms")

    return "\n".join(lines)


def render_rich_table(trace: TaskProfileTrace) -> Any:
    """Render a Rich Table for terminal CLI output."""
    if not HAS_RICH:
        return render_ascii_report(trace)

    table = Table(
        title=f"R.I.O. Performance Trace: {trace.goal or trace.task_id}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Span / Operation", style="white")
    table.add_column("Type", style="dim")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Target / Notes", style="yellow")

    for s in trace.spans:
        target = s.metadata.get("target", "")
        table.add_row(
            s.name,
            s.span_type.value,
            f"{s.duration_ms:,.1f} ms",
            str(target) if target else "",
        )

    table.add_section()
    table.add_row(
        Text("TOTAL", style="bold red"),
        "-",
        Text(f"{trace.total_duration_ms:,.1f} ms", style="bold green"),
        "",
    )
    return table


def to_json_report(trace: TaskProfileTrace, indent: int = 2) -> str:
    """Serialize trace to JSON format."""
    return json.dumps(trace.to_dict(), indent=indent)
