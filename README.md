# Insurance Policy Generation Chatbot

Asistente RAG para consultar pólizas de seguros, incorporar noticias relevantes y, como capacidad opcional, proponer nuevas coberturas combinando cláusulas existentes. Las respuestas sobre pólizas deben estar fundamentadas en documentos recuperados y mostrar sus fuentes.

## Estado actual

- Repositorio y configuración segura creados.
- Descarga desde S3 parametrizada por variables de entorno.
- EDA reproducible para PDFs: extracción, calidad, duplicados, estructura legal, vocabulario y gráficos.
- Arquitectura objetivo y límites de seguridad documentados.
- Próxima fase: preprocesamiento/indexación, evaluación de recuperación, API y UI.

## Estructura mínima

```text
.
├── data/                   # raw/ e index/; contenido local ignorado por Git
├── docs/architecture.md    # diseño y diagrama Mermaid
├── outputs/                # artefactos generados; ignorados por Git
├── src/insurance_chatbot/
│   └── eda.py              # descarga + EDA ejecutable
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
