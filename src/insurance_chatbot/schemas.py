"""Public API contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QueryMode(StrEnum):
    AUTO = "auto"
    POLICIES = "policies"
    WEB = "web"
    COMBINED = "combined"


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Pregunta del usuario sobre la póliza de seguro.",
    )
    policy_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="ID opcional de la póliza que limita la búsqueda.",
    )
    mode: QueryMode = Field(
        default=QueryMode.AUTO,
        description=(
            "Ruta de consulta: auto usa el agente; policies consulta el índice; "
            "web busca información reciente; combined usa ambas fuentes."
        ),
    )


class AskResponse(BaseModel):
    answer: str = Field(..., description="Respuesta generada por el RAG.")
    sources: list[str] = Field(
        default_factory=list,
        description="Fuentes documentales utilizadas.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos técnicos no sensibles de la respuesta.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "La póliza cubre hospitalización según la cláusula citada.",
                    "sources": ["POL320190074.pdf - Página 20"],
                    "metadata": {
                        "model": "gpt-4.1-mini",
                        "embedding_model": "text-embedding-3-small",
                        "response_time_ms": 850.4,
                        "retrieved_chunks": 3,
                    },
                }
            ]
        }
    }


class ConfigResponse(BaseModel):
    llm_model: str = Field(..., description="Modelo de lenguaje activo.")
    router_model: str = Field(..., description="Modelo usado por el agente de enrutamiento.")
    web_model: str = Field(..., description="Modelo con búsqueda web activa.")
    embedding_model: str = Field(..., description="Modelo de embeddings activo.")
    vector_store: str = Field(..., description="Base vectorial en uso.")
    collection: str = Field(..., description="Colección vectorial consultada.")
    top_k: int = Field(..., description="Cantidad máxima de chunks recuperados.")
    score_threshold: float | None = Field(
        default=None,
        description="Similitud mínima configurada; null desactiva el umbral.",
    )
    openai_configured: bool = Field(
        ...,
        description="Indica si OPENAI_API_KEY está configurada.",
    )
    available_modes: list[QueryMode] = Field(
        default_factory=lambda: list(QueryMode),
        description="Rutas disponibles para POST /ask.",
    )


class PolicyDraftRequest(BaseModel):
    instructions: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        description="Objetivo y requisitos del borrador de póliza.",
    )
    source_policy_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Entre una y tres pólizas indexadas que servirán como evidencia.",
    )


class PolicyDraftResponse(BaseModel):
    draft: str
    sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "Borrador generado para fines demostrativos. Requiere revisión legal, actuarial "
        "y de cumplimiento antes de cualquier uso."
    )


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "service": "Insurance Policy RAG API",
                    "version": "0.4.0",
                }
            ]
        }
    }


class ReadinessResponse(BaseModel):
    status: str
    openai_configured: bool
    index_ready: bool
    collection: str
    indexed_chunks: int
    detail: str | None = None
