from fastapi.testclient import TestClient
from insurance_chatbot.app import app, get_rag_service
from insurance_chatbot.rag_service import FakeRAGService

def override_get_rag_service() -> FakeRAGService:
    """Usar el servicio simulado durante las pruebas de la API."""
    return FakeRAGService()


app.dependency_overrides[get_rag_service] = override_get_rag_service

client = TestClient(app)

def test_health_endpoint():
    """Verificar que el endpoint /health responda con status 200 y el estado operativo"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_config_endpoint():
    """Verifica que el endpoint /config retorne los parametros esperados"""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm_model" in data
    assert "embedding_model" in data
    assert "vector_store" in data
    assert "top_k" in data

def test_ask_endpoint_source():
    """Verifica que el endpoint /ask procese correctamente una pregunta valida """
    payload = {
        "question": "¿Que coberturas incluye la poliza de salud",
        "policy_id": "POL-12345",
    }
    response = client.post("/ask", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "metadata" in data
    assert isinstance(data["sources"], list)
    assert isinstance(data["metadata"], dict)

def test_ask_endpoint_invalid_payload():
    """Verifica la validacion de Pydantic cuando la pregunta tiene menos de 3 caracteres"""
    payload = {"question": "ab"}
    response = client.post("/ask", json=payload)
    assert response.status_code == 422

def test_ask_endpoint_value_error_handling():
    """Verifica el manejo de errores HTTP 400 por parametros no validos"""
    payload = {"question": "trigger_val_err test"}
    response = client.post("/ask", json=payload)
    assert response.status_code == 400
    assert "Parametros de consulta no validos" in response.json()["detail"]

def test_ask_endpoint_timeout_error_handling():
    """Verifica el manejo de errores HTTP 504 por timeout"""
    payload = {"question": "trigger_timeout test"}
    response = client.post("/ask", json=payload)
    assert response.status_code == 504
    assert "El servicio tardo en responder" in response.json()["detail"]

def test_ask_endpoint_sensitive_error_details():
    """Verifica que los errores HTTP 500 no expongan informacion sensible ni credenciales """
    payload = {"question": "trigger_internal_err test"}
    response = client.post("/ask", json=payload)
    assert response.status_code == 500

    detail = response.json()["detail"]
    assert detail == "Error interno al procesar la solicitud en el motor RAG."
    assert "postgresql" not in detail
    assert "secret" not in detail