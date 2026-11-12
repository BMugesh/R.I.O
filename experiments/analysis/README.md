# R.I.O. Public Sandbox Experimentation Guide

This directory contains reproducible evaluation scenarios, telemetry schemas, and metric-computation scripts for the isolated R.I.O. public research demonstrator (`apps/public-demo`).

## Directory Structure

- `scenarios/benchmark_scenarios.json`: Benchmark task suite covering normal approval, human rejection containment, pause/resume interrupts, cancellation, and adversarial boundary stress tests.
- `scenarios/run_scenarios.py`: Executes all scenarios in-process against `apps/public-demo` without modifying or touching the private local R.I.O. runtime.
- `metrics/telemetry_schema.json`: JSON Schema describing the collected research telemetry format.
- `analysis/analyze_metrics.py`: Computes gate enforcement rate, rejection containment rate, boundary isolation rate, invalid action rejection rate, and trust calibration coverage.

## Running Reproducibly

From the repository root:

```powershell
python experiments/scenarios/run_scenarios.py
python experiments/analysis/analyze_metrics.py
```

Outputs are written to `experiments/metrics/sample_run_metrics.json` and `experiments/metrics/summary_report.json`.
