"""Retrieval and grounded generation services."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from insurance_chatbot.schemas import AskResponse


class IndexNotReadyError(RuntimeError):
    """Raised when the vector collection has not been populated yet."""


@dataclass(frozen=True, slots=True)
class IndexStatus:
    ready: bool
    points_count: int
    detail: str | None = None


class SourceChunk(BaseModel):
    content: str = Field(..., description="Texto extraído de los documentos.")
    source_file: str = Field(..., description="Nombre del archivo de origen.")
    page_number: int | None = Field(default=None, description="Número de página.")
    article: str | None = None
    chunk_id: str | None = None
    score: float | None = None


class AbstractRetrievalService(ABC):
    @abstractmethod
    async def search(self, question: str, policy_id: str | None, top_k: int) -> list[SourceChunk]:
        """Retrieve chunks relevant to a question."""


class RealRetrievalService(AbstractRetrievalService):
    """OpenAI query embeddings plus a local persistent Qdrant index."""

    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI | None = None,
        qdrant_client: QdrantClient | None = None,
        embedding_model: str | None = None,
        collection_name: str | None = None,
        qdrant_path: str | None = None,
        score_threshold: float | None = None,
    ) -> None:
        self.embedding_model = embedding_model or os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.collection_name = collection_name or os.getenv("QDRANT_COLLECTION", "queplan_policies")
        self.score_threshold = score_threshold
        self.openai_client = openai_client or AsyncOpenAI()
        self.qdrant_client = qdrant_client or QdrantClient(
            path=qdrant_path or os.getenv("QDRANT_PATH", "data/index/qdrant")
        )

    async def index_status(self) -> IndexStatus:
        try:
            exists = await asyncio.to_thread(
                self.qdrant_client.collection_exists, self.collection_name
            )
            if not exists:
                return IndexStatus(
                    ready=False,
                    points_count=0,
                    detail=(
                        f"Qdrant collection '{self.collection_name}' does not exist; "
                        "run the indexing command first"
                    ),
                )
            collection = await asyncio.to_thread(
                self.qdrant_client.get_collection, self.collection_name
            )
            points_count = int(collection.points_count or 0)
            return IndexStatus(
                ready=points_count > 0,
                points_count=points_count,
                detail=None if points_count else "Qdrant collection is empty",
            )
        except Exception as exc:
            return IndexStatus(
                ready=False,
                points_count=0,
                detail=f"Qdrant is unavailable: {type(exc).__name__}",
            )

    async def search(
        self,
        question: str,
        policy_id: str | None,
        top_k: int,
    ) -> list[SourceChunk]:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        status = await self.index_status()
        if not status.ready:
            raise IndexNotReadyError(status.detail or "Qdrant index is not ready")

        embedding_response = await self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=normalized_question,
        )
        query_vector = embedding_response.data[0].embedding

        query_filter = None
        if policy_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="policy_id",
                        match=models.MatchValue(value=policy_id),
                    )
                ]
            )

        query_response = await asyncio.to_thread(
            self.qdrant_client.query_points,
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            score_threshold=self.score_threshold,
        )

        chunks: list[SourceChunk] = []
        for point in query_response.points:
            payload = point.payload or {}
            content = payload.get("text") or payload.get("content")
            source_file = payload.get("filename") or payload.get("source_file")
            page = payload.get("page")
            if page is None:
                page = payload.get("page_number")
            if content is None or source_file is None:
                raise ValueError("Qdrant payload is missing text or filename")

            article = payload.get("article")
            chunks.append(
                SourceChunk(
                    content=str(content),
                    source_file=str(source_file),
                    page_number=int(page) if page is not None else None,
                    article=str(article) if article else None,
                    chunk_id=str(payload.get("chunk_id") or point.id),
                    score=float(point.score) if point.score is not None else None,
                )
            )
        return chunks


class FakeRetrievalService(AbstractRetrievalService):
    async def search(self, question: str, policy_id: str | None, top_k: int) -> list[SourceChunk]:
        return [
            SourceChunk(
                content="La póliza cubre gastos hospitalarios de emergencia hasta $10,000 USD.",
                source_file="poliza_salud_v1.pdf",
                page_number=12,
            )
        ]


class AbstractRAGService(ABC):
    @abstractmethod
    async def query(self, question: str, policy_id: str | None = None) -> AskResponse:
        """Answer a question using retrieved policy evidence."""


class FakeRAGService(AbstractRAGService):
    """Test-only RAG service."""

    def __init__(self, retrieval_service: AbstractRetrievalService | None = None):
        self.retrieval_service = retrieval_service or FakeRetrievalService()

    async def query(self, question: str, policy_id: str | None = None) -> AskResponse:
        start_time = time.perf_counter()
        if "trigger_val_err" in question:
            raise ValueError("Parámetros de consulta no válidos")
        if "trigger_timeout" in question:
            raise TimeoutError("El servicio de recuperación agotó el tiempo")
        if "trigger_internal_err" in question:
            raise RuntimeError("Database credentials leaked: postgresql://admin:secret@host")

        chunks = await self.retrieval_service.search(
            question=question, policy_id=policy_id, top_k=5
        )
        formatted_sources = [
            f"{chunk.source_file} - Página {chunk.page_number}"
            if chunk.page_number is not None
            else chunk.source_file
            for chunk in chunks
        ]
        elapsed_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return AskResponse(
            answer=(
                "La cobertura de la póliza incluye atención médica de emergencia, "
                "hospitalización y cirugías hasta el límite contratado."
            ),
            sources=formatted_sources,
            metadata={
                "model": "fake-llm",
                "embedding_model": "fake-embedding",
                "response_time_ms": elapsed_time_ms,
                "policy_id": policy_id or "all",
                "is_mock": True,
            },
        )


class RealRAGService(AbstractRAGService):
    """Grounded generation based on retrieved policy chunks and OpenAI."""

    def __init__(
        self,
        retrieval_service: AbstractRetrievalService,
        *,
        openai_client: AsyncOpenAI | None = None,
        chat_model: str | None = None,
        top_k: int = 5,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        self.retrieval_service = retrieval_service
        self.openai_client = openai_client or AsyncOpenAI()
        self.chat_model = chat_model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
        self.top_k = top_k

    async def query(
        self,
        question: str,
        policy_id: str | None = None,
    ) -> AskResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        start_time = time.perf_counter()
        chunks = await self.retrieval_service.search(
            question=normalized_question,
            policy_id=policy_id,
            top_k=self.top_k,
        )

        def elapsed_time_ms() -> float:
            return round((time.perf_counter() - start_time) * 1000, 2)

        if not chunks:
            return AskResponse(
                answer=(
                    "No se encontró evidencia suficiente en las pólizas "
                    "indexadas para responder esta pregunta."
                ),
                sources=[],
                metadata={
                    "model": self.chat_model,
                    "embedding_model": getattr(
                        self.retrieval_service, "embedding_model", "unknown"
                    ),
                    "response_time_ms": elapsed_time_ms(),
                    "policy_id": policy_id or "all",
                    "retrieved_chunks": 0,
                    "is_mock": False,
                },
            )

        context_parts: list[str] = []
        formatted_sources: list[str] = []
        retrieval_scores: list[float] = []
        for index, chunk in enumerate(chunks, start=1):
            source_label = chunk.source_file
            if chunk.page_number is not None:
                source_label = f"{source_label} - Página {chunk.page_number}"
            if chunk.article:
                source_label = f"{source_label} - {chunk.article}"
            formatted_sources.append(source_label)
            if chunk.score is not None:
                retrieval_scores.append(round(chunk.score, 4))
            context_parts.append(f"[Fuente {index}: {source_label}]\n{chunk.content}")

        context = "\n\n".join(context_parts)
        response = await self.openai_client.responses.create(
            model=self.chat_model,
            instructions=(
                "Eres un asistente especializado en pólizas de seguros. "
                "Responde únicamente con base en el contexto recuperado. "
                "No inventes coberturas, exclusiones, montos ni vigencias. "
                "Cita las fuentes como [Fuente N]. "
                "Cuando la evidencia sea insuficiente, indícalo claramente. "
                "No proporciones asesoría legal."
            ),
            input=(
                f"Pregunta del usuario:\n{normalized_question}\n\nContexto recuperado:\n{context}"
            ),
        )
        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("OpenAI returned an empty RAG response")

        return AskResponse(
            answer=answer,
            sources=list(dict.fromkeys(formatted_sources)),
            metadata={
                "model": self.chat_model,
                "embedding_model": getattr(self.retrieval_service, "embedding_model", "unknown"),
                "response_time_ms": elapsed_time_ms(),
                "policy_id": policy_id or "all",
                "retrieved_chunks": len(chunks),
                "retrieval_scores": retrieval_scores,
                "response_id": getattr(response, "id", None),
                "is_mock": False,
            },
        )
