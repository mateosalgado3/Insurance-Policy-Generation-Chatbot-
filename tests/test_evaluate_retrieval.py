import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_retrieval  # noqa: E402


def test_compute_metrics_uses_real_ranks_and_recall() -> None:
    cases = [
        evaluate_retrieval.EvaluationCase(
            id="one",
            question="question one",
            policy_id=None,
            relevant_chunk_ids=("a", "b"),
        ),
        evaluate_retrieval.EvaluationCase(
            id="two",
            question="question two",
            policy_id=None,
            relevant_chunk_ids=("z",),
        ),
    ]
    rankings = {
        "one": [
            evaluate_retrieval.RankedHit("x", 0.9),
            evaluate_retrieval.RankedHit("a", 0.8),
        ],
        "two": [evaluate_retrieval.RankedHit("z", 0.7)],
    }

    metrics, details = evaluate_retrieval.compute_metrics(cases, rankings, top_k=2)

    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["recall_at_k"] == 0.75
    assert metrics["mrr"] == 0.75
    assert details[0]["rank"] == 2


def test_exploratory_threshold_returns_labeled_operating_point() -> None:
    cases = [
        evaluate_retrieval.EvaluationCase(
            id="one",
            question="question",
            policy_id=None,
            relevant_chunk_ids=("relevant",),
        )
    ]
    rankings = {
        "one": [
            evaluate_retrieval.RankedHit("relevant", 0.8),
            evaluate_retrieval.RankedHit("other", 0.4),
        ]
    }

    result = evaluate_retrieval.exploratory_threshold(cases, rankings)

    assert result is not None
    assert result["score_threshold"] == 0.8
    assert result["labeled_f1"] == 1.0
