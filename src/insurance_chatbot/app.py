import os
import time
from fastapi import FastAPI, HTTPException, status
from insurance_chatbot.schemas import AskRequest, AskResponse, ConfigResponse

app = FastAPI(
    title="Insurance Policy RAG API",
    version="0.1.0"
)

@app.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar información sobre pólizas",
    description="Recibe una pregunta y devuelve la respuesta basado en los documentos consultados"
)

async def ask_question(payload: AskRequest):
    start_time = time.perf_counter()

    # try:
    #     result = await rag_service.query(
    #         question=payload.question, 
    #         policy_id=payload.policy_id
    #     )

    #     execution_time_sec = round(time.perf_counter() - start_time, 3)

    #     metadata = {
    #         "model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
    #         "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    #         "response_time_sec": execution_time_sec,
    #     }

    #     if "metadata" in result and isinstance(result["metadata"], dict):
    #         metadata.update(result["metadata"])

    #     return AskResponse(
    #         answer=result["answer"],
    #         sources=result["sources"],
    #         metadata=metadata
    #     )

    try:
        rag_answer = "La cobertura incluye gastos hospitalarios..."
        rag_sources = ["poliza_salud_v1.pdf - Pág 12"]
        model_used = "gpt-4o-mini"

        elapsed_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        dynamic_metadata = {
            "model": model_used,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "response_time_ms": elapsed_time_ms,
        }


        return AskResponse(
            answer=rag_answer, sources=rag_sources, metadata=dynamic_metadata
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
            detail=f"Error interno al procesar la solicitud en el motor RAG: {str(err)}"
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
