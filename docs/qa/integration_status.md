# Integration Status

## Overall QA Status

| Area | Status |
|---|---|
| Backend API | Validated |
| Chainlit Frontend | Validated |
| Policy Retrieval | Validated |
| Combined Mode | Validated |
| Draft Generation | Validated |
| Web Mode | Validated |
| QA Evidence Package | Finalized |
| Demo Runbook | Finalized |
| Streaming Frontend | Validated |
| Documented Functional Observations | No open blocker |

## Final Release Validation

- Date: 2026-08-19/20
- Validated commit: `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`
- Final Docker build: API `0.5.0`
- API and frontend containers healthy.
- `GET /health`: healthy, service `Insurance Policy RAG API`, API `0.5.0`.
- `GET /ready`: ready, OpenAI configured, collection `queplan_policies`, 262 indexed chunks.
- Final E2E replay: policies, web, combined, and draft passed. Conversational
  flows used `POST /ask/stream`; draft generation used `POST /generate-policy`.
- Official offline backup question validated: `¿Qué es el período de carencia y desde cuándo se cuenta?` with policy `POL320190074`.
- Automated suite: 74 passed, 2 dependency/deprecation warnings.
- Retrieval matched the presentation baseline.
- RAGAS remained healthy.
- Latency replay showed expected environment-sensitive variation.
- Blocking defects: none.

Detailed execution evidence is recorded in docs/qa/test_execution_log.md.

## Available

- FastAPI application.
- `GET /health`.
- `GET /config`.
- `POST /ask`.
- `POST /ask/stream` with `status`, `token`, `complete`, and `error` SSE events.
- API schemas and response contracts.
- `RealRAGService`.
- `FakeRAGService` used in tests through FastAPI `dependency_overrides`.
- Qdrant integration.
- Indexing pipeline.
- Retrieval that returns citable source chunks.
- API tests.
- Embedding tests.
- Dataset profiling tests.
- Indexing tests.
- RAG service tests.
- Automated coverage for grounded answers with citations.
- Automated coverage for abstention when no evidence is found.
- Automated coverage for missing-index handling.

## Historical Manual Indexing Validation

- OpenAI configuration was detected by `GET /ready`.
- The Qdrant collection `queplan_policies` was created or updated by `python -m insurance_chatbot.indexing`.
- The local index was reported as available by `GET /ready`.
- `GET /ready` is operational before and after indexing.
- The readiness state changed from `not_ready` before indexing to `ready` after indexing.
- The index reported 487 chunks from 9 documents using `text-embedding-3-small`.

This historical manual validation confirms index creation and readiness only.
It predates the final reusable snapshot, where `/ready` reports 262 indexed
chunks. It does not define the final release corpus size.

## Previous QA - Manually Validated Functional `/ask` Path

- FastAPI to Qdrant to OpenAI to response flow worked for the first Swagger `/ask` case.
- Retrieval returned 5 chunks.
- Real policy sources were returned for `POL320190074.pdf`.
- Real metadata was returned, including `model: "gpt-4.1-mini"`, `embedding_model: "text-embedding-3-small"`, `policy_id: "POL320190074"`, `retrieved_chunks: 5`, and `is_mock: false`.
- The response included citations in the answer text.
- Manual `/ask` validation cases `QA-API-005` through `QA-API-016` were executed from PowerShell against the Docker Compose API at `http://localhost:8000`.
- Missing `question`, empty `question`, too-short `question`, numeric `question`, null `question`, numeric `policy_id`, array body, and string body returned HTTP 422 schema validation responses.
- Whitespace-only `question` returned HTTP 400 service-level validation with `question must not be empty`.
- `policy_id: null` was accepted by the schema and returned a normal answer.
- Unknown extra fields were ignored by the current schema and returned a normal answer.
- Malformed JSON for `/ask` returned HTTP 422 with `json_invalid` before endpoint logic.
- Invalid `Content-Type: text/plain` for `/ask` returned HTTP 422 with `model_attributes_type` before endpoint execution.

## Previous QA - Manually Validated Grounding For First `/ask` Case

- Grounding of the first `/ask` answer against `POL320190074.pdf` was manually validated.
- The main answer claims matched the cited pages.
- No contradictions were detected.
- No evident hallucinations were detected in this case.
- Page 35 was confirmed as additional context rather than direct support for every listed coverage.
- The first complete end-to-end flow is manually validated: FastAPI to Qdrant to OpenAI to cited answer to PDF page review.

## Previous QA - Manually Validated Frontend Smoke Test

