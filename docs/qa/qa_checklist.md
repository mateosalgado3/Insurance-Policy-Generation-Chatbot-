# QA Checklist

This checklist reflects the current QA, integration, and demo-preparation status documented in `docs/qa/api_manual_test_cases.md`, `docs/qa/test_execution_log.md`, `docs/qa/integration_status.md`, `docs/qa/known_issues.md`, `README.md`, `docs/demo.md`, and `compose.yaml`.

Legend:

- `[x] Completed`: supported by executed evidence.
- `[~] Partial`: partially validated or documented, but not fully closed.
- Optional future improvements are listed separately and are not required for the completed QA scope.

## Environment Preparation

- [x] Completed - Editable development installation was executed with `pip install -e ".[dev]"`.
- [x] Completed - Automated suite execution was recorded after installation.
- [x] Completed - Latest QA context records the automated suite as passing with 54 passed and 2 warnings.
- [x] Completed - Docker Compose startup commands are documented in `README.md` and `docs/demo.md`.
- [x] Completed - The QA demo runbook is finalized for the documented project scope.

## Git And Sensitive Files

- [x] Completed - Working tree was clean after the recorded test executions.
- [x] Completed - `.env` is ignored by Git according to documented inspection.
- [x] Completed - `.venv` is ignored by Git according to documented inspection.
- [x] Completed - Raw PDFs under local data folders are ignored by Git according to documented inspection.
- [x] Completed - Generated `outputs` are ignored by Git according to documented inspection.
- [x] Completed - Local runtime lock files under the Qdrant index are ignored by Git according to documented inspection.
- [x] Completed - `.dockerignore` excludes `.env`, `.venv`, raw data, outputs, caches, tests, docs, and frontend from the API image context.
- [x] Completed - The repository intentionally versions `data/index/chunks.jsonl` and the local Qdrant snapshot as the reproducible demo artifact; runtime lock files remain ignored.

## API

- [x] Completed - FastAPI is available.
- [x] Completed - `GET /health` was manually validated.
- [x] Completed - `GET /ready` was manually validated before and after local indexing.
- [x] Completed - `GET /config` was revalidated directly against the final Docker API and returned the active models, Qdrant configuration and `top_k: 5`.
- [x] Completed - `POST /ask` was manually validated from Swagger for a real policies query.
- [x] Completed - `POST /generate-policy` was manually validated from Swagger.
- [x] Completed - Swagger is documented at `http://127.0.0.1:8000/docs`.
- [x] Completed - Manual `/ask` validation cases `QA-API-005` through `QA-API-016` were executed from PowerShell.

## Validations

- [x] Completed - `/generate-policy` successful draft generation was validated.
- [x] Completed - `/generate-policy` minimum `instructions` length validation was validated with HTTP 422.
- [x] Completed - `/generate-policy` malformed JSON handling was validated with HTTP 422.
- [x] Completed - `/generate-policy` minimum `source_policy_ids` item validation was validated with HTTP 422.
- [x] Completed - Invalid `/draft` command usage was validated from Chainlit.
- [x] Completed - Valid `/ask` with `policy_id` was validated.
- [x] Completed - Missing required `question` field validation for `/ask` was executed.
- [x] Completed - Empty and too-short `question` validations for `/ask` were executed.
- [x] Completed - Whitespace-only `question` validation for `/ask` was executed and returned HTTP 400 service-level validation.
- [x] Completed - Wrong-type payload validations for `/ask` were executed.
- [x] Completed - `policy_id: null` runtime behavior for `/ask` was confirmed as accepted by the schema.
- [x] Completed - Extra-field behavior for `/ask` was confirmed as accepted by the current schema.
- [x] Completed - Malformed JSON validation for `/ask` was executed and returned HTTP 422 before endpoint logic.
- [x] Completed - Invalid `Content-Type` validation for `/ask` was executed and returned HTTP 422 before endpoint execution.

## Error Handling

- [x] Completed - `/generate-policy` 422 responses were validated directly from Swagger.
- [x] Completed - `FE-WEB-001` was regression-tested after the fix and now returns HTTP 200; empty web output also degrades safely instead of returning HTTP 500.
- [x] Completed - `FE-ERR-API-OFF-001` confirmed the frontend handles an unavailable backend API with a controlled message and no infinite loading.
- [x] Completed - `FE-TIMEOUT-001` confirmed the frontend handles backend timeout with a controlled message and no infinite loading.
- [x] Completed - The historical web-mode HTTP 500 root cause was fixed and the original query was regression-tested with HTTP 200.
- [x] Completed - Timeout and upstream error mappings are covered by automated API tests; the user-facing timeout path was also validated from the frontend.

## Frontend

- [x] Completed - Chainlit frontend is available.
- [x] Completed - Chainlit startup is documented in `README.md`.
- [x] Completed - Docker Compose exposes Chainlit at `http://127.0.0.1:8001`.
- [x] Completed - `/config` command was executed from Chainlit.
- [x] Completed - `/mode policies` was accepted by Chainlit.
- [x] Completed - `/policy POL320190074` was accepted by Chainlit.
- [x] Completed - `/mode web` was executed from Chainlit.
- [x] Completed - `/mode combined` was executed from Chainlit.
- [x] Completed - `/draft` command validation was executed from Chainlit.
- [x] Completed - Successful `/draft` generation was executed from Chainlit.
- [x] Completed - Frontend rendered sources in the UI.
- [x] Completed - Frontend did not show infinite loading in the validated smoke test.
- [x] Completed - Final screenshots for the QA evidence package were created under `docs/qa/screenshots/`.

