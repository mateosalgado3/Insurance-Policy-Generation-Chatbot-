import asyncio
from types import SimpleNamespace

import pytest

from insurance_chatbot.rag_service import (
    AbstractRetrievalService,
    RealRAGService,
    RealRetrievalService,
    SourceChunk,
)


class FakeEmbeddingsAPI:
    """Simula la generación de embeddings de OpenAI."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(
        self,
        *,
        model: str,
        input: str,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "model": model,
                "input": input,
            }
        )

        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    embedding=[0.1, 0.2, 0.3],
                )
            ]
        )


class FakeResponsesAPI:
    """Simula una respuesta generada por OpenAI."""

    def __init__(
        self,
        output_text: str = "Respuesta basada en la póliza.",
    ) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    async def create(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input": input,
            }
        )

        return SimpleNamespace(
            id="response-test-001",
            output_text=self.output_text,
        )


class FakeOpenAIClient:
    """Cliente OpenAI falso para embeddings y respuestas."""

    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsAPI()
        self.responses = FakeResponsesAPI()


class FakeQdrantClient:
    """Simula una búsqueda en Qdrant."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)

        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.92,
                    payload={
                        "chunk_id": "POL320190074-art12-001",
                        "text": (
                            "La póliza cubre atención hospitalaria "
                            "de emergencia."
                        ),
                        "policy_id": "POL320190074",
                        "filename": "POL320190074.pdf",
                        "article": "Artículo 12",
                        "page": 20,
                        "document_hash": "hash-test",
                    },
                )
            ]
        )


class StubRetrievalService(AbstractRetrievalService):
    """Retrieval controlado para probar RealRAGService."""

    embedding_model = "text-embedding-test"

    def __init__(self, chunks: list[SourceChunk]) -> None:
        self.chunks = chunks
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        question: str,
        policy_id: str | None,
        top_k: int,
    ) -> list[SourceChunk]:
        self.calls.append(
            {
                "question": question,
                "policy_id": policy_id,
                "top_k": top_k,
            }
        )

        return self.chunks


def test_real_retrieval_returns_source_chunks() -> None:
    openai_client = FakeOpenAIClient()
    qdrant_client = FakeQdrantClient()

    service = RealRetrievalService(
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        embedding_model="text-embedding-test",
        collection_name="test-collection",
    )

    results = asyncio.run(
        service.search(
            question="¿Qué cubre la póliza?",
            policy_id="POL320190074",
            top_k=3,
        )
    )

    assert len(results) == 1
    assert results[0].content == (
        "La póliza cubre atención hospitalaria de emergencia."
    )
    assert results[0].source_file == "POL320190074.pdf"
    assert results[0].page_number == 20

    assert openai_client.embeddings.calls == [
        {
            "model": "text-embedding-test",
            "input": "¿Qué cubre la póliza?",
        }
    ]

    qdrant_call = qdrant_client.calls[0]
    assert qdrant_call["collection_name"] == "test-collection"
    assert qdrant_call["limit"] == 3
    assert qdrant_call["with_payload"] is True
    assert qdrant_call["query_filter"] is not None


def test_real_retrieval_searches_without_policy_filter() -> None:
    qdrant_client = FakeQdrantClient()

    service = RealRetrievalService(
        openai_client=FakeOpenAIClient(),
        qdrant_client=qdrant_client,
    )

    asyncio.run(
        service.search(
            question="¿Cuál es la vigencia?",
            policy_id=None,
            top_k=5,
        )
    )

    assert qdrant_client.calls[0]["query_filter"] is None


def test_real_retrieval_rejects_empty_question() -> None:
    service = RealRetrievalService(
        openai_client=FakeOpenAIClient(),
        qdrant_client=FakeQdrantClient(),
    )

    with pytest.raises(ValueError, match="question must not be empty"):
        asyncio.run(
            service.search(
                question="   ",
                policy_id=None,
                top_k=5,
            )
        )


def test_real_retrieval_rejects_invalid_top_k() -> None:
    service = RealRetrievalService(
        openai_client=FakeOpenAIClient(),
        qdrant_client=FakeQdrantClient(),
    )

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        asyncio.run(
            service.search(
                question="¿Qué cubre?",
                policy_id=None,
                top_k=0,
            )
        )


def test_real_rag_generates_grounded_response() -> None:
    retrieval_service = StubRetrievalService(
        chunks=[
            SourceChunk(
                content="La póliza cubre hospitalización de emergencia.",
                source_file="POL320190074.pdf",
                page_number=20,
            )
        ]
    )
    openai_client = FakeOpenAIClient()

    service = RealRAGService(
        retrieval_service=retrieval_service,
        openai_client=openai_client,
        chat_model="gpt-test",
        top_k=3,
    )

    response = asyncio.run(
        service.query(
            question="¿Qué cubre la póliza?",
            policy_id="POL320190074",
        )
    )

    assert response.answer == "Respuesta basada en la póliza."
    assert response.sources == ["POL320190074.pdf - Pág 20"]
    assert response.metadata["model"] == "gpt-test"
    assert response.metadata["embedding_model"] == (
        "text-embedding-test"
    )
    assert response.metadata["retrieved_chunks"] == 1
    assert response.metadata["is_mock"] is False

    assert retrieval_service.calls == [
        {
            "question": "¿Qué cubre la póliza?",
            "policy_id": "POL320190074",
            "top_k": 3,
        }
    ]

    generation_call = openai_client.responses.calls[0]
    assert generation_call["model"] == "gpt-test"
    assert "hospitalización de emergencia" in str(
        generation_call["input"]
    )


def test_real_rag_abstains_when_no_chunks_are_found() -> None:
    retrieval_service = StubRetrievalService(chunks=[])
    openai_client = FakeOpenAIClient()

    service = RealRAGService(
        retrieval_service=retrieval_service,
        openai_client=openai_client,
    )

    response = asyncio.run(
        service.query(
            question="¿Existe esta cobertura?",
            policy_id=None,
        )
    )

    assert "No se encontró evidencia suficiente" in response.answer
    assert response.sources == []
    assert response.metadata["retrieved_chunks"] == 0
    assert openai_client.responses.calls == []


def test_real_rag_rejects_empty_question() -> None:
    service = RealRAGService(
        retrieval_service=StubRetrievalService(chunks=[]),
        openai_client=FakeOpenAIClient(),
    )

    with pytest.raises(ValueError, match="question must not be empty"):
        asyncio.run(
            service.query(
                question="  ",
                policy_id=None,
            )
        )


def test_real_rag_rejects_invalid_top_k() -> None:
    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        RealRAGService(
            retrieval_service=StubRetrievalService(chunks=[]),
            openai_client=FakeOpenAIClient(),
            top_k=0,
        )