"""Measure policy-query latency before, during, and after the model call."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from openai import AsyncOpenAI
from qdrant_client import QdrantClient

from eval_baseline import compare_latency_to_baseline, load_baseline
from evaluate_retrieval import DEFAULT_QUESTIONS_PATH, load_cases
from insurance_chatbot.indexing import DEFAULT_CHUNKS_PATH, load_chunks
from insurance_chatbot.rag_service import RealRAGService, RealRetrievalService
from insurance_chatbot.schemas import QueryMode
from insurance_chatbot.settings import PROJECT_ROOT, Settings


DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "evaluation" / "latency.json"
DEFAULT_BASELINE_PATH = PROJECT_ROOT / "data" / "evaluation" / "latency_baseline.json"


@dataclass(frozen=True, slots=True)
class LatencyCase:
    id: str
    question: str
    policy_id: str | None
    time_to_model_ms: float
    model_response_time_ms: float
    postprocessing_time_ms: float
    backend_total_time_ms: float
    client_observed_time_ms: float
    retrieved_chunks: int
    type: str = "standard"


def percentile(values: list[float], percentile_value: float) -> float:
    """Calculate a linearly interpolated percentile without extra dependencies."""
    if not values:
        raise ValueError("At least one latency value is required")
    if not 0 <= percentile_value <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile_value / 100
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("At least one latency value is required")
    return {
        "mean": round(mean(values), 2),
        "p50": round(median(values), 2),
        "p95": round(percentile(values, 95), 2),
        "minimum": round(min(values), 2),
        "maximum": round(max(values), 2),
    }


def latency_from_metadata(metadata: dict[str, Any]) -> dict[str, float]:
    latency = metadata.get("latency_ms")
    if not isinstance(latency, dict):
        raise ValueError("RAG response does not contain latency_ms metadata")
    required = (
        "time_to_model_ms",
        "model_response_time_ms",
        "postprocessing_time_ms",
        "total_time_ms",
    )
    parsed: dict[str, float] = {}
    for key in required:
        value = latency.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"RAG latency metadata is missing {key}")
        parsed[key] = float(value)
    return parsed


def aggregate_results(results: list[LatencyCase]) -> dict[str, Any]:
    if not results:
        raise ValueError("At least one latency result is required")
    return {
        "cases": len(results),
        "time_to_model_ms": summarize([item.time_to_model_ms for item in results]),
        "model_response_time_ms": summarize(
            [item.model_response_time_ms for item in results]
        ),
        "postprocessing_time_ms": summarize(
            [item.postprocessing_time_ms for item in results]
        ),
        "backend_total_time_ms": summarize(
            [item.backend_total_time_ms for item in results]
        ),
        "client_observed_time_ms": summarize(
            [item.client_observed_time_ms for item in results]
        ),
    }


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
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
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    qdrant = QdrantClient(path=str(settings.qdrant_path))
    retrieval = RealRetrievalService(
        openai_client=openai_client,
        qdrant_client=qdrant,
        embedding_model=settings.embedding_model,
        collection_name=settings.qdrant_collection,
        score_threshold=settings.score_threshold,
    )
    rag = RealRAGService(
        retrieval,
        openai_client=openai_client,
        chat_model=settings.chat_model,
        top_k=args.top_k,
    )

    results: list[LatencyCase] = []
    try:
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] Measuring {case.id}...")
            client_started = time.perf_counter()
            response = await rag.query(
                case.question,
                case.policy_id,
                QueryMode.POLICIES,
            )
            client_observed_ms = round((time.perf_counter() - client_started) * 1000, 2)
            latency = latency_from_metadata(response.metadata)
            results.append(
                LatencyCase(
                    id=case.id,
                    question=case.question,
                    policy_id=case.policy_id,
                    time_to_model_ms=latency["time_to_model_ms"],
                    model_response_time_ms=latency["model_response_time_ms"],
                    postprocessing_time_ms=latency["postprocessing_time_ms"],
                    backend_total_time_ms=latency["total_time_ms"],
                    client_observed_time_ms=client_observed_ms,
                    retrieved_chunks=int(response.metadata.get("retrieved_chunks", 0)),
                    type=case.type,
                )
            )
    finally:
        qdrant.close()
        await openai_client.close()

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "route": QueryMode.POLICIES.value,
        "generator_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "top_k": args.top_k,
        "definitions": {
            "time_to_model_ms": "Query start through retrieval and prompt construction.",
            "model_response_time_ms": "OpenAI request duration, including network and generation.",
            "postprocessing_time_ms": "Answer parsing and response metadata construction.",
            "backend_total_time_ms": "Complete policy RAG execution inside the service.",
            "client_observed_time_ms": "Wall-clock duration observed by this benchmark process.",
        },
        "summary": aggregate_results(results),
        "cases": [asdict(result) for result in results],
    }
    if not args.no_baseline_compare:
        report["baseline_comparison"] = compare_latency_to_baseline(
            report, load_baseline(args.baseline_path)
        )
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
    parser.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument(
        "--no-baseline-compare",
        action="store_true",
        help="Skip comparing this run against the versioned baseline.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = asyncio.run(run_evaluation(args))
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"Latency evaluation failed: {exc}") from exc
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report.get("baseline_comparison"):
        print("Baseline comparison:")
        print(json.dumps(report["baseline_comparison"], ensure_ascii=False, indent=2))
    print(f"Full report: {args.output_path}")


if __name__ == "__main__":
    main()
