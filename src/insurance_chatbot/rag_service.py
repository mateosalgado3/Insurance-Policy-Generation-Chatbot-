from abc import ABC, abstractmethod
import time
from pydantic import BaseModel, Field
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