- Chainlit frontend is available.
- Frontend to API connection was validated.
- `policies` mode was validated from Chainlit.
- `policy_id` filtering with `POL320190074` was validated from Chainlit.
- A real response with retrieval was returned through the frontend.
- Sources were rendered in the Chainlit interface.
- The first frontend end-to-end smoke test was validated: Chainlit frontend -> FastAPI -> Qdrant -> OpenAI -> Chainlit frontend.
- The response was not mock.
- API-off frontend handling was validated with `FE-ERR-API-OFF-001`.
- When FastAPI was stopped, Chainlit remained responsive and displayed a controlled backend-unavailable message.
- No traceback, internal exception, or infinite loading was observed during API-off validation.
- Policies-mode no-evidence behavior was validated with `FE-POL-NOEVIDENCE-001`; the assistant did not fabricate unsupported spacecraft-collision coverage and cited retrieved policy sections.
- Automatic routing was validated with `FE-AUTO-001`; a general knowledge question in `auto` mode was routed to `web`.
- Out-of-scope behavior was validated with `FE-OOS-001`; a creative poem request in `policies` mode was declined based on unsupported policy evidence and cited retrieved policy sources.
- Frontend timeout handling was validated with `FE-TIMEOUT-001`; Chainlit displayed a controlled timeout message, stayed responsive, and did not expose a traceback or infinite loading state.

## QA Evidence Package

Manual QA execution screenshots are stored in `docs/qa/screenshots/`.

| Screenshot | Description |
|---|---|
| `01-policy-setup.png` | Policies mode selection and policy selection before querying |
| `02-policy-response.png` | Successful policy answer with retrieved sources |
| `03-no-evidence-setup.png` | No-evidence scenario setup |
| `04-no-evidence-response.png` | No-evidence response showing insufficient evidence and retrieved sources |
| `05-auto-route-web.png` | Automatic routing to the web route |
| `06-out-of-scope.png` | Out-of-scope request handled without hallucination |
| `07-api-unreachable.png` | Frontend behavior when the backend is unavailable |
| `08-timeout.png` | Frontend timeout handling |
| `09-health-endpoint.png` | Health endpoint verification |
| `10-config-endpoint.png` | Configuration endpoint verification |
| `11-frontend-home.png` | Final ready state, mode chips and configuration controls |
| `12-policies-final.png` | Final policies answer with PDF sources and latency |
| `13-web-final.png` | Final Chile web answer with clickable sources and latency |
| `14-combined-final.png` | Final combined answer with policy and web evidence |
| `15-draft-final.png` | Review-only draft with sources, disclaimer and latency |
| `16-mobile-final.png` | Mobile-width validation after fixing settings overflow |

## Frontend Web Flow Status

- `FE-WEB-001` is historical and resolved: the original web-route failure was
  corrected, empty model output is handled without HTTP 500, and web retrieval
  is validated in explicit `web` and `combined` flows.

## Streaming Frontend Validation

- Chainlit consumes `POST /ask/stream` and progressively renders the answer.
- The backend emits periodic progress events while retrieval and generation run.
- Route chips update the active session and the settings sidebar consistently.
- A policy identifier written directly in the question is used as a one-request retrieval filter.
- The browser E2E check for `POL320190074` returned five sources and every source belonged to that policy.
- `/ready` returns the RAG state without being sent through the LLM router.

## Previous QA - Manually Validated Combined Flow

- `combined` mode was validated from Chainlit.
- The response displayed route `combined`.
- The response included separate `Evidencia de pólizas` and `Información web actual` blocks.
- PDF sources were displayed.
- Web sources with URLs were displayed.
- Sources from `POL320190074.pdf` were retrieved.
- Web sources included domains such as `supercias.gob.ec` and `undp.org`.
- No HTTP 500 occurred in `FE-COMB-001`.

## Previous QA - Manually Validated Draft Generation

- Draft generation: Validated.
- `/draft` command validation works.
- Successful draft generation works.
- Citation of policy sources works.
- Responsible handling of missing information was observed.
- The system did not invent missing limits, deductibles, or catastrophic coverage details; it left them for manual definition.

## Direct API Validation

- `/generate-policy` was tested directly from Swagger.
- Successful responses were verified.
- Input validations were verified.
- Validation errors were returned with HTTP 422.
- No HTTP 500 errors were observed during these `/generate-policy` tests.
- `API-DRAFT-001` verified successful draft generation with sources, metadata, disclaimer, `model: "gpt-4.1-mini"`, `retrieved_chunks: 3`, and `is_mock: false`.
- `API-DRAFT-002` verified `instructions` minimum length validation.
- `API-DRAFT-003` verified malformed JSON rejection before endpoint logic.
- `API-DRAFT-004` verified `source_policy_ids` minimum item validation.

## Current Service Behavior

The normal application path uses real services. The `policies` route uses `RealRAGService` for policy retrieval and answer generation.

`FakeRAGService` is used by tests through dependency overrides. It should not be treated as the normal runtime service, and this task does not suggest changing the application to use the fake service.

## QA Scope Completion

- All planned manual QA scenarios for the documented project scope were completed.
- The QA evidence package is finalized in `docs/qa/screenshots/`.
- The demo runbook is finalized in `docs/qa/demo_runbook.md`.
- Recommended demo questions are documented. The final replay records the
  official offline backup question: `¿Qué es el período de carencia y desde
  cuándo se cuenta?`, in `policies` mode with `POL320190074`.
- `FE-WEB-001` remains resolved as historical QA evidence; the final replay
  validated the current web demo flow with current web sources and URLs.
