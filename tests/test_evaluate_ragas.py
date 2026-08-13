import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_ragas  # noqa: E402
from evaluate_retrieval import EvaluationCase  # noqa: E402
from insurance_chatbot.rag_service import FakeRAGService, SourceChunk  # noqa: E402


@dataclass
class MetricResult:
    value: float
    reason: str | None = None


class FixedMetric:
    def __init__(self, value: float, reason: str) -> None:
        self.result = MetricResult(value, reason)
        self.calls: list[dict] = []

    async def ascore(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FixedRetrieval:
    embedding_model = "test-embedding"

    async def search(self, question: str, policy_id: str | None, top_k: int):
        return [
            SourceChunk(
                content="La póliza cubre hospitalización.",
                source_file="POL1.pdf",
                page_number=2,
                chunk_id="POL1-art2-001",
                score=0.75,
            )
        ]


def test_evaluate_case_scores_real_answer_and_captured_contexts() -> None:
    async def run() -> None:
        capture = evaluate_ragas.CapturingRetrievalService(FixedRetrieval())
        rag = FakeRAGService(capture)
        answer_metric = FixedMetric(0.8, "relevant answer")
        context_metric = FixedMetric(0.7, "relevant context")
        case = EvaluationCase("case", "¿Qué cubre?", "POL1", ("POL1-art2-001",))

        result = await evaluate_ragas.evaluate_case(
            case,
            rag_service=rag,
            retrieval_service=capture,
            answer_metric=answer_metric,
            context_metric=context_metric,
        )

        assert result.answer_relevancy == 0.8
        assert result.context_relevance == 0.7
        assert result.retrieved_chunk_ids == ["POL1-art2-001"]
        assert answer_metric.calls[0]["user_input"] == case.question
        assert answer_metric.calls[0]["response"] == result.answer
        assert context_metric.calls[0]["retrieved_contexts"] == [
            "La póliza cubre hospitalización."
        ]

    asyncio.run(run())


def test_aggregate_results_applies_sixty_percent_health_threshold() -> None:
    common = {
        "question": "q",
        "policy_id": None,
        "answer": "a",
        "sources": [],
        "retrieved_chunk_ids": [],
        "retrieval_scores": [],
    }
    results = [
        evaluate_ragas.RagasCaseResult(
            id="one", answer_relevancy=0.8, context_relevance=0.7, type="standard", **common
        ),
        evaluate_ragas.RagasCaseResult(
            id="two", answer_relevancy=0.6, context_relevance=0.5, type="unanswerable", **common
        ),
    ]

    summary = evaluate_ragas.aggregate_results(results, threshold=0.6)

    assert summary["answer_relevancy"]["mean"] == 0.7
    assert summary["answer_relevancy"]["healthy"] is True
    assert summary["context_relevance"]["mean"] == 0.6
    assert summary["context_relevance"]["passing_cases"] == 1
    assert summary["healthy"] is True
    assert summary["by_type"]["standard"]["answer_relevancy_mean"] == 0.8
    assert summary["by_type"]["unanswerable"]["cases"] == 1
