# Insurance Policy Generation Chatbot

Asistente RAG para consultar las pólizas QuePlan con respuestas fundamentadas y
fuentes citables. El MVP usa FastAPI, embeddings y generación de OpenAI, y un
índice Qdrant persistente local.

## Estado

- Descarga S3, EDA y perfilado de los 9 PDFs: implementados.
- Contrato FastAPI `/ask`, configuración, liveness y readiness: implementados.
- Extracción de chunks, embeddings, indexación idempotente y retrieval: implementados.
- Generación fundamentada con OpenAI Responses API: implementada.
- Frontend, noticias web y generación opcional de pólizas: fuera de este cambio.

## Instalación

Requiere Python 3.12.

```powershell
cd "C:\Users\pmate\ANYONEAI\PROYECTO FINAL"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env  # solo si .env todavía no existe
```

Los secretos viven únicamente en `.env`, que Git ignora. Para el RAG real se
necesita `OPENAI_API_KEY` con cuota API disponible. Una suscripción de ChatGPT
no incluye automáticamente saldo de API.

## Descargar y analizar el dataset

```powershell
python -m insurance_chatbot.eda --download
python scripts/profile_dataset.py
```

El EDA se guarda en `outputs/eda/` y el perfilado en `outputs/profiling/`.

## Crear o actualizar el índice

Detén FastAPI antes de ejecutar este comando, porque Qdrant embebido permite un
solo proceso sobre el directorio local:

```powershell
python -m insurance_chatbot.indexing
```

El proceso:

1. extrae texto de los 9 PDFs;
2. conserva `policy_id`, archivo, página, artículo y hash;
3. aplica el tamaño decidido por el perfilado (1.024 tokens estimados y overlap 154);
4. obtiene embeddings en lotes con OpenAI;
5. omite documentos sin cambios y reemplaza de forma segura los que cambiaron.

Si se cambia a un embedding con otra dimensión:

```powershell
python -m insurance_chatbot.indexing --recreate
```

## Levantar y comprobar la API

```powershell
python -m uvicorn insurance_chatbot.app:app --app-dir src --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- Liveness: `http://127.0.0.1:8000/health`
- Readiness real: `http://127.0.0.1:8000/ready`
- Configuración pública: `http://127.0.0.1:8000/config`

Ejemplo:

```powershell
$body = @{
  question = "¿Qué coberturas hospitalarias contempla la póliza?"
  policy_id = "POL320190074"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/ask" `
  -ContentType "application/json" `
  -Body $body
```

`/health` confirma que FastAPI está vivo. `/ready` solo devuelve 200 cuando la
clave está configurada y Qdrant contiene chunks; así el demo no aparenta estar
listo si falta una dependencia.

## Calidad

```powershell
python -m ruff check src tests
python -m pytest -q
```

El diseño y el estado técnico están en [docs/architecture.md](docs/architecture.md).
