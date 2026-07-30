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
