"""Compare a fresh RAGAS/latency report against its versioned baseline.

Baselines are the compact JSON files in data/evaluation/ (ragas_baseline.json,
latency_baseline.json). Comparisons run on the subset of case ids present in
both the current run and the baseline, so growing the question dataset never
breaks the regression signal, and a run missing a previously-baselined case
is flagged instead of silently skewing the average.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


def load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _matched_and_missing(
    current_ids: set[str], baseline_ids: set[str]
) -> tuple[set[str], list[str]]:
    return current_ids & baseline_ids, sorted(baseline_ids - current_ids)


def compare_ragas_to_baseline(
    report: dict[str, Any], baseline: dict[str, Any] | None
) -> dict[str, Any] | None:
    if baseline is None:
        return None
    current_by_id = {case["id"]: case for case in report["cases"]}
    baseline_by_id = {case["id"]: case for case in baseline["cases"]}
    matched, missing = _matched_and_missing(set(current_by_id), set(baseline_by_id))
    comparison: dict[str, Any] = {
        "baseline_generated_at": baseline.get("generated_at"),
        "matched_cases": len(matched),
        "missing_from_run": missing,
    }
    if not matched:
        return comparison

    for metric in ("answer_relevancy", "context_relevance"):
        current_mean = round(mean(current_by_id[i][metric] for i in matched), 4)
        baseline_mean = round(mean(baseline_by_id[i][metric] for i in matched), 4)
        comparison[metric] = {
            "current_mean": current_mean,
            "baseline_mean": baseline_mean,
            "delta": round(current_mean - baseline_mean, 4),
        }
    return comparison


def compare_latency_to_baseline(
    report: dict[str, Any], baseline: dict[str, Any] | None
) -> dict[str, Any] | None:
    if baseline is None:
        return None
    from evaluate_latency import summarize

    current_by_id = {case["id"]: case for case in report["cases"]}
    baseline_by_id = {case["id"]: case for case in baseline["cases"]}
    matched, missing = _matched_and_missing(set(current_by_id), set(baseline_by_id))
    comparison: dict[str, Any] = {
        "baseline_generated_at": baseline.get("generated_at"),
        "matched_cases": len(matched),
        "missing_from_run": missing,
    }
    if not matched:
        return comparison

    for field in ("time_to_model_ms", "model_response_time_ms", "backend_total_time_ms"):
        current_summary = summarize([current_by_id[i][field] for i in matched])
        baseline_summary = summarize([baseline_by_id[i][field] for i in matched])
        comparison[field] = {
            "current": current_summary,
            "baseline": baseline_summary,
            "delta_mean": round(current_summary["mean"] - baseline_summary["mean"], 2),
            "delta_p95": round(current_summary["p95"] - baseline_summary["p95"], 2),
        }
    return comparison
