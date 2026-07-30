"""Evaluate retrieval with curated questions using local or OpenAI embeddings."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI
from qdrant_client import QdrantClient, models

from insurance_chatbot.embeddings import LocalHashingEmbedder
from insurance_chatbot.indexing import DEFAULT_CHUNKS_PATH, load_chunks
from insurance_chatbot.settings import PROJECT_ROOT, Settings


DEFAULT_QUESTIONS_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_questions.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "evaluation" / "retrieval.json"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    question: str
    policy_id: str | None
    relevant_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedHit:
    chunk_id: str
    score: float


def load_cases(path: Path, available_chunk_ids: set[str]) -> list[EvaluationCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for raw in raw_cases:
        case = EvaluationCase(
            id=str(raw["id"]),
            question=str(raw["question"]).strip(),
            policy_id=raw.get("policy_id"),
            relevant_chunk_ids=tuple(raw["relevant_chunk_ids"]),
        )
        if not case.question or not case.relevant_chunk_ids:
            raise ValueError(f"Invalid evaluation case: {case.id}")
        if case.id in seen_ids:
            raise ValueError(f"Duplicate evaluation case id: {case.id}")
        missing = set(case.relevant_chunk_ids) - available_chunk_ids
        if missing:
            raise ValueError(f"Case {case.id} references missing chunks: {sorted(missing)}")
        seen_ids.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    return cases


def local_rankings(
    cases: list[EvaluationCase],
    chunks: list[dict[str, Any]],
    *,
    top_k: int,
) -> dict[str, list[RankedHit]]:
    embedder = LocalHashingEmbedder()
    document_vectors = embedder.encode([chunk["text"] for chunk in chunks])
    query_vectors = embedder.encode([case.question for case in cases])
    rankings: dict[str, list[RankedHit]] = {}
    for case, query_vector in zip(cases, query_vectors, strict=True):
        candidate_indices = [
            index
            for index, chunk in enumerate(chunks)
            if case.policy_id is None or chunk["policy_id"] == case.policy_id
        ]
        scores = document_vectors[candidate_indices] @ query_vector
        order = np.argsort(scores)[::-1][:top_k]
        rankings[case.id] = [
            RankedHit(
                chunk_id=chunks[candidate_indices[int(position)]]["chunk_id"],
                score=float(scores[int(position)]),
            )
            for position in order
        ]
    return rankings


def openai_rankings(
    cases: list[EvaluationCase],
    *,
    client: OpenAI,
    qdrant: QdrantClient,
    embedding_model: str,
    collection_name: str,
    top_k: int,
) -> dict[str, list[RankedHit]]:
    response = client.embeddings.create(
        model=embedding_model,
        input=[case.question for case in cases],
    )
    vectors = [item.embedding for item in response.data]
    if len(vectors) != len(cases):
        raise RuntimeError("OpenAI returned an unexpected query embedding count")

    rankings: dict[str, list[RankedHit]] = {}
    for case, vector in zip(cases, vectors, strict=True):
        query_filter = None
        if case.policy_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="policy_id",
                        match=models.MatchValue(value=case.policy_id),
                    )
                ]
            )
        result = qdrant.query_points(
            collection_name=collection_name,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=["chunk_id"],
        )
        rankings[case.id] = [
            RankedHit(
                chunk_id=str(point.payload["chunk_id"]),
                score=float(point.score),
            )
            for point in result.points
        ]
    return rankings


def compute_metrics(
    cases: list[EvaluationCase],
    rankings: dict[str, list[RankedHit]],
    *,
    top_k: int,
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    hits = 0
    details: list[dict[str, Any]] = []
    for case in cases:
        relevant = set(case.relevant_chunk_ids)
        ranked = rankings[case.id][:top_k]
        retrieved_ids = [hit.chunk_id for hit in ranked]
        matched = relevant.intersection(retrieved_ids)
        rank = next(
            (
                index
                for index, chunk_id in enumerate(retrieved_ids, start=1)
                if chunk_id in relevant
            ),
            None,
        )
        reciprocal_rank = 1 / rank if rank else 0.0
        recall = len(matched) / len(relevant)
        hits += int(bool(matched))
        reciprocal_ranks.append(reciprocal_rank)
        recalls.append(recall)
        details.append(
            {
                "id": case.id,
                "question": case.question,
                "relevant_chunk_ids": list(case.relevant_chunk_ids),
                "rank": rank,
                "reciprocal_rank": round(reciprocal_rank, 4),
                "recall": round(recall, 4),
                "retrieved": [asdict(hit) for hit in ranked],
            }
        )
    return (
        {
            "questions": len(cases),
            "top_k": top_k,
            "hit_rate_at_k": round(hits / len(cases), 4),
            "recall_at_k": round(float(np.mean(recalls)), 4),
            "mrr": round(float(np.mean(reciprocal_ranks)), 4),
        },
        details,
    )


def exploratory_threshold(
    cases: list[EvaluationCase],
    rankings: dict[str, list[RankedHit]],
) -> dict[str, float] | None:
    labels_and_scores: list[tuple[bool, float]] = []
    by_id = {case.id: set(case.relevant_chunk_ids) for case in cases}
    for case_id, hits in rankings.items():
        labels_and_scores.extend((hit.chunk_id in by_id[case_id], hit.score) for hit in hits)
    if not labels_and_scores or not any(label for label, _ in labels_and_scores):
        return None

    best: tuple[float, float, float, float] | None = None
    for threshold in sorted({score for _, score in labels_and_scores}):
        tp = sum(label and score >= threshold for label, score in labels_and_scores)
        fp = sum(not label and score >= threshold for label, score in labels_and_scores)
        fn = sum(label and score < threshold for label, score in labels_and_scores)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        candidate = (f1, threshold, precision, recall)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    return {
        "score_threshold": round(best[1], 4),
        "labeled_precision": round(best[2], 4),
        "labeled_recall": round(best[3], 4),
        "labeled_f1": round(best[0], 4),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("local", "openai"), default="local")
    parser.add_argument("--questions-path", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than zero")
    chunks = load_chunks(args.chunks_path)
    cases = load_cases(args.questions_path, {chunk["chunk_id"] for chunk in chunks})
    settings = Settings.from_env()

    if args.provider == "local":
        rankings = local_rankings(cases, chunks, top_k=args.top_k)
    else:
        settings.require_openai()
        qdrant = QdrantClient(path=str(settings.qdrant_path))
        try:
            rankings = openai_rankings(
                cases,
                client=OpenAI(api_key=settings.openai_api_key),
                qdrant=qdrant,
                embedding_model=settings.embedding_model,
                collection_name=settings.qdrant_collection,
                top_k=args.top_k,
            )
        finally:
            qdrant.close()

    metrics, details = compute_metrics(cases, rankings, top_k=args.top_k)
    report = {
        "provider": args.provider,
        "embedding_model": (
            settings.embedding_model if args.provider == "openai" else "local-hashing"
        ),
        "metrics": metrics,
        "exploratory_threshold": (
            exploratory_threshold(cases, rankings) if args.provider == "openai" else None
        ),
        "cases": details,
    }
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
