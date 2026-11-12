"""Score Stage 2 human evaluation metrics: completion, decision accuracy, comprehension, perceived control, SUS, and NASA-TLX."""

from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
INSTRUMENT_PATH = HERE / "survey_instrument.json"
DEFAULT_DATA_PATH = HERE / "sample_study_data.json"


def compute_sus_score(sus_responses: dict, sus_items: list) -> float:
    total = 0.0
    for item in sus_items:
        raw = float(sus_responses[item["id"]])
        if item["polarity"] == "positive":
            total += raw - 1.0
        else:
            total += 5.0 - raw
    return round(total * 2.5, 2)


def compute_nasa_tlx(tlx_responses: dict, subscales: list) -> tuple[float, dict]:
    sub = {s["id"]: float(tlx_responses[s["id"]]) for s in subscales}
    overall = round(sum(sub.values()) / len(sub), 2)
    return overall, sub


def score_study_dataset(data_path: Path = DEFAULT_DATA_PATH) -> dict:
    with INSTRUMENT_PATH.open("r", encoding="utf-8") as f:
        instrument = json.load(f)
    with data_path.open("r", encoding="utf-8") as f:
        study = json.load(f)

    comp_questions = instrument["comprehension_questions"]
    pc_items = instrument["perceived_control_items"]
    sus_items = instrument["sus_items"]
    tlx_subscales = instrument["nasa_tlx_subscales"]

    grouped = defaultdict(list)
    for participant in study.get("participants", []):
        tasks = participant["tasks"]
        completion_rate = sum(1 for t in tasks if t["completed"]) / max(1, len(tasks))
        decision_acc = sum(1 for t in tasks if t["decision_accurate"]) / max(1, len(tasks))
        mean_review_s = statistics.mean(t["review_seconds"] for t in tasks)

        comp_correct = sum(
            1
            for q in comp_questions
            if participant["comprehension"].get(q["id"]) == q["correct_option"]
        )
        comp_score = comp_correct / len(comp_questions)

        pc_mean = statistics.mean(float(participant["perceived_control"][i["id"]]) for i in pc_items)
        sus_score = compute_sus_score(participant["sus"], sus_items)
        tlx_overall, tlx_sub = compute_nasa_tlx(participant["nasa_tlx"], tlx_subscales)

        grouped[participant["condition"]].append(
            {
                "participant_id": participant["participant_id"],
                "task_completion_rate": round(completion_rate, 4),
                "decision_accuracy": round(decision_acc, 4),
                "mean_review_seconds": round(mean_review_s, 2),
                "comprehension_score": round(comp_score, 4),
                "perceived_control_mean": round(pc_mean, 2),
                "sus_score": sus_score,
                "nasa_tlx_overall": tlx_overall,
                "nasa_tlx_subscales": tlx_sub,
            }
        )

    summary_by_condition = {}
    for condition, rows in grouped.items():
        summary_by_condition[condition] = {
            "n": len(rows),
            "task_completion_rate_mean": round(statistics.mean(r["task_completion_rate"] for r in rows), 4),
            "decision_accuracy_mean": round(statistics.mean(r["decision_accuracy"] for r in rows), 4),
            "mean_review_seconds": round(statistics.mean(r["mean_review_seconds"] for r in rows), 2),
            "comprehension_score_mean": round(statistics.mean(r["comprehension_score"] for r in rows), 4),
            "perceived_control_mean_1_to_5": round(statistics.mean(r["perceived_control_mean"] for r in rows), 2),
            "sus_score_mean_0_to_100": round(statistics.mean(r["sus_score"] for r in rows), 2),
            "nasa_tlx_overall_mean_0_to_100": round(statistics.mean(r["nasa_tlx_overall"] for r in rows), 2),
        }

    return {
        "synthetic_validation_fixture": bool(study.get("synthetic_validation_fixture", False)),
        "conditions": summary_by_condition,
        "participants_scored": dict(grouped),
    }


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_PATH
    result = score_study_dataset(target)
    print(json.dumps(result, indent=2))
