import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import eval_baseline  # noqa: E402


def test_load_baseline_returns_none_when_missing(tmp_path: Path) -> None:
    assert eval_baseline.load_baseline(tmp_path / "missing.json") is None


def test_compare_ragas_to_baseline_matches_by_id_and_reports_delta() -> None:
    report = {
        "cases": [
            {"id": "one", "answer_relevancy": 0.9, "context_relevance": 1.0},
            {"id": "two", "answer_relevancy": 0.5, "context_relevance": 0.8},
            {"id": "new_case", "answer_relevancy": 0.7, "context_relevance": 0.7},
        ]
    }
    baseline = {
        "generated_at": "2026-08-07T00:00:00Z",
        "cases": [
            {"id": "one", "answer_relevancy": 0.7, "context_relevance": 1.0},
            {"id": "two", "answer_relevancy": 0.5, "context_relevance": 0.8},
            {"id": "gone_case", "answer_relevancy": 0.6, "context_relevance": 0.6},
        ],
    }

    comparison = eval_baseline.compare_ragas_to_baseline(report, baseline)

    assert comparison is not None
    assert comparison["matched_cases"] == 2
    assert comparison["missing_from_run"] == ["gone_case"]
    assert comparison["answer_relevancy"]["current_mean"] == 0.7
    assert comparison["answer_relevancy"]["baseline_mean"] == 0.6
    assert comparison["answer_relevancy"]["delta"] == 0.1


def test_compare_ragas_to_baseline_returns_none_without_baseline() -> None:
    assert eval_baseline.compare_ragas_to_baseline({"cases": []}, None) is None


def test_compare_latency_to_baseline_reports_mean_and_p95_delta() -> None:
    report = {
        "cases": [
            {
                "id": "one",
                "time_to_model_ms": 100,
                "model_response_time_ms": 1000,
                "backend_total_time_ms": 1100,
            },
            {
                "id": "two",
                "time_to_model_ms": 200,
                "model_response_time_ms": 2000,
                "backend_total_time_ms": 2200,
            },
        ]
    }
    baseline = {
        "generated_at": "2026-08-11T00:00:00Z",
        "cases": [
            {
                "id": "one",
                "time_to_model_ms": 50,
                "model_response_time_ms": 900,
                "backend_total_time_ms": 950,
            },
            {
                "id": "two",
                "time_to_model_ms": 150,
                "model_response_time_ms": 1800,
                "backend_total_time_ms": 1950,
            },
        ],
    }

    comparison = eval_baseline.compare_latency_to_baseline(report, baseline)

    assert comparison is not None
    assert comparison["matched_cases"] == 2
    assert comparison["backend_total_time_ms"]["current"]["mean"] == 1650
    assert comparison["backend_total_time_ms"]["baseline"]["mean"] == 1450
    assert comparison["backend_total_time_ms"]["delta_mean"] == 200
