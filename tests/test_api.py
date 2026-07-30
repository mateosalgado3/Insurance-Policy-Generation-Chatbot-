from fastapi.testclient import TestClient

import insurance_chatbot.app as app_module
from insurance_chatbot.rag_service import FakeRAGService, IndexStatus


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
        "version": "0.2.0",
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
