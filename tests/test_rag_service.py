import asyncio
from types import SimpleNamespace

import pytest

from insurance_chatbot.rag_service import (
    AbstractRetrievalService,
    IndexNotReadyError,
    RealRAGService,
    RealRetrievalService,
    SourceChunk,
)


class FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, input: str) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class FakeResponsesAPI:
    def __init__(self, output_text: str = "Respuesta basada en [Fuente 1]."):
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:
        self.calls.append({"model": model, "instructions": instructions, "input": input})
        return SimpleNamespace(id="response-test-001", output_text=self.output_text)


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsAPI()
        self.responses = FakeResponsesAPI()


class FakeQdrantClient:
    def __init__(self, *, exists: bool = True, points_count: int = 1) -> None:
        self.exists = exists
        self.points_count = points_count
        self.calls: list[dict[str, object]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    def get_collection(self, collection_name: str) -> SimpleNamespace:
        return SimpleNamespace(points_count=self.points_count)

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id="point-1",
                    score=0.92,
                    payload={
                        "chunk_id": "POL320190074-p020-c001",
                        "text": "La póliza cubre atención hospitalaria de emergencia.",
                        "policy_id": "POL320190074",
                        "filename": "POL320190074.pdf",
                        "article": "Artículo 12",
                        "page": 20,
                    },
                )
            ]
        )


class StubRetrievalService(AbstractRetrievalService):
    embedding_model = "text-embedding-test"

    def __init__(self, chunks: list[SourceChunk]) -> None:
        self.chunks = chunks
        self.calls: list[dict[str, object]] = []

    async def search(self, question: str, policy_id: str | None, top_k: int) -> list[SourceChunk]:
        self.calls.append({"question": question, "policy_id": policy_id, "top_k": top_k})
        return self.chunks


def test_real_retrieval_returns_citable_source_chunks() -> None:
    openai_client = FakeOpenAIClient()
    qdrant_client = FakeQdrantClient()
    service = RealRetrievalService(
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="test-collection",
        score_threshold=0.4,
    )

    results = asyncio.run(
        service.search(
            question="¿Qué cubre la póliza?",
            policy_id="POL320190074",
            top_k=3,
        )
    )

    assert results[0].source_file == "POL320190074.pdf"
    assert results[0].page_number == 20
    assert results[0].article == "Artículo 12"
    assert results[0].score == 0.92
    assert qdrant_client.calls[0]["score_threshold"] == 0.4
    assert qdrant_client.calls[0]["query_filter"] is not None


def test_real_retrieval_reports_missing_index() -> None:
    service = RealRetrievalService(
        openai_client=FakeOpenAIClient(),
        qdrant_client=FakeQdrantClient(exists=False),
    )
    with pytest.raises(IndexNotReadyError, match="does not exist"):
        asyncio.run(service.search("¿Qué cubre?", None, 5))


def test_real_retrieval_rejects_invalid_input() -> None:
    service = RealRetrievalService(
        openai_client=FakeOpenAIClient(),
        qdrant_client=FakeQdrantClient(),
    )
    with pytest.raises(ValueError, match="question must not be empty"):
        asyncio.run(service.search("  ", None, 5))
    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        asyncio.run(service.search("¿Qué cubre?", None, 0))


def test_real_rag_generates_grounded_response_and_citations() -> None:
    retrieval = StubRetrievalService(
        [
            SourceChunk(
                content="La póliza cubre hospitalización de emergencia.",
                source_file="POL320190074.pdf",
                page_number=20,
                article="Artículo 12",
                score=0.91,
            )
        ]
    )
    openai_client = FakeOpenAIClient()
    service = RealRAGService(
        retrieval_service=retrieval,
        openai_client=openai_client,
        chat_model="gpt-test",
        top_k=3,
    )

    response = asyncio.run(service.query("¿Qué cubre la póliza?", "POL320190074"))

    assert response.answer == "Respuesta basada en [Fuente 1]."
    assert response.sources == ["POL320190074.pdf - Página 20 - Artículo 12"]
    assert response.metadata["retrieval_scores"] == [0.91]
    assert response.metadata["retrieved_chunks"] == 1
    assert response.metadata["latency_ms"]["time_to_model_ms"] >= 0
    assert response.metadata["latency_ms"]["model_response_time_ms"] >= 0
    assert response.metadata["latency_ms"]["total_time_ms"] >= 0
    assert "[Fuente 1" in openai_client.responses.calls[0]["input"]


def test_real_rag_abstains_without_calling_generation() -> None:
    retrieval = StubRetrievalService([])
    openai_client = FakeOpenAIClient()
    service = RealRAGService(retrieval_service=retrieval, openai_client=openai_client)

    response = asyncio.run(service.query("¿Existe esta cobertura?"))
    assert "No se encontró evidencia suficiente" in response.answer
    assert response.sources == []
    assert openai_client.responses.calls == []


def test_real_rag_rejects_invalid_input() -> None:
    retrieval = StubRetrievalService([])
    service = RealRAGService(retrieval_service=retrieval, openai_client=FakeOpenAIClient())
    with pytest.raises(ValueError, match="question must not be empty"):
        asyncio.run(service.query("  "))
    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        RealRAGService(
            retrieval_service=retrieval,
            openai_client=FakeOpenAIClient(),
            top_k=0,
        )