## Frontend To API Integration

- [x] Completed - First frontend end-to-end smoke test passed: Chainlit frontend -> FastAPI -> Qdrant -> OpenAI -> Chainlit frontend.
- [x] Completed - Frontend sent a policies question to `POST /ask`.
- [x] Completed - Frontend rendered the answer field.
- [x] Completed - Frontend rendered policy sources.
- [x] Completed - Frontend rendered route `policies`.
- [x] Completed - Frontend rendered route `web` for a general web query.
- [x] Completed - Frontend rendered route `combined`.
- [x] Completed - Frontend displayed PDF sources and web URL sources in combined mode.
- [x] Completed - Frontend behavior when the API is unavailable was validated in Docker Compose.
- [x] Completed - Frontend timeout behavior was validated.
- [x] Completed - Web mode is validated: the historical `FE-WEB-001` failure is resolved, the original query returns HTTP 200, and the final Chile query returned 12 web sources.

## Sources

- [x] Completed - Source strings returned by `/ask` were verified for the first Swagger policies case.
- [x] Completed - Cited PDF pages were manually checked for the first Swagger policies case.
- [x] Completed - Sources were visible in the Chainlit UI for `FE-POL-001`.
- [x] Completed - PDF sources were visible in the Chainlit UI for `FE-COMB-001`.
- [x] Completed - Web sources with URLs were visible in the Chainlit UI for `FE-COMB-001`.
- [x] Completed - The public API keeps `sources` compatible while the frontend normalizes richer source metadata for PDF labels and clickable web URLs.
- [x] Completed - Final screenshots showing sources in the UI were created under `docs/qa/screenshots/`.

## Qdrant And Indexing

- [x] Completed - Qdrant integration is present.
- [x] Completed - Indexing pipeline is present.
- [x] Completed - Local indexing command was executed previously with `python -m insurance_chatbot.indexing`.
- [x] Completed - `GET /ready` confirmed the index state before and after indexing.
- [x] Completed - The current repository documents a reusable local Qdrant snapshot.
- [x] Completed - Docker Compose configures the API with `QDRANT_PATH: /app/data/index/qdrant`.
- [x] Completed - Qdrant intentionally runs as an embedded local persistent store mounted at `/app/data/index/qdrant`; a separate service container is not required by this architecture.

## Real Retrieval

- [x] Completed - Real retrieval queried local Qdrant for the validated policies case.
- [x] Completed - Real retrieval used `text-embedding-3-small`.
- [x] Completed - `/ask` completed against real indexed policy data.
- [x] Completed - Retrieval returned citable source payloads used in the API response.
- [x] Completed - The validated policies response used `gpt-4.1-mini` and was not mock.
- [x] Completed - Manual grounding against cited PDF pages was completed for the first policies case.
- [x] Completed - Web retrieval is validated in explicit web and combined modes; the former query-specific HTTP 500 is resolved.
- [x] Completed - Policies-mode query with no supporting evidence was executed and did not fabricate unsupported coverage.

## Modes

- [x] Completed - `policies` mode validated from Chainlit.
- [x] Completed - `combined` mode validated from Chainlit.
- [x] Completed - `web` mode validated from Chainlit with current Chile insurance-regulation sources.
- [x] Completed - `auto` mode manual validation was executed for a general knowledge question and routed to `web`.
- [x] Completed - Out-of-scope manual validation was executed in policies mode.

## Draft Generation

- [x] Completed - `/draft` command syntax validation works.
- [x] Completed - Successful draft generation works from Chainlit.
- [x] Completed - `POST /generate-policy` works from Swagger.
- [x] Completed - Draft generation returns sources, metadata, and disclaimer.
- [x] Completed - Responsible handling of missing limits, deductibles, and catastrophic coverage details was observed.
- [x] Accepted - Draft generation is functionally complete; terse internal citation suffixes remain a documented, non-blocking UX limitation.

## Demo Preparation

- [x] Completed - `docs/demo.md` documents Docker Compose startup, validation, demo cases, evidence to capture, logs, and shutdown.
- [x] Completed - `README.md` documents Docker Compose startup, local API startup, local Chainlit startup, endpoints, Chainlit commands, and indexing commands.
- [x] Completed - A validated policies question is documented as a demo candidate.
- [x] Completed - The final combined demo question and its evidence are recorded in `14-combined-final.png`.
- [x] Completed - The final web demo question for Chile and its evidence are recorded in `13-web-final.png`.
- [x] Completed - Recommended demo question list is documented in `docs/qa/demo_runbook.md`.
- [x] Completed - Final demo evidence screenshots were created under `docs/qa/screenshots/`.

## QA Scope Completion

- [x] Completed - All planned manual QA scenarios for the documented project scope were executed or documented as historical observations.
- [x] Completed - QA evidence package is finalized in `docs/qa/screenshots/`.
- [x] Completed - Demo runbook is finalized in `docs/qa/demo_runbook.md`.

## Optional Future Improvements

- Second-person runbook validation as a handoff improvement, if requested later.
