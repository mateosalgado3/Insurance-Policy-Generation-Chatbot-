from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from insurance_chatbot.schemas import AskResponse

class SourceChunk(BaseModel):
    content: str = Field(
        ...,
        description="Texto extraido de los docuemntos",
    )
    source_file: str = Field(
        ...,
        description="Nombre del archivo origen"
    )
    page_number: int | None = Field(
        default=None, description="Número de la pagina de la poliza"
    )

class AbstractRetrievalService(ABC):

    @abstractmethod
    async def search(
        self, question: str, policy_id: str | None, top_k: int
    ) -> list[SourceChunk]:
        pass


class RealRetrievalService(AbstractRetrievalService):
    """Retrieval real usando OpenAI embeddings y Qdrant local."""

    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI | None = None,
        qdrant_client: QdrantClient | None = None,
        embedding_model: str | None = None,
        collection_name: str | None = None,
        qdrant_path: str | None = None,
    ) -> None:
        self.embedding_model = embedding_model or os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        )
        self.collection_name = collection_name or os.getenv(
            "QDRANT_COLLECTION",
            "queplan_policies",
        )

        self.openai_client = openai_client or AsyncOpenAI()

        self.qdrant_client = qdrant_client or QdrantClient(
            path=qdrant_path
            or os.getenv(
                "QDRANT_PATH",
                "data/index/qdrant",
            )
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
                raise ValueError(
                    "Qdrant payload is missing text or filename"
                )

            chunks.append(
                SourceChunk(
                    content=str(content),
                    source_file=str(source_file),
                    page_number=int(page) if page is not None else None,
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
    async def query(
        self, question: str, policy_id: str | None = None
    ) -> AskResponse:
        pass

class FakeRAGService(AbstractRAGService):
    """Implementación de prueba del servicio RAG."""
    def __init__(self, retrieval_service: AbstractRetrievalService | None = None):
        self.retrieval_service = retrieval_service or FakeRetrievalService()

    async def query(self, question: str, policy_id: str | None = None) -> AskResponse:
        start_time = time.perf_counter()

        if "trigger_val_err" in question:
            raise ValueError("Parametros de consulta no validos")
        if "trigger_timeout" in question:
            raise TimeoutError("El servicio de recuperaciòn agoto el tiempo")
        if "trigger_internal_err" in question:
            raise RuntimeError("Database credentials leaked: postgresql://admin:secret@host")

        chunks = await self.retrieval_service.search(
            question=question, policy_id=policy_id, top_k=5
        )

        formatted_sources = [
            f"{chunk.source_file} - Pág {chunk.page_number}"
            if chunk.page_number
            else chunk.source_file
            for chunk in chunks
        ]

        elapsed_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return AskResponse(
            answer=(
                "La cobertura de la póliza incluye atención médica de emergencia,"
                "hospitalización y cirugías hasta el límite contratado."
            ),
            sources=formatted_sources, 
            metadata={
                "model": "Implementacion Fake de llm service",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "response_time_ms": elapsed_time_ms,
                "policy_id": policy_id or "all",
                "is_mock": True
            },
        )
class RealRAGService(AbstractRAGService):
    """Servicio RAG real basado en retrieval y OpenAI."""

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
        self.chat_model = chat_model or os.getenv(
            "OPENAI_CHAT_MODEL",
            "gpt-4.1-mini",
        )
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

        if not chunks:
            elapsed_time_ms = round(
                (time.perf_counter() - start_time) * 1000,
                2,
            )

            return AskResponse(
                answer=(
                    "No se encontró evidencia suficiente en las pólizas "
                    "indexadas para responder esta pregunta."
                ),
                sources=[],
                metadata={
                    "model": self.chat_model,
                    "embedding_model": getattr(
                        self.retrieval_service,
                        "embedding_model",
                        "unknown",
                    ),
                    "response_time_ms": elapsed_time_ms,
                    "policy_id": policy_id or "all",
                    "retrieved_chunks": 0,
                    "is_mock": False,
                },
            )

        context_parts: list[str] = []
        formatted_sources: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            source_label = chunk.source_file

            if chunk.page_number is not None:
                source_label = (
                    f"{chunk.source_file} - Pág {chunk.page_number}"
                )

            formatted_sources.append(source_label)

            context_parts.append(
                f"[Fuente {index}: {source_label}]\n"
                f"{chunk.content}"
            )

        context = "\n\n".join(context_parts)

        response = await self.openai_client.responses.create(
            model=self.chat_model,
            instructions=(
                "Eres un asistente especializado en pólizas de seguros. "
                "Responde únicamente con base en el contexto recuperado. "
                "No inventes coberturas, exclusiones, montos ni vigencias. "
                "Cuando la evidencia sea insuficiente, indícalo claramente. "
                "No proporciones asesoría legal."
            ),
            input=(
                f"Pregunta del usuario:\n{normalized_question}\n\n"
                f"Contexto recuperado:\n{context}"
            ),
        )

        answer = response.output_text.strip()

        if not answer:
            raise RuntimeError("OpenAI returned an empty RAG response")

        elapsed_time_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        return AskResponse(
            answer=answer,
            sources=list(dict.fromkeys(formatted_sources)),
            metadata={
                "model": self.chat_model,
                "embedding_model": getattr(
                    self.retrieval_service,
                    "embedding_model",
                    "unknown",
                ),
                "response_time_ms": elapsed_time_ms,
                "policy_id": policy_id or "all",
                "retrieved_chunks": len(chunks),
                "response_id": getattr(response, "id", None),
                "is_mock": False,
            },
        )