"""Public API contracts."""

from typing import Any

from pydantic import BaseModel, Field


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


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    openai_configured: bool
    index_ready: bool
    collection: str
    indexed_chunks: int
    detail: str | None = None
