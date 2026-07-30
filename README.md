# Insurance Policy Generation Chatbot

Asistente RAG para consultar las pólizas QuePlan con respuestas fundamentadas
y fuentes citables. El MVP usa FastAPI, OpenAI y un índice Qdrant persistente.

## Estado

- Descarga S3, EDA y perfilado de 9 PDFs: implementados.
- FastAPI `/ask`, `/config`, `/health` y `/ready`: implementados.
- Chunking canónico por artículos, indexación versionada y retrieval: implementados.
- Índice compartido: 262 chunks con `text-embedding-3-small`.
- Evaluación: 12 preguntas curadas, Hit Rate@5 1.00, Recall@5 0.9167 y MRR 0.8125.
- Frontend, noticias web y generación opcional de pólizas: siguientes fases.

## Instalación

```powershell
cd "C:\Users\pmate\ANYONEAI\PROYECTO FINAL"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env  # solo si .env todavía no existe
```

Los secretos viven únicamente en `.env`, que Git ignora.

## Datos, EDA y chunking

```powershell
python -m insurance_chatbot.eda --download
python scripts/profile_dataset.py
python scripts/chunk_policies.py
```

El chunker no llama a OpenAI. Produce determinísticamente los 262 registros de
`data/index/chunks.jsonl` usando 1.024 tokens estimados y overlap de 154.

## Índice compartido sin volver a pagar embeddings

El repositorio incluye un snapshot Qdrant compatible con los 262 chunks. Para
verificar y versionar su metadata sin llamadas a OpenAI:

```powershell
python -m insurance_chatbot.indexing --metadata-only
```

El comando normal también es idempotente:

```powershell
python -m insurance_chatbot.indexing
```

Si `chunk_id`, modelo y versión coinciden, reutiliza los 262 vectores y realiza
cero llamadas. Solo genera embeddings cuando el corpus o la versión cambia.

El snapshot contiene texto extraído de las pólizas. El repositorio debe
mantenerse privado hasta confirmar los permisos de redistribución del dataset.

## Evaluación de retrieval

Línea base local sin costo:

```powershell
python scripts/evaluate_retrieval.py --provider local --top-k 5
```

Evaluación del índice OpenAI —una sola llamada batch para las preguntas:

```powershell
python scripts/evaluate_retrieval.py --provider openai --top-k 5
```

Los resultados se guardan en `outputs/evaluation/retrieval.json`. Consulta las
decisiones y limitaciones en [docs/evaluation.md](docs/evaluation.md).

## Levantar la API

```powershell
python -m uvicorn insurance_chatbot.app:app --app-dir src --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- Liveness: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/ready`
- Configuración pública: `http://127.0.0.1:8000/config`

## Calidad

```powershell
$env:MPLBACKEND="Agg"
python -m ruff check src scripts tests
python -m pytest -q
```

La arquitectura está en [docs/architecture.md](docs/architecture.md).
