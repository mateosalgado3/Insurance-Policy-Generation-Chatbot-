import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_latency  # noqa: E402


def test_percentile_interpolates_and_validates_input() -> None:
    assert evaluate_latency.percentile([10, 20, 30], 50) == 20
    assert evaluate_latency.percentile([10, 20], 95) == pytest.approx(19.5)
    with pytest.raises(ValueError, match="At least one"):
        evaluate_latency.percentile([], 95)


def test_latency_from_metadata_requires_complete_breakdown() -> None:
    parsed = evaluate_latency.latency_from_metadata(
        {
            "latency_ms": {
                "time_to_model_ms": 100,
                "model_response_time_ms": 500,
                "postprocessing_time_ms": 2,
                "total_time_ms": 602,
            }
        }
    )

    assert parsed["model_response_time_ms"] == 500
    with pytest.raises(ValueError, match="missing model_response_time_ms"):
        evaluate_latency.latency_from_metadata(
            {"latency_ms": {"time_to_model_ms": 100}}
        )


def test_aggregate_results_reports_mean_p50_and_p95() -> None:
    first = evaluate_latency.LatencyCase(
        "one", "q1", None, 100, 500, 2, 602, 604, 5
    )
    second = evaluate_latency.LatencyCase(
        "two", "q2", "POL1", 200, 900, 4, 1104, 1108, 5
    )

    summary = evaluate_latency.aggregate_results([first, second])

    assert summary["time_to_model_ms"]["mean"] == 150
    assert summary["model_response_time_ms"]["p50"] == 700
    assert summary["backend_total_time_ms"]["maximum"] == 1104
