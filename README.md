# Insurance Policy Generation Chatbot

Asistente RAG para consultar pólizas de seguros, incorporar noticias relevantes y, como capacidad opcional, proponer nuevas coberturas combinando cláusulas existentes. Las respuestas sobre pólizas deben estar fundamentadas en documentos recuperados y mostrar sus fuentes.

## Estado actual

- Repositorio y configuración segura creados.
- Descarga desde S3 parametrizada por variables de entorno.
- EDA reproducible para PDFs: extracción, calidad, duplicados, estructura legal, vocabulario y gráficos.
- Perfilado real para split y chunking implementado y probado.
- Contratos FastAPI `/ask` y `/config` creados; `/ask` todavía usa una respuesta simulada.
- Arquitectura simplificada con estado y evidencia documentados.
- Próxima fase: chunking, embeddings, Qdrant y retrieval real.

## Estructura mínima

```text
.
├── data/                   # raw/ e index/; contenido local ignorado por Git
├── docs/architecture.md    # diseño y diagrama Mermaid
├── outputs/                # artefactos generados; ignorados por Git
├── scripts/
│   └── profile_dataset.py  # split train/test, nulos/duplicados/longitudes y propuesta de chunking
├── src/insurance_chatbot/
│   ├── app.py              # FastAPI; contrato creado, RAG aún simulado
│   ├── schemas.py          # contratos de entrada/salida
│   └── eda.py              # descarga + EDA ejecutable
├── tests/
│   └── test_profile_dataset.py
├── .env.example
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Instalación local

Se recomienda Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env  # solo si todavía no existe
```

Completar `.env` con `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`. El script usa además `S3_BUCKET` y `S3_PREFIX`; nunca recibe secretos como argumentos ni los imprime.

## Descargar los datos y ejecutar el EDA

```powershell
# Prueba rápida sobre 10 documentos
python -m insurance_chatbot.eda --download --limit 10

# Corpus completo (los archivos ya descargados se omiten si su tamaño coincide)
python -m insurance_chatbot.eda --download

# Repetir el análisis sin volver a descargar
python -m insurance_chatbot.eda
```

Los resultados quedan en `outputs/eda/`:

- `report.md`: resumen ejecutivo y recomendaciones.
- `document_metrics.csv`: métricas y banderas por PDF.
- `near_duplicates.csv`: documentos con similitud coseno ≥ 0.90.
- `top_terms.csv`: perfil léxico del corpus.
- `summary.json`: métricas agregadas para automatización.
- `eda_overview.png`: tablero visual de calidad y distribución.

## Perfilado del dataset para chunking (train/test, nulos, duplicados, longitudes)

`scripts/profile_dataset.py` reutiliza la auditoría de `insurance_chatbot.eda` (nulos,
duplicados exactos/casi duplicados, longitudes) y agrega lo que ese módulo no cubre:

- un split train/test a nivel documento, agrupando duplicados y casi-duplicados para que
  no aparezcan en ambos lados del split (ver supuesto abajo),
- la distribución de longitud por artículo/cláusula detectado, y
- una grilla de chunks estimados por combinación de `chunk_size`/`chunk_overlap`, con una
  propuesta final justificada por esa distribución.

```powershell
python scripts/profile_dataset.py
# con overrides:
python scripts/profile_dataset.py --test-ratio 0.2 --target-coverage 0.9 --overlap-ratio 0.15
```

Los resultados quedan en `outputs/profiling/`: `report.md`, `document_metrics.csv`,
`article_lengths.csv`, `train_test_split.csv`, `chunk_estimates.csv`, `chunking_evidence.png`
y `summary.json`.

**Supuesto sobre "train/test":** este corpus son PDFs de pólizas, no un dataset etiquetado.
Se asume que el split es a nivel documento para evaluación de recuperación más adelante
(`train` = corpus indexado, `test` = holdout para construir preguntas de evaluación, ver
"Evaluación antes del demo" en [docs/architecture.md](docs/architecture.md)). Este supuesto
no estaba definido en el enunciado del proyecto; queda documentado en `report.md` para
poder ajustarlo si el mentor tiene otro criterio en mente.

## API actual

```powershell
python -m uvicorn insurance_chatbot.app:app --app-dir src --reload
```

Swagger queda disponible en `http://127.0.0.1:8000/docs`. Los contratos de `/ask` y
`/config` están implementados, pero `/ask` aún devuelve una respuesta simulada hasta
conectar chunking, embeddings, Qdrant, retrieval y OpenAI.

## Docker

```powershell
docker build -t insurance-policy-eda .
docker run --rm --env-file .env `
  -v "${PWD}\data:/app/data" `
  -v "${PWD}\outputs:/app/outputs" `
  insurance-policy-eda --download
```

## Criterios de aceptación del EDA

1. Todo PDF descargado aparece en `document_metrics.csv`, incluso si falla su extracción.
2. Los PDFs escaneados o con cobertura de texto menor al 25 % quedan marcados para OCR.
3. Los duplicados exactos se detectan por hash binario y por hash de texto normalizado.
4. La similitud semántico-léxica solo genera candidatos; no se interpreta como equivalencia legal.
5. Ninguna clave, texto de póliza o artefacto generado se versiona por defecto.

Consulta el diseño completo en [docs/architecture.md](docs/architecture.md).
