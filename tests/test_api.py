from fastapi.testclient import TestClient

import insurance_chatbot.app as app_module
from insurance_chatbot.rag_service import FakeRAGService, IndexStatus
from insurance_chatbot.schemas import PolicyDraftResponse


def override_get_rag_service() -> FakeRAGService:
    return FakeRAGService()


app_module.app.dependency_overrides[app_module.get_rag_service] = override_get_rag_service
client = TestClient(app_module.app)


def test_health_endpoint_is_liveness_only() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Insurance Policy RAG API",
        "version": "0.4.0",
    }


def test_config_matches_real_stack() -> None:
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert data["embedding_model"] == "text-embedding-3-small"
    assert data["vector_store"] == "Qdrant (local persistent)"
    assert data["collection"] == "queplan_policies"
    assert isinstance(data["openai_configured"], bool)


def test_readiness_reports_dependencies(monkeypatch) -> None:
    class ReadyRetrieval:
        async def index_status(self) -> IndexStatus:
            return IndexStatus(ready=True, points_count=42)

    monkeypatch.setattr(app_module, "get_retrieval_service", lambda: ReadyRetrieval())
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["indexed_chunks"] == 42


def test_ask_endpoint_returns_stable_contract() -> None:
    response = client.post(
        "/ask",
        json={
            "question": "¿Qué coberturas incluye la póliza de salud?",
            "policy_id": "POL-12345",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "sources", "metadata"}
    assert isinstance(data["sources"], list)
    assert isinstance(data["metadata"], dict)


def test_ask_endpoint_accepts_explicit_web_mode() -> None:
    response = client.post(
        "/ask",
        json={"question": "Latest insurance news", "mode": "web"},
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["route"] == "web"


def test_stream_endpoint_emits_status_tokens_and_complete() -> None:
    response = client.post(
        "/ask/stream",
        json={"question": "What does the policy cover?", "mode": "policies"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert "event: token" in response.text
    assert "event: complete" in response.text
    assert "La cobertura" in response.text


def test_stream_endpoint_emits_safe_error_event() -> None:
    response = client.post(
        "/ask/stream",
        json={"question": "trigger_internal_err test"},
    )

    assert response.status_code == 200
    assert "event: error" in response.text
    assert '"status_code":500' in response.text
    assert "Error interno al procesar" in response.text
    assert "postgresql" not in response.text
    assert "secret" not in response.text


def test_generate_policy_endpoint_contract(monkeypatch) -> None:
    class FakeDraftService:
        async def generate(
            self,
            instructions: str,
            source_policy_ids: list[str],
        ) -> PolicyDraftResponse:
            return PolicyDraftResponse(
                draft="BORRADOR PARA REVISIÓN",
                sources=["POL1.pdf - Página 1"],
                metadata={"source_policy_ids": source_policy_ids},
            )

    monkeypatch.setattr(app_module, "_build_draft_service", lambda: FakeDraftService())
    response = client.post(
        "/generate-policy",
        json={
            "instructions": "Combine the hospital coverage clauses",
            "source_policy_ids": ["POL1"],
        },
    )
    assert response.status_code == 200
    assert response.json()["draft"] == "BORRADOR PARA REVISIÓN"
    assert "revisión legal" in response.json()["disclaimer"]


def test_ask_endpoint_rejects_short_question() -> None:
    response = client.post("/ask", json={"question": "ab"})
    assert response.status_code == 422


def test_ask_endpoint_maps_value_error() -> None:
    response = client.post("/ask", json={"question": "trigger_val_err test"})
    assert response.status_code == 400
    assert "no válidos" in response.json()["detail"]


def test_ask_endpoint_maps_timeout() -> None:
    response = client.post("/ask", json={"question": "trigger_timeout test"})
    assert response.status_code == 504


def test_ask_endpoint_hides_sensitive_error_details() -> None:
    response = client.post("/ask", json={"question": "trigger_internal_err test"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "Error interno al procesar la solicitud en el motor RAG."
    assert "postgresql" not in detail
    assert "secret" not in detail
