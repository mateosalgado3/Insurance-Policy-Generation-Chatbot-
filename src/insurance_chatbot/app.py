"""FastAPI entrypoint for the insurance-policy RAG service."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from qdrant_client import QdrantClient

from insurance_chatbot.rag_service import (
    AbstractRAGService,
    AgenticRAGService,
    IndexNotReadyError,
    OpenAIWebSearchService,
    PolicyDraftService,
    RealRAGService,
    RealRetrievalService,
)
from insurance_chatbot.schemas import (
    AskRequest,
    AskResponse,
    ConfigResponse,
    HealthResponse,
    PolicyDraftRequest,
    PolicyDraftResponse,
    ReadinessResponse,
)
from insurance_chatbot.settings import Settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release persistent clients cleanly when the API stops."""
    yield
    if get_retrieval_service.cache_info().currsize:
        retrieval_service = get_retrieval_service()
        await retrieval_service.openai_client.close()
        retrieval_service.qdrant_client.close()
    _build_rag_service.cache_clear()
    _build_draft_service.cache_clear()
    get_retrieval_service.cache_clear()
    get_settings.cache_clear()


app = FastAPI(
    title="Insurance Policy RAG API",
    version="0.4.0",
    description=(
        "API agente para consultar pólizas QuePlan, buscar información actual "
        "del sector y crear borradores trazables para revisión humana."
    ),
    lifespan=lifespan,
)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_retrieval_service() -> RealRetrievalService:
    settings = get_settings()
    # A placeholder lets /ready inspect Qdrant even before an API key is configured.
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key or "not-configured")
    return RealRetrievalService(
        openai_client=openai_client,
        qdrant_client=QdrantClient(path=str(settings.qdrant_path)),
        embedding_model=settings.embedding_model,
        collection_name=settings.qdrant_collection,
        score_threshold=settings.score_threshold,
    )


@lru_cache(maxsize=1)
def _build_rag_service() -> AgenticRAGService:
    settings = get_settings()
    settings.require_openai()
    retrieval_service = get_retrieval_service()
    policy_service = RealRAGService(
        retrieval_service=retrieval_service,
        openai_client=retrieval_service.openai_client,
        chat_model=settings.chat_model,
        top_k=settings.top_k,
    )
    web_service = OpenAIWebSearchService(
        openai_client=retrieval_service.openai_client,
        web_model=settings.web_model,
        search_context_size=settings.web_search_context_size,
    )
    return AgenticRAGService(
        policy_service=policy_service,
        web_service=web_service,
        router_model=settings.router_model,
        openai_api_key=settings.openai_api_key,
    )


@lru_cache(maxsize=1)
def _build_draft_service() -> PolicyDraftService:
    settings = get_settings()
    settings.require_openai()
    retrieval_service = get_retrieval_service()
    return PolicyDraftService(
        retrieval_service=retrieval_service,
        openai_client=retrieval_service.openai_client,
        chat_model=settings.chat_model,
    )


def get_rag_service() -> AbstractRAGService:
    """FastAPI dependency kept overrideable for isolated API tests."""
    try:
        return _build_rag_service()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG service is not configured: {exc}",
        ) from exc


def _public_error(exc: Exception) -> tuple[int, str]:
    """Map internal failures to stable, non-sensitive API errors."""
    if isinstance(exc, ValueError):
        return status.HTTP_400_BAD_REQUEST, f"Parámetros de consulta no válidos: {exc}"
    if isinstance(exc, IndexNotReadyError):
        return status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
    if isinstance(exc, (TimeoutError, APITimeoutError)):
        return (
            status.HTTP_504_GATEWAY_TIMEOUT,
            "El servicio externo tardó demasiado en responder.",
        )
    if isinstance(exc, RateLimitError):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "OpenAI rechazó temporalmente la solicitud por límite de uso.",
        )
    if isinstance(exc, APIConnectionError):
        return status.HTTP_502_BAD_GATEWAY, "No fue posible conectar con OpenAI."
    return (
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Error interno al procesar la solicitud en el motor RAG.",
    )


