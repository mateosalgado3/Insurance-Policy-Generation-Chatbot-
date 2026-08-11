"""Retrieval and grounded generation services."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from insurance_chatbot.schemas import AskResponse, PolicyDraftResponse, QueryMode


class IndexNotReadyError(RuntimeError):
    """Raised when the vector collection has not been populated yet."""


def _milliseconds(start: float, end: float | None = None) -> float:
    """Return a stable millisecond duration from perf-counter timestamps."""
    finish = end if end is not None else time.perf_counter()
    return round(max(0.0, finish - start) * 1000, 2)


def _latency_breakdown(
    query_started: float,
    model_started: float,
    model_completed: float,
) -> dict[str, float]:
    """Split one generated response into pre-model, model, and post-model time."""
    completed = time.perf_counter()
    return {
        "time_to_model_ms": _milliseconds(query_started, model_started),
        "model_response_time_ms": _milliseconds(model_started, model_completed),
        "postprocessing_time_ms": _milliseconds(model_completed, completed),
        "total_time_ms": _milliseconds(query_started, completed),
    }


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
    async def query(
        self,
        question: str,
        policy_id: str | None = None,
        mode: QueryMode | str = QueryMode.AUTO,
    ) -> AskResponse:
        """Answer a question using retrieved policy evidence."""


class FakeRAGService(AbstractRAGService):
    """Test-only RAG service."""

    def __init__(self, retrieval_service: AbstractRetrievalService | None = None):
        self.retrieval_service = retrieval_service or FakeRetrievalService()

    async def query(
        self,
        question: str,
        policy_id: str | None = None,
        mode: QueryMode | str = QueryMode.AUTO,
    ) -> AskResponse:
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
                "route": str(mode),
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
        mode: QueryMode | str = QueryMode.POLICIES,
    ) -> AskResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        query_started = time.perf_counter()
        chunks = await self.retrieval_service.search(
            question=normalized_question,
            policy_id=policy_id,
            top_k=self.top_k,
        )

        if not chunks:
            total_time_ms = _milliseconds(query_started)
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
                    "response_time_ms": total_time_ms,
                    "latency_ms": {
                        "time_to_model_ms": None,
                        "model_response_time_ms": None,
                        "postprocessing_time_ms": 0.0,
                        "total_time_ms": total_time_ms,
                    },
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
        model_started = time.perf_counter()
        response = await self.openai_client.responses.create(
            model=self.chat_model,
            instructions=(
                "Eres un asistente especializado en pólizas de seguros. "
                "Responde en el mismo idioma de la pregunta del usuario. "
                "Responde únicamente con base en el contexto recuperado. "
                "No inventes coberturas, exclusiones, montos ni vigencias. "
                "Cita las fuentes como [Fuente N]. "
                "Cuando la evidencia sea insuficiente, indícalo claramente. "
                "Organiza respuestas extensas con títulos y viñetas, evita repetir "
                "información y no proporciones asesoría legal."
            ),
            input=(
                f"Pregunta del usuario:\n{normalized_question}\n\nContexto recuperado:\n{context}"
            ),
        )
        model_completed = time.perf_counter()
        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("OpenAI returned an empty RAG response")

        latency_ms = _latency_breakdown(query_started, model_started, model_completed)
        return AskResponse(
            answer=answer,
            sources=list(dict.fromkeys(formatted_sources)),
            metadata={
                "model": self.chat_model,
                "embedding_model": getattr(self.retrieval_service, "embedding_model", "unknown"),
                "response_time_ms": latency_ms["total_time_ms"],
                "latency_ms": latency_ms,
                "policy_id": policy_id or "all",
                "retrieved_chunks": len(chunks),
                "retrieval_scores": retrieval_scores,
                "response_id": getattr(response, "id", None),
                "route": QueryMode.POLICIES.value,
                "is_mock": False,
            },
        )


def _object_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class OpenAIWebSearchService:
    """Current insurance information using the Responses API web-search tool."""

    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI,
        web_model: str,
        search_context_size: str = "medium",
    ) -> None:
        if search_context_size not in {"low", "medium", "high"}:
            raise ValueError("search_context_size must be low, medium, or high")
        self.openai_client = openai_client
        self.web_model = web_model
        self.search_context_size = search_context_size

    @staticmethod
    def _extract_sources(response: Any) -> list[str]:
        cited: list[tuple[str, str | None]] = []
        discovered: list[tuple[str, str | None]] = []

        for item in _object_value(response, "output", []) or []:
            if _object_value(item, "type") == "message":
                for content in _object_value(item, "content", []) or []:
                    for annotation in _object_value(content, "annotations", []) or []:
                        if _object_value(annotation, "type") == "url_citation":
                            cited.append(
                                (
                                    _object_value(annotation, "url"),
                                    _object_value(annotation, "title"),
                                )
                            )
            if _object_value(item, "type") == "web_search_call":
                action = _object_value(item, "action")
                for source in _object_value(action, "sources", []) or []:
                    discovered.append((_object_value(source, "url"), None))

        sources: list[str] = []
        seen_urls: set[str] = set()
        for url, title in [*cited, *discovered]:
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            host = urlparse(url).netloc or "web"
            sources.append(f"[Web] {title or host} — {url}")
            if len(sources) == 12:
                break
        return sources

    async def query(self, question: str) -> AskResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        query_started = time.perf_counter()
        model_started = time.perf_counter()
        response = await self.openai_client.responses.create(
            model=self.web_model,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": self.search_context_size,
                }
            ],
            include=["web_search_call.action.sources"],
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=2000,
            instructions=(
                "Busca información actual y verificable relacionada con seguros. "
                "Prioriza fuentes oficiales, reguladores y publicaciones reputadas. "
                "Distingue claramente noticias o regulación vigente de las cláusulas "
                "contractuales de una póliza. Responde en el mismo idioma de la "
                "pregunta. Responde de forma concisa, con máximo "
                "seis viñetas, e incluye citas web en la respuesta. "
                "No proporciones asesoría legal ni inventes hechos."
            ),
            input=normalized_question,
        )
        model_completed = time.perf_counter()
        answer = str(response.output_text or "").strip()
        sources = self._extract_sources(response)
        if not answer:
            answer = (
                "No fue posible generar un resumen web en este momento. "
                "Puedes revisar las fuentes recuperadas o volver a intentarlo."
            )
        latency_ms = _latency_breakdown(query_started, model_started, model_completed)
        return AskResponse(
            answer=answer,
            sources=sources,
            metadata={
                "model": self.web_model,
                "response_time_ms": latency_ms["total_time_ms"],
                "latency_ms": latency_ms,
                "web_sources": len(sources),
                "response_id": getattr(response, "id", None),
                "degraded": not bool(response.output_text),
                "route": QueryMode.WEB.value,
                "is_mock": False,
            },
        )


class AgenticRAGService(AbstractRAGService):
    """LangChain agent that routes between policy and web-search tools."""

    def __init__(
        self,
        *,
        policy_service: RealRAGService,
        web_service: OpenAIWebSearchService,
        router_model: str,
        openai_api_key: str,
        agent: Any | None = None,
    ) -> None:
        self.policy_service = policy_service
        self.web_service = web_service
        self.router_model = router_model
        self._tools = self._build_tools()
        if agent is None:
            model = ChatOpenAI(
                model=router_model,
                api_key=openai_api_key,
                temperature=0,
                timeout=30,
                max_retries=1,
            )
            agent = create_agent(
                model=model,
                tools=self._tools,
                system_prompt=(
                    "Eres el agente de enrutamiento de un asistente de seguros. "
                    "Debes llamar exactamente una herramienta y su resultado será la "
                    "respuesta final. Usa search_policy_documents para coberturas, "
                    "exclusiones, vigencias, montos o cláusulas del corpus. Usa "
                    "search_current_insurance_information para noticias, regulación o "
                    "hechos recientes. Usa compare_policy_and_web cuando el usuario pida "
                    "comparar documentos con información actual. Usa decline_out_of_scope "
                    "si la consulta no trata sobre seguros. No respondas sin herramienta."
                ),
            )
        self.agent = agent

    @staticmethod
    def _tag_route(response: AskResponse, route: QueryMode, **extra: Any) -> AskResponse:
        metadata = {**response.metadata, "route": route.value, **extra}
        return response.model_copy(update={"metadata": metadata})

    async def _combined(self, question: str, policy_id: str | None) -> AskResponse:
        query_started = time.perf_counter()
        results = await asyncio.gather(
            self.policy_service.query(question, policy_id, QueryMode.POLICIES),
            self.web_service.query(question),
            return_exceptions=True,
        )
        policy_result, web_result = results
        sections: list[str] = []
        sources: list[str] = []
        component_errors: list[str] = []

        if isinstance(policy_result, AskResponse):
            sections.append(f"## Evidencia de pólizas\n\n{policy_result.answer}")
            sources.extend(policy_result.sources)
        else:
            component_errors.append(f"policies:{type(policy_result).__name__}")
        if isinstance(web_result, AskResponse):
            sections.append(f"## Información web actual\n\n{web_result.answer}")
            sources.extend(web_result.sources)
        else:
            component_errors.append(f"web:{type(web_result).__name__}")

        if not sections:
            raise RuntimeError("Both policy and web routes failed")
        if component_errors:
            sections.append(
                "\nNo fue posible completar una de las fuentes de información; "
                "la respuesta muestra únicamente la evidencia disponible."
            )
        total_time_ms = _milliseconds(query_started)
        component_latency: dict[str, Any] = {}
        if isinstance(policy_result, AskResponse):
            component_latency["policies"] = policy_result.metadata.get("latency_ms", {})
        if isinstance(web_result, AskResponse):
            component_latency["web"] = web_result.metadata.get("latency_ms", {})
        return AskResponse(
            answer="\n\n".join(sections),
            sources=list(dict.fromkeys(sources)),
            metadata={
                "model": f"{self.policy_service.chat_model}+{self.web_service.web_model}",
                "route": QueryMode.COMBINED.value,
                "component_errors": component_errors,
                "response_time_ms": total_time_ms,
                "latency_ms": {
                    "total_time_ms": total_time_ms,
                    "parallel_components": component_latency,
                },
                "is_mock": False,
            },
        )

    @staticmethod
    def _decline(question: str) -> AskResponse:
        lowered = question.casefold()
        spanish_markers = {
            "qué",
            "que ",
            "cómo",
            "como ",
            "póliza",
            "seguro",
            "cobertura",
            "exclusión",
        }
        spanish = any(marker in lowered for marker in spanish_markers)
        answer = (
            "No puedo responder esa consulta porque está fuera del alcance de este "
            "asistente. Puedo ayudar con pólizas de seguros, coberturas, exclusiones "
            "o información reciente del sector asegurador."
            if spanish
            else "I cannot answer that request because it is outside this assistant's "
            "scope. I can help with insurance policies, coverage, exclusions, or "
            "recent insurance-sector information."
        )
        return AskResponse(
            answer=answer,
            sources=[],
            metadata={
                "route": "out_of_scope",
                "is_mock": False,
                "question_length": len(question),
            },
        )

    def _build_tools(self) -> list[Any]:
        @tool("search_policy_documents", return_direct=True)
        async def search_policy_documents(
            question: str,
            policy_id: str | None = None,
        ) -> str:
            """Answer a question from the indexed insurance-policy documents."""
            response = await self.policy_service.query(
                question,
                policy_id,
                QueryMode.POLICIES,
            )
            return self._tag_route(response, QueryMode.POLICIES).model_dump_json()

        @tool("search_current_insurance_information", return_direct=True)
        async def search_current_insurance_information(question: str) -> str:
            """Search the web for current insurance news, regulation, or facts."""
            response = await self.web_service.query(question)
            return self._tag_route(response, QueryMode.WEB).model_dump_json()

        @tool("compare_policy_and_web", return_direct=True)
        async def compare_policy_and_web(
            question: str,
            policy_id: str | None = None,
        ) -> str:
            """Combine indexed policy evidence with current web information."""
            return (await self._combined(question, policy_id)).model_dump_json()

        @tool("decline_out_of_scope", return_direct=True)
        async def decline_out_of_scope(question: str) -> str:
            """Decline questions unrelated to insurance."""
            return self._decline(question).model_dump_json()

        return [
            search_policy_documents,
            search_current_insurance_information,
            compare_policy_and_web,
            decline_out_of_scope,
        ]

    async def _dispatch(
        self,
        mode: QueryMode,
        question: str,
        policy_id: str | None,
    ) -> AskResponse:
        if mode == QueryMode.POLICIES:
            response = await self.policy_service.query(question, policy_id, mode)
            return self._tag_route(response, mode, router="explicit")
        if mode == QueryMode.WEB:
            response = await self.web_service.query(question)
            return self._tag_route(response, mode, router="explicit")
        if mode == QueryMode.COMBINED:
            response = await self._combined(question, policy_id)
            return self._tag_route(response, mode, router="explicit")
        raise ValueError(f"Unsupported explicit mode: {mode}")

    @staticmethod
    def _fallback_mode(question: str, policy_id: str | None) -> QueryMode | None:
        lowered = question.casefold()
        insurance_terms = {
            "seguro",
            "póliza",
            "poliza",
            "cobertura",
            "exclusión",
            "exclusion",
            "asegurado",
            "prima",
            "siniestro",
            "indemnización",
            "indemnizacion",
        }
        current_terms = {
            "actual",
            "hoy",
            "reciente",
            "noticia",
            "última",
            "ultima",
            "nuevo",
            "regulación",
            "regulacion",
            "internet",
            "web",
        }
        is_insurance = policy_id is not None or any(term in lowered for term in insurance_terms)
        is_current = any(term in lowered for term in current_terms)
        if is_insurance and is_current:
            return QueryMode.COMBINED
        if is_current:
            return QueryMode.WEB
        if is_insurance:
            return QueryMode.POLICIES
        return None

    async def _agent_query(self, question: str, policy_id: str | None) -> AskResponse:
        user_message = question
        if policy_id:
            user_message = f"{question}\n\nPolicy id filter: {policy_id}"
        try:
            result = await asyncio.wait_for(
                self.agent.ainvoke({"messages": [{"role": "user", "content": user_message}]}),
                timeout=60,
            )
            for message in reversed(result.get("messages", [])):
                if getattr(message, "type", None) != "tool":
                    continue
                content = getattr(message, "content", "")
                if isinstance(content, str):
                    response = AskResponse.model_validate_json(content)
                    return response.model_copy(
                        update={
                            "metadata": {
                                **response.metadata,
                                "router": "langchain_agent",
                                "router_model": self.router_model,
                            }
                        }
                    )
        except Exception:
            pass

        fallback = self._fallback_mode(question, policy_id)
        if fallback is None:
            return self._decline(question).model_copy(
                update={"metadata": {"route": "out_of_scope", "router": "fallback"}}
            )
        response = await self._dispatch(fallback, question, policy_id)
        return response.model_copy(
            update={"metadata": {**response.metadata, "router": "fallback"}}
        )

    async def query(
        self,
        question: str,
        policy_id: str | None = None,
        mode: QueryMode | str = QueryMode.AUTO,
    ) -> AskResponse:
        query_started = time.perf_counter()
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        selected_mode = QueryMode(mode)
        if selected_mode == QueryMode.AUTO:
            response = await self._agent_query(normalized_question, policy_id)
        else:
            response = await self._dispatch(selected_mode, normalized_question, policy_id)

        query_total_ms = _milliseconds(query_started)
        route_latency = response.metadata.get("latency_ms")
        route_total_ms = (
            route_latency.get("total_time_ms")
            if isinstance(route_latency, dict)
            else None
        )
        agent_overhead_ms = (
            round(max(0.0, query_total_ms - float(route_total_ms)), 2)
            if isinstance(route_total_ms, (int, float))
            else query_total_ms
        )
        return response.model_copy(
            update={
                "metadata": {
                    **response.metadata,
                    "response_time_ms": query_total_ms,
                    "query_execution_time_ms": query_total_ms,
                    "agent_overhead_time_ms": agent_overhead_ms,
                }
            }
        )


class PolicyDraftService:
    """Generate a traceable policy draft from one to three indexed policies."""

    def __init__(
        self,
        *,
        retrieval_service: AbstractRetrievalService,
        openai_client: AsyncOpenAI,
        chat_model: str,
        top_k_per_policy: int = 3,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.openai_client = openai_client
        self.chat_model = chat_model
        self.top_k_per_policy = top_k_per_policy

    async def generate(
        self,
        instructions: str,
        source_policy_ids: list[str],
    ) -> PolicyDraftResponse:
        query_started = time.perf_counter()
        policy_ids = list(dict.fromkeys(policy_id.strip() for policy_id in source_policy_ids))
        if not policy_ids or any(not policy_id for policy_id in policy_ids):
            raise ValueError("source_policy_ids must contain non-empty values")

        chunks: list[SourceChunk] = []
        for policy_id in policy_ids:
            chunks.extend(
                await self.retrieval_service.search(
                    question=instructions,
                    policy_id=policy_id,
                    top_k=self.top_k_per_policy,
                )
            )
        if not chunks:
            raise IndexNotReadyError("No source evidence was found for the requested policies")

        context_parts: list[str] = []
        sources: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.source_file
            if chunk.page_number is not None:
                source = f"{source} - Página {chunk.page_number}"
            if chunk.article:
                source = f"{source} - {chunk.article}"
            sources.append(source)
            context_parts.append(f"[Fuente {index}: {source}]\n{chunk.content}")

        context = "\n\n".join(context_parts)
        model_started = time.perf_counter()
        response = await self.openai_client.responses.create(
            model=self.chat_model,
            instructions=(
                "Redacta un borrador demostrativo de sección de póliza usando únicamente "
                "la evidencia proporcionada. Conserva las citas [Fuente N]. No inventes "
                "montos, exclusiones, jurisdicción ni requisitos. Señala cualquier dato "
                "que necesite definición humana. Incluye un encabezado visible que diga "
                "'BORRADOR PARA REVISIÓN'. No presentes el texto como asesoría legal."
            ),
            input=(
                f"Requisitos del borrador:\n{instructions}\n\n"
                f"Pólizas fuente: {', '.join(policy_ids)}\n\n"
                f"Evidencia:\n{context}"
            ),
        )
        model_completed = time.perf_counter()
        draft = response.output_text.strip()
        if not draft:
            raise RuntimeError("OpenAI returned an empty policy draft")
        latency_ms = _latency_breakdown(query_started, model_started, model_completed)
        return PolicyDraftResponse(
            draft=draft,
            sources=list(dict.fromkeys(sources)),
            metadata={
                "model": self.chat_model,
                "source_policy_ids": policy_ids,
                "retrieved_chunks": len(chunks),
                "response_id": getattr(response, "id", None),
                "response_time_ms": latency_ms["total_time_ms"],
                "latency_ms": latency_ms,
                "is_mock": False,
            },
        )
