# Plan de cierre del equipo

Este plan congela el alcance del MVP. Cualquier cambio debe resolver un defecto,
mejorar una métrica comprobable o completar evidencia para la presentación. No
se agregan frameworks, modos ni rediseños antes de cerrar QA.

## Mateo Salgado — Lead y arquitectura

**Objetivo:** entregar una versión coherente, explicable y ensayada.

- Congelar `main` después de integrar únicamente correcciones verificadas.
- Revisar el C4 de contexto, contenedores y componentes del README.
- Preparar una explicación de 90 segundos del flujo offline y runtime.
- Presentar Hit Rate/Recall/MRR, RAGAS y latencia como métricas distintas.
- Aclarar que 0.60 es un umbral interno y 12 preguntas no son un benchmark universal.
- Coordinar un ensayo de máximo diez minutos y registrar el tiempo por integrante.
- Crear el tag de entrega solo después de que Carlos y Daisy firmen el checklist.

**Aceptación:** commit final identificado, alcance congelado, demo ensayada y cada
integrante puede explicar su sección sin leer código.

## Carlos Lincango — Backend y operación

**Objetivo:** certificar que la API 0.5.0 y Docker sean reproducibles.

- Validar `/health`, `/ready`, `/config`, `/ask`, `/ask/stream` y `/generate-policy`.
- Confirmar Swagger, códigos 400/422/429/502/503/504 y errores 500 sanitizados.
- Verificar que `metadata.latency_ms` incluya hasta-modelo, modelo y total.
- Probar `policies`, `web`, `combined` y `auto` sin romper `answer/sources/metadata`.
- Ejecutar build limpio de Docker Compose y guardar logs de una consulta exitosa.
- No convertir RAGAS en endpoint: permanece como evaluación batch para controlar gasto.

**Aceptación:** ambos contenedores saludables, contratos estables, logs sin traceback
y evidencia de una respuesta que incluya el desglose de latencia.

## Nicolás Liberio — Frontend y experiencia de demo

**Objetivo:** hacer visible el comportamiento del sistema sin ocultar sus fuentes.

- Validar chips, panel de configuración, filtro por póliza y comandos del chat.
- Confirmar estados SSE, recuperación ante timeout y backend no disponible.
- Revisar que se muestren hasta-modelo, modelo y total en respuestas de pólizas.
- Probar textos largos, enlaces web, fuentes PDF y modo combinado en pantalla de demo.
- Capturar los flujos finales de `policies`, `web`, `combined` y `/draft`.
- Mantener mensajes claros en español y evitar cambios visuales amplios de último momento.

**Aceptación:** cuatro flujos capturados, enlaces utilizables, tiempos visibles y cero
estados de carga infinitos.

## David Herrera — Generación y retrieval

**Objetivo:** mejorar el caso débil sin degradar grounding ni velocidad.

- Analizar `periodo_carencia`, cuyo Answer Relevancy base es 0.3922.
- Reducir repetición y extensión conservando respuesta, citas y restricciones legales.
- Probar primero con un subconjunto usando RAGAS y nunca con cambios globales sin evidencia.
- Comparar Answer Relevancy, Context Relevance y latencia antes/después.
- Rechazar cambios que mejoren estilo pero reduzcan relevancia de contexto o trazabilidad.
- Documentar prompt, casos ejecutados, resultados y decisión de conservar o revertir.

**Aceptación:** comparación reproducible; mejora medible del caso o justificación escrita
para mantener la línea base.

## Javier Loera — Evaluación y datos

**Objetivo:** convertir las métricas en un proceso repetible y auditable.

- Ser responsable de `evaluate_retrieval.py`, `evaluate_ragas.py` y `evaluate_latency.py`.
- Ampliar las 12 preguntas hacia 30–50 casos revisados manualmente.
- Incluir preguntas sin respuesta, ambiguas y adversariales.
- Validar `relevant_chunk_ids` directamente contra los PDF y el JSONL.
- Comparar cada corrida con `ragas_baseline.json` y `latency_baseline.json`.
- Reportar media y p95; no concluir rendimiento usando una sola consulta.
- Mantener los reportes completos en `outputs/` y versionar solo líneas base compactas.

**Aceptación:** dataset sin IDs inválidos, metodología explicada y tabla comparativa de
retrieval, RAGAS y latencia.

## Daisy Llivisaca — QA y presentación

**Objetivo:** demostrar la versión exacta que será entregada.

- Ejecutar el E2E final desde un clon/configuración limpia con Docker.
- Completar checklist, capturas, logs, commit probado y resultados observados.
- Preparar diapositivas con C4, 9 PDF, 262 chunks, métricas y limitaciones.
- Explicar que tiempo del modelo incluye red y proveedor, y que no representa un SLA.
- Organizar el orden y duración de los seis participantes.
- Preparar una pregunta de pólizas como respaldo si falla Internet o web search.
- Confirmar que los borradores se presentan como material sujeto a revisión humana.

**Aceptación:** checklist firmado, presentación de máximo diez minutos, evidencia legible
y plan alternativo ensayado.

## Orden recomendado de cierre

1. David y Javier entregan comparaciones de calidad y latencia.
2. Carlos certifica backend y Docker sobre el commit candidato.
3. Nicolás captura la UI usando ese mismo commit.
4. Daisy ejecuta el E2E y congela evidencias y diapositivas.
5. Mateo revisa, etiqueta la versión y dirige el ensayo final.
