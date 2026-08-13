# Evaluación del retrieval

## Dataset

Se curaron 12 preguntas sobre coberturas, exclusiones, carencia, deducibles y
definiciones. Cada pregunta declara la póliza y uno o más `chunk_id` relevantes.
Los IDs se validan contra el JSONL antes de ejecutar la evaluación.

El conjunto es pequeño y sirve como prueba del MVP, no como benchmark
estadísticamente representativo.

## Resultados

| Proveedor | Hit Rate@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| Hashing local | 0.6667 | 0.5833 | 0.4097 |
| OpenAI `text-embedding-3-small` | 1.0000 | 0.9167 | 0.8125 |

La evaluación OpenAI usa una sola llamada batch para las 12 preguntas y no
regenera los embeddings de documentos.

Dos preguntas recuperaron solo uno de sus dos chunks relevantes en top-5:
la cobertura catastrófica y la definición de monto máximo. Deben ampliarse los
casos antes de considerar definitivos los parámetros.

## Decisión sobre el umbral

El mejor punto exploratorio sobre las etiquetas actuales fue:

```text
score_threshold candidato = 0.5762
precision etiquetada = 0.5652
recall etiquetado = 0.7222
F1 etiquetado = 0.6341
```

No se activa globalmente todavía. Los scores relevantes variaron
aproximadamente entre 0.35 y 0.67; fijar 0.5762 descartaría preguntas válidas,
como la consulta de códigos CIE-10. Para el MVP se mantiene
`RAG_SCORE_THRESHOLD` vacío y se usa top-k=5 más abstención del generador.

Se recomienda revisar el umbral cuando existan al menos 50 preguntas
etiquetadas, incluyendo consultas sin respuesta y preguntas adversariales.

## Evaluación RAGAS

El script `scripts/evaluate_ragas.py` ejecuta el RAG real sobre las mismas 12
preguntas curadas y calcula dos métricas LLM-as-a-judge:

- **Answer Relevancy:** alineación entre la respuesta generada y la pregunta.
- **Context Relevance:** pertinencia de los chunks recuperados frente a la pregunta.

Ambas se reportan de 0 a 1. El equipo adoptó `0.60` como umbral operativo inicial;
es un criterio interno para el MVP, no un estándar universal de RAGAS. El JSON
incluye promedios, mínimos, casos aprobados, fuentes, IDs y scores de retrieval.

```powershell
uv sync --extra eval
python scripts/evaluate_ragas.py --health-threshold 0.60
```

La ejecución es secuencial para mantener predecible el consumo. `--limit 2`
permite un smoke test y `--fail-below-threshold` habilita una futura compuerta CI.

### Línea base del 6 de agosto de 2026

| Métrica RAGAS | Promedio | Casos sobre 0.60 | Estado |
|---|---:|---:|---|
| Answer Relevancy | 0.7053 | 11/12 | Saludable |
| Context Relevance | 0.9792 | 12/12 | Saludable |
| Promedio combinado | 0.8422 | — | Saludable |

La respuesta sobre `periodo_carencia` obtuvo `0.3922` de relevancia aunque sus
contextos obtuvieron `1.0`. La respuesta contiene la información solicitada, pero
es extensa y repetitiva; queda como caso objetivo para mejorar concisión sin
debilitar citas ni fidelidad. La línea base compacta y versionada está en
`data/evaluation/ragas_baseline.json`; el reporte completo permanece en `outputs/`.

## Línea base de latencia

`scripts/evaluate_latency.py` ejecuta las 12 preguntas en modo `policies` y usa
la instrumentación incluida en cada respuesta. La corrida del 11 de agosto de
2026, con top-k 5, produjo:

| Fase | Media | P50 | P95 |
|---|---:|---:|---:|
| Hasta el modelo | 475.06 ms | 479.56 ms | 795.28 ms |
| Respuesta de OpenAI | 4411.09 ms | 4416.54 ms | 6754.63 ms |
| Pipeline backend | 4886.15 ms | 4936.60 ms | 7477.79 ms |

La primera fase incluye embedding, Qdrant y prompt. La segunda incluye red y
generación del proveedor. La línea base compacta está en
`data/evaluation/latency_baseline.json`; se debe comparar p50 y p95 entre
corridas equivalentes, no una sola consulta aislada.
