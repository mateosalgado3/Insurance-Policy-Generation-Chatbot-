from typing import Any, Dict, List
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Pregunta del usuario sobre la póliza del seguro."
    )
    policy_id: str | None = Field(
        default=None,
        description="ID de la poliza"
    )

class AskResponse(BaseModel):
    answer: str = Field(
        ...,
        description="Respuesta generada por el RAG"
    )
    sources: list[str] = Field(
        default_factory=list, 
        description="Lista de fuentes consultadas"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos involucrados en la respuesta del modelo"
    )

    # Ejemplo
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "La poliza del seguro cubre gastos de hospitalizacion de hasta 10.000 USD-Esto solo es un ejemplo",
                    "sources": ["health_policy_inventada.pdf - Pagina 0"],
                    "metadata": {
                        "model":"gpt-o1",
                        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                        "response_time_ms": 5000
                    }
                }
            ]
        }
    }

class ConfigResponse(BaseModel):
    llm_model: str = Field(
        ...,
        description="Nombre del modelo de lenguaje activo"
    )
    embedding_model: str = Field(
        ...,
        description="Modelo utilizado para generar embeddings vectoriales"
    )
    vector_store: str = Field(
        ...,
        description="Base de datos vectorial en uso"
    )
    top_k: int = Field(
        ...,
        description="Numero de fragmentos/documentos recuperados por consulta"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "llm_model": "gpt-4.1-mini",
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                    "vector_store": "Chroma/FAISS/Pinecone",
                    "top_k": 5,
                }
            ]
        }
    }
