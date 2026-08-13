# Evaluación del retrieval

## Dataset

`data/evaluation/retrieval_questions.json` tiene 52 casos: los 12 originales
sobre coberturas, exclusiones, carencia, deducibles y definiciones, más 40
casos agregados para cubrir las 9 pólizas (antes solo 6 tenían preguntas) y
tres categorías que no existían:

| Tipo | Casos | Qué prueba |
|---|---:|---|
| `standard` | 34 | Pregunta con respuesta clara y `relevant_chunk_ids` verificados. |
| `unanswerable` | 7 | Pregunta razonable que ningún chunk del corpus responde (fuera de dominio, o dato que solo vive en Condiciones Particulares). Debe producir abstención, no una respuesta inventada. |
| `ambiguous` | 5 | Pregunta sin `policy_id` donde la respuesta correcta cambia según la póliza, o donde dos artículos de la misma póliza se tensionan. |
| `adversarial` | 6 | Inyección de instrucciones, número de artículo citado a propósito mal, término importado de otra póliza, pedido fuera de alcance contractual, cifra inventada o cruce entre dos pólizas con texto casi idéntico. |

Cada caso declara `type` y, cuando aplica, `note` con la justificación de por
qué el chunk citado (o la ausencia de chunk) es correcto. Los `relevant_chunk_ids`
se validaron manualmente contra `data/index/chunks.jsonl` y contra el texto de
los PDF en `data/raw/`; solo los casos `unanswerable` y `adversarial` pueden
declarar `relevant_chunk_ids: []` — cualquier otro tipo con la lista vacía
falla la carga (`evaluate_retrieval.load_cases`).

Los tres scripts (`evaluate_retrieval.py`, `evaluate_ragas.py`,
`evaluate_latency.py`) comparten este dataset vía `load_cases` y reportan
métricas agregadas y desglosadas por `type` (clave `by_type` en el reporte).
Los casos sin chunks relevantes no cuentan para `hit_rate_at_k`/`recall_at_k`/`mrr`
(división por cero indefinida); en su lugar se reporta `top_retrieved_score`
por caso, útil para calibrar `RAG_SCORE_THRESHOLD` con ejemplos negativos
reales.

52 casos siguen siendo un conjunto acotado para un MVP, no un benchmark
estadísticamente representativo, pero ya permite ver comportamiento por tipo
en vez de un promedio único.

## Resultados

### Corrida del 13 de agosto de 2026 (n=52, 43 casos con chunks etiquetados)

| Proveedor | Hit Rate@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| Hashing local | 0.6279 | 0.5930 | 0.3981 |
| OpenAI `text-embedding-3-small` | 1.0000 | 0.9341 | 0.8078 |

Comparado con la línea base de 12 preguntas (Hit Rate 1.0000, Recall 0.9167,
MRR 0.8125), el retrieval con OpenAI se mantiene estable al triplicar el
dataset: Recall@5 sube levemente (más cobertura de pólizas que antes no
tenían preguntas) y MRR se mantiene prácticamente igual. Desglose por tipo en
`outputs/evaluation/retrieval.json` → `metrics.by_type`; los casos
`ambiguous` tienen el MRR más bajo (0.7167), esperable porque varias
respuestas correctas compiten por el top-1.

Los 9 casos `unanswerable`/`adversarial` sin chunk objetivo no participan del
promedio (no tienen "relevante" contra qué medir recall), pero sí se les
midió el score del mejor resultado recuperado.

### Corrida del 11 de agosto de 2026 (n=12, línea base original)

Dos preguntas recuperaron solo uno de sus dos chunks relevantes en top-5:
la cobertura catastrófica y la definición de monto máximo.

## Decisión sobre el umbral

El punto exploratorio sobre las 43 preguntas etiquetadas (13 de agosto de
2026) fue:

```text
score_threshold candidato = 0.5974
precision etiquetada = 0.4872
recall etiquetado = 0.6909
F1 etiquetado = 0.5714
```

