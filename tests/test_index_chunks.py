"""Tests for scripts/index_chunks.py, including an end-to-end check that
chunks indexed with this script are actually retrievable through the
existing insurance_chatbot.rag_service.RealRetrievalService — i.e. that the
chunk schema this script writes is really what the rest of the app expects,
not just what it claims to expect.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import index_chunks  # noqa: E402

from insurance_chatbot.rag_service import RealRetrievalService  # noqa: E402


def _fake_embed(text: str) -> list[float]:
    """Deterministic 2-D bag-of-keywords embedding: [hospital, exclus]."""
    lowered = text.lower()
    return [float(lowered.count("hospital")), float(lowered.count("exclus"))]


class FakeSyncEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=_fake_embed(text)) for text in input]
        )


class FakeSyncOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeSyncEmbeddingsAPI()


class FakeAsyncEmbeddingsAPI:
    async def create(self, *, model: str, input: str) -> SimpleNamespace:
        return SimpleNamespace(data=[SimpleNamespace(embedding=_fake_embed(input))])


class FakeAsyncOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeAsyncEmbeddingsAPI()


SAMPLE_CHUNKS = [
    {
        "chunk_id": "POLTEST-art1-001",
        "text": "La poliza cubre gastos de hospitalizacion de emergencia.",
        "policy_id": "POLTEST",
        "filename": "POLTEST.pdf",
        "article": "Articulo 1",
        "page": 3,
        "document_hash": "hash-a",
        "embedding_model": "text-embedding-test",
        "index_version": "article-v1-1024-154",
    },
    {
        "chunk_id": "POLTEST-art2-001",
        "text": "Quedan excluidas las exclusiones por enfermedades preexistentes.",
        "policy_id": "POLTEST",
        "filename": "POLTEST.pdf",
        "article": "Articulo 2",
        "page": 5,
        "document_hash": "hash-a",
        "embedding_model": "text-embedding-test",
        "index_version": "article-v1-1024-154",
    },
]


def test_load_chunks_reads_valid_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in SAMPLE_CHUNKS), encoding="utf-8")

    chunks = index_chunks.load_chunks(path)

    assert chunks == SAMPLE_CHUNKS


def test_load_chunks_rejects_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps({"chunk_id": "X", "text": "..."}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing fields"):
        index_chunks.load_chunks(path)


def test_load_chunks_requires_the_file_to_exist(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        index_chunks.load_chunks(tmp_path / "does_not_exist.jsonl")


def test_point_id_for_is_deterministic() -> None:
    first = index_chunks.point_id_for("POL0001-art3-001")
    second = index_chunks.point_id_for("POL0001-art3-001")
    different = index_chunks.point_id_for("POL0001-art3-002")

    assert first == second
    assert first != different


def test_index_chunks_upserts_points_with_full_payload() -> None:
    qdrant_client = QdrantClient(":memory:")
    openai_client = FakeSyncOpenAIClient()

    result = index_chunks.index_chunks(
        SAMPLE_CHUNKS,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="test_policies",
        batch_size=1,
    )

    assert result == {
        "chunks_indexed": 2,
        "chunks_reused": 0,
        "batches": 2,
        "collection": "test_policies",
    }

    stored = qdrant_client.scroll(collection_name="test_policies", limit=10, with_payload=True)[0]
    assert len(stored) == 2
    assert {point.payload["chunk_id"] for point in stored} == {
        "POLTEST-art1-001",
        "POLTEST-art2-001",
    }


def test_second_index_run_reuses_vectors_without_api_calls() -> None:
    qdrant_client = QdrantClient(":memory:")
    openai_client = FakeSyncOpenAIClient()

    index_chunks.index_chunks(
        SAMPLE_CHUNKS,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="test_policies",
    )
    calls_after_first_run = len(openai_client.embeddings.calls)
    result = index_chunks.index_chunks(
        SAMPLE_CHUNKS,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="test_policies",
    )

    assert result["chunks_indexed"] == 0
    assert result["chunks_reused"] == 2
    assert len(openai_client.embeddings.calls) == calls_after_first_run


def test_metadata_only_versions_existing_points_without_openai() -> None:
    qdrant_client = QdrantClient(":memory:")
    qdrant_client.create_collection(
        collection_name="test_policies",
        vectors_config=models.VectorParams(
            size=1536,
            distance=models.Distance.COSINE,
        ),
    )
    qdrant_client.upsert(
        collection_name="test_policies",
        points=[
            models.PointStruct(
                id=index_chunks.point_id_for(chunk["chunk_id"]),
                vector=[0.0] * 1536,
                payload={
                    key: value
                    for key, value in chunk.items()
                    if key not in {"embedding_model", "index_version"}
                },
            )
            for chunk in SAMPLE_CHUNKS
        ],
    )

    result = index_chunks.annotate_existing_index(
        qdrant_client,
        SAMPLE_CHUNKS,
        collection_name="test_policies",
        embedding_model="text-embedding-3-small",
    )
    points, _ = qdrant_client.scroll(collection_name="test_policies", limit=10, with_payload=True)

    assert result["openai_calls"] == 0
    assert all(point.payload["index_version"] == "article-v1-1024-154" for point in points)


def test_indexed_chunks_are_retrievable_through_rag_service() -> None:
    """End-to-end: chunk schema -> index_chunks -> Qdrant -> RealRetrievalService."""
    qdrant_client = QdrantClient(":memory:")

    index_result = index_chunks.index_chunks(
        SAMPLE_CHUNKS,
        openai_client=FakeSyncOpenAIClient(),
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="queplan_policies_test",
    )
    assert index_result["chunks_indexed"] == 2

    retrieval_service = RealRetrievalService(
        openai_client=FakeAsyncOpenAIClient(),
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="queplan_policies_test",
    )

    results = asyncio.run(
        retrieval_service.search(
            question="Que cubre la hospitalizacion?",
            policy_id=None,
            top_k=1,
        )
    )

    assert len(results) == 1
    assert results[0].content == SAMPLE_CHUNKS[0]["text"]
    assert results[0].source_file == "POLTEST.pdf"
    assert results[0].page_number == 3
