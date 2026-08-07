"""Evaluate answer and retrieved-context relevance with RAGAS.

The script runs the real policy RAG against the curated retrieval questions and
stores one auditable JSON report. It deliberately evaluates sequentially to keep
API usage predictable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from openai import AsyncOpenAI
from qdrant_client import QdrantClient

from evaluate_retrieval import DEFAULT_QUESTIONS_PATH, EvaluationCase, load_cases
from insurance_chatbot.indexing import DEFAULT_CHUNKS_PATH, load_chunks
from insurance_chatbot.rag_service import (
    AbstractRetrievalService,
    RealRAGService,
    RealRetrievalService,
    SourceChunk,
)
from insurance_chatbot.schemas import QueryMode
from insurance_chatbot.settings import PROJECT_ROOT, Settings


DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "evaluation" / "ragas.json"
DEFAULT_HEALTH_THRESHOLD = 0.60


class AsyncMetric(Protocol):
    async def ascore(self, **kwargs: Any) -> Any:
        """Return an object exposing value and, optionally, reason."""


class CapturingRetrievalService(AbstractRetrievalService):
    """Record the exact chunks used by the RAG without running retrieval twice."""

    def __init__(self, delegate: AbstractRetrievalService) -> None:
        self.delegate = delegate
        self.last_chunks: list[SourceChunk] = []
        self.embedding_model = getattr(delegate, "embedding_model", "unknown")

    async def search(self, question: str, policy_id: str | None, top_k: int) -> list[SourceChunk]:
        self.last_chunks = await self.delegate.search(question, policy_id, top_k)
        return self.last_chunks


@dataclass(frozen=True, slots=True)
class RagasCaseResult:
    id: str
    question: str
    policy_id: str | None
    answer: str
    sources: list[str]
    retrieved_chunk_ids: list[str]
    retrieval_scores: list[float]
    answer_relevancy: float
    context_relevance: float
    answer_reason: str | None = None
    context_reason: str | None = None


def _score(metric_result: Any, metric_name: str) -> tuple[float, str | None]:
    value = float(metric_result.value)
    if not math.isfinite(value):
        raise ValueError(f"RAGAS returned a non-finite {metric_name} score")
    reason = getattr(metric_result, "reason", None)
    return round(value, 4), str(reason) if reason else None


async def evaluate_case(
    case: EvaluationCase,
    *,
    rag_service: RealRAGService,
    retrieval_service: CapturingRetrievalService,
    answer_metric: AsyncMetric,
    context_metric: AsyncMetric,
) -> RagasCaseResult:
    response = await rag_service.query(
        question=case.question,
        policy_id=case.policy_id,
        mode=QueryMode.POLICIES,
    )
    chunks = list(retrieval_service.last_chunks)
    if not chunks:
        raise RuntimeError(f"Case {case.id} returned no contexts to evaluate")

    answer_result = await answer_metric.ascore(
        user_input=case.question,
        response=response.answer,
    )
    context_result = await context_metric.ascore(
        user_input=case.question,
        retrieved_contexts=[chunk.content for chunk in chunks],
    )
    answer_score, answer_reason = _score(answer_result, "answer relevancy")
    context_score, context_reason = _score(context_result, "context relevance")

    return RagasCaseResult(
        id=case.id,
        question=case.question,
        policy_id=case.policy_id,
        answer=response.answer,
        sources=response.sources,
        retrieved_chunk_ids=[chunk.chunk_id or "unknown" for chunk in chunks],
        retrieval_scores=[round(chunk.score, 4) for chunk in chunks if chunk.score is not None],
        answer_relevancy=answer_score,
        context_relevance=context_score,
        answer_reason=answer_reason,
        context_reason=context_reason,
    )


def aggregate_results(
    results: list[RagasCaseResult],
    *,
    threshold: float,
) -> dict[str, Any]:
    if not results:
        raise ValueError("At least one RAGAS result is required")

    answer_scores = [item.answer_relevancy for item in results]
    context_scores = [item.context_relevance for item in results]
    answer_mean = sum(answer_scores) / len(answer_scores)
    context_mean = sum(context_scores) / len(context_scores)
    overall_mean = (answer_mean + context_mean) / 2
    return {
        "cases": len(results),
        "health_threshold": threshold,
        "answer_relevancy": {
            "mean": round(answer_mean, 4),
            "minimum": round(min(answer_scores), 4),
            "passing_cases": sum(score >= threshold for score in answer_scores),
            "healthy": answer_mean >= threshold,
        },
        "context_relevance": {
            "mean": round(context_mean, 4),
            "minimum": round(min(context_scores), 4),
            "passing_cases": sum(score >= threshold for score in context_scores),
            "healthy": context_mean >= threshold,
        },
        "overall_mean": round(overall_mean, 4),
        "healthy": answer_mean >= threshold and context_mean >= threshold,
    }


def create_ragas_metrics(
    *,
    client: AsyncOpenAI,
    evaluator_model: str,
    embedding_model: str,
) -> tuple[AsyncMetric, AsyncMetric]:
    """Create metrics lazily so normal app/test installs do not require RAGAS."""
    try:
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerRelevancy, ContextRelevance
    except ImportError as exc:
        raise RuntimeError("Install evaluation dependencies with: uv sync --extra eval") from exc

    evaluator_llm = llm_factory(evaluator_model, client=client)
    evaluator_embeddings = embedding_factory(
        "openai",
        model=embedding_model,
        client=client,
    )
    return (
        AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
        ContextRelevance(llm=evaluator_llm),
    )


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    if not 0 < args.health_threshold <= 1:
        raise ValueError("--health-threshold must be between 0 and 1")
    if args.top_k <= 0:
        raise ValueError("--top-k must be greater than zero")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be greater than zero")

    chunks = load_chunks(args.chunks_path)
    cases = load_cases(args.questions_path, {chunk["chunk_id"] for chunk in chunks})
    if args.limit is not None:
        cases = cases[: args.limit]

    settings = Settings.from_env()
    settings.require_openai()
    evaluator_model = args.evaluator_model or os.getenv(
        "RAGAS_EVALUATOR_MODEL", settings.chat_model
    )
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    qdrant = QdrantClient(path=str(settings.qdrant_path))
    base_retrieval = RealRetrievalService(
        openai_client=openai_client,
        qdrant_client=qdrant,
        embedding_model=settings.embedding_model,
        collection_name=settings.qdrant_collection,
        score_threshold=settings.score_threshold,
    )
    capturing_retrieval = CapturingRetrievalService(base_retrieval)
    rag_service = RealRAGService(
        capturing_retrieval,
        openai_client=openai_client,
        chat_model=settings.chat_model,
        top_k=args.top_k,
    )
    answer_metric, context_metric = create_ragas_metrics(
        client=openai_client,
        evaluator_model=evaluator_model,
        embedding_model=settings.embedding_model,
    )

    results: list[RagasCaseResult] = []
    try:
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] Evaluating {case.id}...")
            results.append(
                await evaluate_case(
                    case,
                    rag_service=rag_service,
                    retrieval_service=capturing_retrieval,
                    answer_metric=answer_metric,
                    context_metric=context_metric,
                )
            )
    finally:
        qdrant.close()
        await openai_client.close()

    report = {
        "framework": "ragas",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator_model": settings.chat_model,
        "evaluator_model": evaluator_model,
        "embedding_model": settings.embedding_model,
        "top_k": args.top_k,
        "summary": aggregate_results(results, threshold=args.health_threshold),
        "cases": [asdict(result) for result in results],
    }
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions-path", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--evaluator-model", default=None)
    parser.add_argument("--health-threshold", type=float, default=DEFAULT_HEALTH_THRESHOLD)
    parser.add_argument(
        "--fail-below-threshold",
        action="store_true",
        help="Return exit code 2 when either mean relevance score is below the threshold.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = asyncio.run(run_evaluation(args))
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"RAGAS evaluation failed: {exc}") from exc

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Full report: {args.output_path}")
    if args.fail_below_threshold and not report["summary"]["healthy"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
