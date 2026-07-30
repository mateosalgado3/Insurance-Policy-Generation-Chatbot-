"""FastAPI entrypoint for the insurance-policy RAG service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Response, status
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
    version="0.3.0",
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parámetros de consulta no válidos: {exc}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar la solicitud en el motor RAG.",
        ) from exc


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
