# Runbook de demo y QA

Este documento deja a Daisy una secuencia reproducible para validar, capturar
evidencia y preparar la presentación.

## 1. Preflight

```powershell
cd "C:\Users\pmate\ANYONEAI\PROYECTO FINAL"
git pull --ff-only origin main
docker compose config
docker compose up --build -d
docker compose ps
```

Validar:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/config
```

Esperado: API saludable, `status=ready`, `indexed_chunks=262` y frontend
disponible en `http://127.0.0.1:8001`.

## Explicación de arquitectura (90 segundos, inglés)

> Our system has two complementary flows. Offline, nine QuePlan PDFs are
> extracted, profiled and split into 262 deterministic, article-aware chunks.
> OpenAI creates document embeddings once and the resulting Qdrant snapshot is
> versioned, so teammates can run the demo without rebuilding the index. At
> runtime, the user interacts with Chainlit on port 8001. Chainlit calls the
> FastAPI service on port 8000 through REST or Server-Sent Events. The LangChain
> agent selects one of three routes: policies, web, or combined. The policies
> route embeds the question, retrieves the top five chunks from local Qdrant and
> asks GPT-4.1 mini to answer only from that evidence with citations. The web
> route uses OpenAI web search and preserves source URLs. Combined runs both
> routes in parallel and keeps contractual and current information separate.
> Every response returns answer, sources and metadata, including route,
> retrieval scores and latency. Retrieval metrics measure whether the correct
> chunks were found; RAGAS evaluates answer and context relevance; latency
> measures time to the model, model response and total execution. Drafts are
> traceable, review-only outputs, never final legal policies.

## Ensayo de diez minutos

| Tiempo | Responsable | Contenido |
|---:|---|---|
| 0:00–1:30 | Mateo | Problema, alcance y C4 |
| 1:30–2:40 | Carlos | API, Docker, contratos y errores |
| 2:40–3:40 | Nicolás o Mateo | Frontend, SSE, fuentes y tiempos |
| 3:40–4:50 | David | `periodo_carencia` y decisión basada en evidencia |
| 4:50–6:15 | Javier | Retrieval, RAGAS y latencia |
| 6:15–8:30 | Daisy | Demo `policies`, `web`, `combined` y borrador |
| 8:30–9:30 | Mateo | Limitaciones, conclusiones y respaldo offline |
| 9:30–10:00 | Equipo | Margen para transición o una pregunta |

Si Nicolás no participa, Mateo cubre el frontend sin cambiar el orden de la
demo. La pregunta de respaldo offline es: `¿Qué es el período de carencia y
desde cuándo se cuenta?`, en modo `policies`.

## 2. Casos de demostración

### Pólizas

```text
/mode policies
¿Qué gastos de hospitalización cubre la póliza cuando ocurre un accidente?
```

Comprobar: ruta `policies`, fuentes PDF y citas `[Fuente N]`.

### Web actual

```text
/mode web
¿Cuáles son las noticias recientes más relevantes del sector asegurador en Chile?
```

Comprobar: ruta `web` y al menos una fuente con URL.

### Combinado

```text
/mode combined
Compara la cobertura catastrófica de las pólizas con información actual del sector.
```

Comprobar: secciones separadas “Evidencia de pólizas” e “Información web actual”.

### Fuera de alcance

```text
/mode auto
¿Cuál es la receta de una pizza?
```

Comprobar: rechazo breve, sin inventar fuentes.

### Borrador

```text
/draft POL320200071,POL320150503 | Combine las cláusulas de cobertura hospitalaria y señale los datos que requieren definición humana
```

Comprobar: encabezado `BORRADOR PARA REVISIÓN`, fuentes y disclaimer.

## 3. Evidencia para la presentación

Capturar:

1. `docker compose ps` con ambos servicios saludables.
2. `/ready` mostrando 262 chunks.
3. Una respuesta de póliza con fuentes.
4. Una respuesta web con URL.
5. Una respuesta combinada.
6. Un borrador con disclaimer.
7. Resultado de `python -m pytest -q`.
8. Diagramas C4 del `README.md`.

## 4. Cierre

```powershell
docker compose logs --tail 100
docker compose down
```

Registrar cualquier fallo con: pregunta exacta, modo, hora, código HTTP,
captura y últimas líneas de logs. No compartir `.env` ni la API key.
