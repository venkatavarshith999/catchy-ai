"""Synthetic language regression evaluation, explicitly not a field benchmark."""

import json
import statistics
import time
from pathlib import Path

from backend.detection import analyze

ROOT = Path(__file__).resolve().parents[1]


def evaluate(write=True):
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": "synthetic-development",
        "field_validated": False,
        "audio_end_to_end_ms": None,
        "languages": [],
    }
    for path in sorted((ROOT / "data").glob("*/cases.json")):
        cases = json.loads(path.read_text(encoding="utf-8"))
        tp = fp = fn = tn = 0
        timings = []
        results = []
        for case in cases:
            start = time.perf_counter()
            result = analyze(case["turns"], path.parent.name)
            timings.append((time.perf_counter() - start) * 1000)
            positive = result["level"] == "high"
            expected = case["expected"] == "high"
            tp += positive and expected
            fp += positive and not expected
            fn += not positive and expected
            tn += not positive and not expected
            results.append(
                {
                    "id": case["id"],
                    "expected": case["expected"],
                    "predicted": result["level"],
                    "match": positive == expected,
                }
            )
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        report["languages"].append(
            {
                "language": path.parent.name,
                "status": "beta",
                "dataset_kind": "authored-synthetic"
                if path.parent.name in {"en", "hi", "te"}
                else "lexicon-derived-smoke",
                "independent_holdout": False,
                "cases": len(cases),
                "scam_cases": tp + fn,
                "genuine_cases": tn + fp,
                "precision": precision,
                "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
                "p50_ms": round(statistics.median(timings), 3),
                "p95_ms": round(sorted(timings)[max(0, int(len(timings) * 0.95) - 1)], 3),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "results": results,
            }
        )
    if write:
        (ROOT / "evaluation" / "multilingual-results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    for row in evaluate()["languages"]:
        print(
            row["language"],
            "precision",
            round(row["precision"], 3),
            "recall",
            round(row["recall"], 3),
            "F1",
            round(row["f1"], 3),
            "p95_ms",
            row["p95_ms"],
        )