Los 7 casos `unanswerable` tuvieron scores del mejor resultado entre 0.49 y
0.65 — es decir, se solapan con el rango de scores de las preguntas que sí
tienen respuesta. Esto confirma, con datos, la razón por la que el umbral no
se activa globalmente: un score alto no distingue de forma confiable una
pregunta contestable de una que no lo es. Para el MVP se mantiene
`RAG_SCORE_THRESHOLD` vacío y se usa top-k=5 más abstención del generador
(el LLM decide no responder cuando el contexto no alcanza, en vez de un corte
numérico rígido).

Esto ya cumple la recomendación anterior de revisar el umbral con al menos 50
preguntas etiquetadas incluyendo casos sin respuesta y adversariales; la
conclusión con más datos es la misma que con 12: no fijar el umbral todavía.

## Evaluación RAGAS

El script `scripts/evaluate_ragas.py` ejecuta el RAG real sobre las preguntas
curadas y calcula dos métricas LLM-as-a-judge:

- **Answer Relevancy:** alineación entre la respuesta generada y la pregunta.
- **Context Relevance:** pertinencia de los chunks recuperados frente a la pregunta.

Ambas se reportan de 0 a 1. El equipo adoptó `0.60` como umbral operativo inicial;
es un criterio interno para el MVP, no un estándar universal de RAGAS. El JSON
incluye promedios, mínimos, casos aprobados, fuentes, IDs, scores de retrieval
y un desglose `by_type` (media de cada métrica por `standard`/`unanswerable`/
`ambiguous`/`adversarial`).

```powershell
uv sync --extra eval
python scripts/evaluate_ragas.py --health-threshold 0.60
```

La ejecución es secuencial para mantener predecible el consumo. `--limit 2`
permite un smoke test y `--fail-below-threshold` habilita una futura compuerta CI.
Con 52 preguntas en vez de 12, una corrida completa hace ~4.3x más llamadas al
evaluador LLM; usar `--limit` para validar cambios antes de correr el dataset
completo.

Cada corrida compara automáticamente contra `data/evaluation/ragas_baseline.json`
(clave `baseline_comparison` en el reporte, y se imprime en consola). La
comparación empareja por `id` de caso, así que agregar preguntas nuevas no
rompe la señal de regresión: solo se comparan los IDs presentes en ambos.
`--no-baseline-compare` desactiva esta comparación y `--baseline-path` permite
apuntar a otra línea base.

### Línea base del 6 de agosto de 2026 (n=12, pendiente de recorrer con el dataset ampliado)

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
Esta línea base todavía refleja las 12 preguntas originales — no se ha vuelto a
correr sobre las 52 porque cada corrida completa consume la API de OpenAI/RAGAS
y requiere aprobación explícita antes de gastar presupuesto.

## Línea base de latencia

`scripts/evaluate_latency.py` ejecuta las preguntas del dataset en modo
`policies` y usa la instrumentación incluida en cada respuesta. La corrida del
11 de agosto de 2026 (todavía sobre las 12 preguntas originales), con top-k 5,
produjo:

| Fase | Media | P50 | P95 |
|---|---:|---:|---:|
| Hasta el modelo | 475.06 ms | 479.56 ms | 795.28 ms |
| Respuesta de OpenAI | 4411.09 ms | 4416.54 ms | 6754.63 ms |
| Pipeline backend | 4886.15 ms | 4936.60 ms | 7477.79 ms |

Igual que en RAGAS, cada corrida se compara automáticamente contra
`data/evaluation/latency_baseline.json` (clave `baseline_comparison`,
emparejado por `id` de caso) y reporta media, p50 y p95 — nunca se concluye
rendimiento a partir de una sola consulta. `--no-baseline-compare` y
`--baseline-path` funcionan igual que en `evaluate_ragas.py`. Con 52 preguntas
el runtime total también crece ~4.3x frente a la línea base de 12.

La primera fase incluye embedding, Qdrant y prompt. La segunda incluye red y
generación del proveedor. La línea base compacta está en
`data/evaluation/latency_baseline.json`; se debe comparar p50 y p95 entre
corridas equivalentes, no una sola consulta aislada.
