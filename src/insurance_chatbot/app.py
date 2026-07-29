import os
import time
from fastapi import Depends, FastAPI, HTTPException, status
from insurance_chatbot.rag_service import AbstractRAGService, FakeRAGService
from insurance_chatbot.schemas import AskRequest, AskResponse, ConfigResponse

app = FastAPI(
    title="Insurance Policy RAG API",
    version="0.1.0"
)

def get_rag_service() -> AbstractRAGService:
    return FakeRAGService()


@app.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar información sobre pólizas",
    description="Recibe una pregunta y devuelve la respuesta basado en los documentos consultados"
)

async def ask_question(
    payload: AskRequest,
    rag_service: AbstractRAGService = Depends(get_rag_service),
):
    try:
        return await rag_service.query(
            question=payload.question, 
            policy_id=payload.policy_id
        )

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Parametros de consulta no validos: {str(val_err)}"
        )

    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="El servicio tardo en responder"
        )

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la solicitud en el motor RAG."
        )

@app.get(
    "/config",
    response_model=ConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar configuración del RAG",
    description="Devuelve la configuración establecida de los modelos y parametros cargados"
)

async def get_config():
    return ConfigResponse(
        llm_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        vector_store=os.getenv("VECTOR_STORE_TYPE", "Chroma"),
        top_k=int(5)
    )

@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Verificar disponibilidad del backend",
    description="Confirma el estado operativo del servicio FastAPI"   
)
async def health_check():
    return {
        "status":"healthy",
        "service":"Insurance Policy RAG API",
        "version":"0.1.0",
    }
