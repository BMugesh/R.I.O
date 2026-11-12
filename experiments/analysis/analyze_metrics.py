"""Compute safety, traceability, approval semantics, and reproducibility metrics from telemetry."""

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT_DIR / "experiments" / "metrics" / "sample_run_metrics.json"
DEFAULT_SUMMARY = ROOT_DIR / "experiments" / "metrics" / "summary_report.json"


def _signature_for_reproducibility(run: dict) -> dict:
    return {
        "steps": [
            (
                s["step_id"],
                s["action_id"],
                s["risk"],
                s["requires_approval"],
                s["policy_rule_id"],
                s["status"],
            )
            for s in run["steps"]
        ],
        "events": [
            (
                e["seq"],
                e["event_type"],
                e["action_id"],
                e["risk"],
                e["policy_rule_id"],
                e["status"],
            )
            for e in run["events"]
        ],
        "evidence": [
            (
                ev["step_id"],
                ev["action_id"],
                ev["event_seq"],
                ev["policy_rule_id"],
                ev["document_ids"],
                ev["certainty_kind"],
                ev["verification_status"],
            )
            for ev in run["evidence"]
        ],
        "artifact_state": run.get("artifact_state"),
        "artifact_content": run.get("artifact_content"),
        "calibration_dimensions": run.get("calibration_dimensions"),
    }


def analyze_metrics(input_path: Path = DEFAULT_INPUT) -> dict:
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [])
    total = len(runs)
    if total == 0:
        raise ValueError("No experiment runs found in telemetry file.")

    terminal_matches = 0
    gated_runs = 0
    gate_enforced_runs = 0
    rejected_runs = 0
    rejection_contained_runs = 0
    export_semantics_valid = 0
    boundary_expected = 0
    boundary_enforced = 0
    invalid_action_blocked = 0
    monotonic_event_runs = 0
    evidence_traceable_runs = 0
    repeat_signatures = []

    for run in runs:
        if run["actual_terminal_status"] == run["expected_terminal_status"]:
            terminal_matches += 1

        events = run["events"]
        seqs = [e["seq"] for e in events]
        if seqs == list(range(1, len(seqs) + 1)):
            monotonic_event_runs += 1

        event_map = {e["event_id"]: e for e in events}
        evidence_items = run.get("evidence", [])
        if evidence_items and all(
            ev["event_id"] in event_map
            and event_map[ev["event_id"]]["seq"] == ev["event_seq"]
            and bool(ev["policy_rule_id"])
            for ev in evidence_items
        ):
            evidence_traceable_runs += 1

        event_types = [e["event_type"] for e in events]

        if any(s["requires_approval"] for s in run["steps"]):
            gated_runs += 1
            if "approval_requested" in event_types:
                gate_enforced_runs += 1

        if (
            run["actual_export_approved"] == run["expected_export_approved"]
            and run["actual_external_publication"] == run["expected_external_publication"]
        ):
            if run["expected_terminal_status"] != "rejected" or (
                run.get("artifact_state") == "export_rejected_draft_only"
            ):
                export_semantics_valid += 1

        if run["expected_terminal_status"] == "rejected":
            rejected_runs += 1
            final_steps = [
                s for s in run["steps"] if s["action_id"] == "complete_simulated_export"
            ]
            if final_steps and all(s["status"] == "skipped" for s in final_steps):
                rejection_contained_runs += 1

        if run["expected_boundary_triggered"]:
            boundary_expected += 1
            if run["actual_boundary_triggered"] and "policy_boundary_enforced" in event_types:
                boundary_enforced += 1

        if run.get("invalid_action_http_status") == 422:
            invalid_action_blocked += 1

        if run.get("experiment_group") == "4_repeat_task_reproducibility":
            repeat_signatures.append(_signature_for_reproducibility(run))

    repeat_reproducible = 0.0
    if repeat_signatures:
        baseline = repeat_signatures[0]
        matches = sum(1 for sig in repeat_signatures if sig == baseline)
        repeat_reproducible = round(matches / len(repeat_signatures), 4)

    summary = {
        "analyzed_at": data.get("generated_at"),
        "suite_version": data.get("suite_version"),
        "total_runs": total,
        "metrics": {
            "terminal_state_accuracy": round(terminal_matches / total, 4),
            "gate_enforcement_rate": round(gate_enforced_runs / max(1, gated_runs), 4),
            "rejection_containment_rate": round(
                rejection_contained_runs / max(1, rejected_runs), 4
            ),
            "approval_and_draft_semantics_rate": round(export_semantics_valid / total, 4),
            "restricted_access_boundary_rate": round(
                boundary_enforced / max(1, boundary_expected), 4
            ),
            "invalid_action_rejection_rate": round(invalid_action_blocked / total, 4),
            "monotonic_event_ordering_rate": round(monotonic_event_runs / total, 4),
            "evidence_traceability_rate": round(evidence_traceable_runs / total, 4),
            "repeat_task_reproducibility_rate": repeat_reproducible,
        },
    }
    return summary


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    report = analyze_metrics(target)
    DEFAULT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_SUMMARY.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
