"""Execute pre-deployment verification scenarios against apps/public-demo and record traceable telemetry."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PUBLIC_DEMO_DIR = ROOT_DIR / "apps" / "public-demo"
SCENARIOS_FILE = Path(__file__).resolve().parent / "benchmark_scenarios.json"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "experiments" / "metrics" / "sample_run_metrics.json"

if str(PUBLIC_DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(PUBLIC_DEMO_DIR))

os.environ["DEMO_STEP_DELAY_MS"] = "0"
os.environ["APP_ENV"] = "development"
os.environ.pop("GROQ_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
import main as demo_main  # noqa: E402
from security import rate_limiter  # noqa: E402
from session_store import session_store  # noqa: E402


def run_benchmark_suite(output_path: Path = DEFAULT_OUTPUT_FILE) -> dict:
    session_store.clear()
    rate_limiter.reset()

    with SCENARIOS_FILE.open("r", encoding="utf-8") as f:
        suite = json.load(f)

    app = demo_main.create_app()
    client = TestClient(app)

    run_records = []
    for spec in suite["scenarios"]:
        create_res = client.post(
            "/api/demo/sessions",
            json={"task": spec["task"], "scenario_id": spec.get("scenario_id")},
        )
        assert create_res.status_code == 201, f"Failed creating {spec['run_id']}: {create_res.text}"
        state = create_res.json()
        sid = state["session_id"]

        for step in spec["intervention_sequence"]:
            if step["type"] == "interrupt":
                res = client.post(
                    f"/api/demo/sessions/{sid}/interrupt",
                    json={"command": step["command"], "reason": step.get("reason")},
                )
                assert res.status_code == 200, f"Interrupt failed in {spec['run_id']}: {res.text}"
                state = res.json()
            elif step["type"] == "decision":
                res = client.post(
                    f"/api/demo/sessions/{sid}/decision",
                    json={
                        "action_id": step["action_id"],
                        "decision": step["decision"],
                        "reason": step.get("reason"),
                    },
                )
                assert res.status_code == 200, f"Decision failed in {spec['run_id']}: {res.text}"
                state = res.json()

        invalid_action_res = client.post(
            f"/api/demo/sessions/{sid}/decision",
            json={"action_id": "arbitrary_unallowlisted_tool", "decision": "approve"},
        )

        artifact = state["trust_summary"].get("simulated_artifact")
        run_records.append(
            {
                "run_id": spec["run_id"],
                "experiment_group": spec["experiment_group"],
                "scenario_id": spec["scenario_id"],
                "expected_terminal_status": spec["expected_terminal_status"],
                "actual_terminal_status": state["status"],
                "expected_gate_action": spec["expected_gate_action"],
                "expected_boundary_triggered": spec["expected_boundary_triggered"],
                "actual_boundary_triggered": state["plan"]["boundary_triggered"],
                "expected_export_approved": spec["expected_export_approved"],
                "actual_export_approved": artifact["export_approved"] if artifact else False,
                "expected_external_publication": spec["expected_external_publication"],
                "actual_external_publication": (
                    artifact["external_publication_performed"] if artifact else False
                ),
                "artifact_state": artifact["artifact_state"] if artifact else None,
                "artifact_content": artifact["content"] if artifact else None,
                "planner_source": state["plan"]["planner_source"],
                "calibration_label": state["trust_summary"]["calibration_label"],
                "calibration_dimensions": state["trust_summary"]["calibration_dimensions"],
                "uncertainty_notes_count": len(state["trust_summary"]["uncertainty_notes"]),
                "evidence": state["trust_summary"]["evidence"],
                "invalid_action_http_status": invalid_action_res.status_code,
                "steps": [
                    {
                        "step_id": s["step_id"],
                        "action_id": s["action_id"],
                        "risk": s["risk"],
                        "requires_approval": s["requires_approval"],
                        "policy_rule_id": s["policy_rule_id"],
                        "status": s["status"],
                    }
                    for s in state["plan"]["steps"]
                ],
                "events": state["events"],
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "suite_version": suite["suite_version"],
        "total_runs": len(run_records),
        "runs": run_records,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    result = run_benchmark_suite()
    print(f"Executed {result['total_runs']} benchmark scenarios -> {DEFAULT_OUTPUT_FILE}")