def _sse(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _answer_chunks(answer: str, size: int = 24) -> list[str]:
    return [answer[start : start + size] for start in range(0, len(answer), size)]


def _progress_message(mode: str) -> str:
    messages = {
        "auto": "Analizando la consulta y seleccionando la mejor ruta…",
        "policies": "Buscando evidencia en las pólizas indexadas…",
        "web": "Consultando fuentes web verificables…",
        "combined": "Consultando pólizas y fuentes web en paralelo…",
    }
    return messages.get(mode, messages["auto"])


@app.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar información sobre pólizas",
    description=(
        "Recibe una pregunta, recupera evidencia desde Qdrant y genera "
        "una respuesta fundamentada con OpenAI."
    ),
)
async def ask_question(
    payload: AskRequest,
    rag_service: AbstractRAGService = Depends(get_rag_service),
) -> AskResponse:
    try:
        return await rag_service.query(
            question=payload.question,
            policy_id=payload.policy_id,
            mode=payload.mode,
        )
    except Exception as exc:
        status_code, detail = _public_error(exc)
        if status_code >= 500:
            logger.exception("RAG request failed", extra={"mode": payload.mode.value})
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.post(
    "/ask/stream",
    response_class=StreamingResponse,
    summary="Consultar el RAG con progreso y respuesta por SSE",
    description=(
        "Emite eventos status, token, complete o error usando Server-Sent Events. "
        "El contrato estable de POST /ask se conserva para otros clientes."
    ),
)
async def ask_question_stream(
    payload: AskRequest,
    rag_service: AbstractRAGService = Depends(get_rag_service),
) -> StreamingResponse:
    request_id = str(uuid4())

    async def event_stream() -> AsyncIterator[str]:
        yield _sse(
            "status",
            {"request_id": request_id, "message": _progress_message(payload.mode.value)},
        )
        query_task = asyncio.create_task(
            rag_service.query(
                question=payload.question,
                policy_id=payload.policy_id,
                mode=payload.mode,
            )
        )
        try:
            elapsed_seconds = 0
            while not query_task.done():
                done, _ = await asyncio.wait({query_task}, timeout=1)
                if done:
                    break
                elapsed_seconds += 1
                yield _sse(
                    "status",
                    {
                        "request_id": request_id,
                        "message": (
                            f"{_progress_message(payload.mode.value)} "
                            f"{elapsed_seconds}s"
                        ),
                    },
                )
            result = query_task.result()
        except asyncio.CancelledError:
            query_task.cancel()
            raise
        except Exception as exc:
            status_code, detail = _public_error(exc)
            if status_code >= 500:
                logger.exception(
                    "Streaming RAG request failed",
                    extra={"mode": payload.mode.value, "request_id": request_id},
                )
            yield _sse(
                "error",
                {
                    "request_id": request_id,
                    "status_code": status_code,
                    "detail": detail,
                },
            )
            return

        yield _sse(
            "status",
            {"request_id": request_id, "message": "Preparando respuesta y fuentes…"},
        )
        for chunk in _answer_chunks(result.answer):
            yield _sse("token", {"request_id": request_id, "text": chunk})
        yield _sse(
            "complete",
            {
                "request_id": request_id,
                "sources": result.sources,
                "metadata": result.metadata,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/generate-policy",
    response_model=PolicyDraftResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar un borrador trazable de póliza",
    description=(
        "Recombina evidencia recuperada de una a tres pólizas. El resultado es "
        "solo un borrador y exige revisión legal, actuarial y de cumplimiento."
    ),
)
async def generate_policy_draft(payload: PolicyDraftRequest) -> PolicyDraftResponse:
    try:
        return await _build_draft_service().generate(
            instructions=payload.instructions,
            source_policy_ids=payload.source_policy_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parámetros de generación no válidos: {exc}",
        ) from exc
    except IndexNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (TimeoutError, APITimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="El servicio externo tardó demasiado en responder.",
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI rechazó temporalmente la solicitud por límite de uso.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible conectar con OpenAI.",
        ) from exc
    except Exception as exc:
        logger.exception("Policy draft generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el borrador de póliza.",
        ) from exc


@app.get(
    "/config",
    response_model=ConfigResponse,
    summary="Ver la configuración pública del RAG",
)
async def get_config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        llm_model=settings.chat_model,
        router_model=settings.router_model,
        web_model=settings.web_model,
        embedding_model=settings.embedding_model,
        vector_store="Qdrant (local persistent)",
        collection=settings.qdrant_collection,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
        openai_configured=settings.openai_configured,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Comprobar que FastAPI está vivo",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="Insurance Policy RAG API",
        version=app.version,
    )


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Comprobar que el RAG puede recibir consultas",
)
async def readiness_check(response: Response) -> ReadinessResponse:
    settings = get_settings()
    index_status = await get_retrieval_service().index_status()
    ready = settings.openai_configured and index_status.ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    details: list[str] = []
    if not settings.openai_configured:
        details.append("OPENAI_API_KEY is not configured")
    if index_status.detail:
        details.append(index_status.detail)

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        openai_configured=settings.openai_configured,
        index_ready=index_status.ready,
        collection=settings.qdrant_collection,
        indexed_chunks=index_status.points_count,
        detail="; ".join(details) or None,
    )
