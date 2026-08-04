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

## Manually Validated After Local Indexing

- OpenAI configuration was detected by `GET /ready`.
- The Qdrant collection `queplan_policies` was created or updated by `python -m insurance_chatbot.indexing`.
- The local index was reported as available by `GET /ready`.
- `GET /ready` is operational before and after indexing.
- The readiness state changed from `not_ready` before indexing to `ready` after indexing.
- The index reported 487 chunks from 9 documents using `text-embedding-3-small`.

This manual validation confirms index creation and readiness only. It does not yet validate retrieval quality, answer quality, or citation correctness.

## Manually Validated Functional `/ask` Path

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

## Manually Validated Grounding For First `/ask` Case

- Grounding of the first `/ask` answer against `POL320190074.pdf` was manually validated.
- The main answer claims matched the cited pages.
- No contradictions were detected.
- No evident hallucinations were detected in this case.
- Page 35 was confirmed as additional context rather than direct support for every listed coverage.
- The first complete end-to-end flow is manually validated: FastAPI to Qdrant to OpenAI to cited answer to PDF page review.

## Manually Validated Frontend Smoke Test

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

## Frontend Web Flow Status

- `FE-WEB-001` was reproduced and its root cause was corrected.
- The exact original query now returns HTTP 200 with web sources.
- Empty model output is handled as a degraded response instead of HTTP 500.
- `FE-WEB-002` confirmed that a general web query can execute successfully.
- `FE-COMB-001` confirmed that web retrieval can also execute successfully inside the `combined` flow.
- Integration of the web route is validated.

## Streaming Frontend Validation

- Chainlit consumes `POST /ask/stream` and progressively renders the answer.
- The backend emits periodic progress events while retrieval and generation run.
- Route chips update the active session and the settings sidebar consistently.
- A policy identifier written directly in the question is used as a one-request retrieval filter.
- The browser E2E check for `POL320190074` returned five sources and every source belonged to that policy.
- `/ready` returns the RAG state without being sent through the LLM router.

## Manually Validated Combined Flow

- `combined` mode was validated from Chainlit.
- The response displayed route `combined`.
- The response included separate `Evidencia de pólizas` and `Información web actual` blocks.
- PDF sources were displayed.
- Web sources with URLs were displayed.
- Sources from `POL320190074.pdf` were retrieved.
- Web sources included domains such as `supercias.gob.ec` and `undp.org`.
- No HTTP 500 occurred in `FE-COMB-001`.

## Manually Validated Draft Generation

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
- Recommended demo questions are documented and avoid the known `FE-WEB-001` query.

## Optional Future Improvements

- Source-format alignment between API `list[str]` responses and richer source descriptions in architecture documentation.
- Second-person runbook validation as a handoff improvement, if requested later.
