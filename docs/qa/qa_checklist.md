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
- [~] Partial - The repository intentionally versions `data/index/chunks.jsonl` and the local Qdrant snapshot for demo reuse.

## API

- [x] Completed - FastAPI is available.
- [x] Completed - `GET /health` was manually validated.
- [x] Completed - `GET /ready` was manually validated before and after local indexing.
- [~] Partial - `GET /config` is documented and was observed from Chainlit, but the Swagger manual case remains not executed.
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
- [x] Completed - `FE-WEB-001` confirmed the frontend handles a backend HTTP 500 with a controlled message and without exposing internal details.
- [x] Completed - `FE-ERR-API-OFF-001` confirmed the frontend handles an unavailable backend API with a controlled message and no infinite loading.
- [x] Completed - `FE-TIMEOUT-001` confirmed the frontend handles backend timeout with a controlled message and no infinite loading.
- [~] Partial - Web-mode HTTP 500 is documented as query-specific or result-specific, with root cause still under investigation.
- [~] Partial - API-layer timeout mapping is documented in the endpoint, but the completed timeout validation was performed from the frontend.

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
- [~] Partial - Web mode is partially validated because `FE-WEB-001` failed with HTTP 500 while `FE-WEB-002` passed.

## Sources

- [x] Completed - Source strings returned by `/ask` were verified for the first Swagger policies case.
- [x] Completed - Cited PDF pages were manually checked for the first Swagger policies case.
- [x] Completed - Sources were visible in the Chainlit UI for `FE-POL-001`.
- [x] Completed - PDF sources were visible in the Chainlit UI for `FE-COMB-001`.
- [x] Completed - Web sources with URLs were visible in the Chainlit UI for `FE-COMB-001`.
- [~] Partial - Source format consistency still needs team confirmation because QA docs record `list[str]` while architecture references richer source attributes.
- [x] Completed - Final screenshots showing sources in the UI were created under `docs/qa/screenshots/`.

## Qdrant And Indexing

- [x] Completed - Qdrant integration is present.
- [x] Completed - Indexing pipeline is present.
- [x] Completed - Local indexing command was executed previously with `python -m insurance_chatbot.indexing`.
- [x] Completed - `GET /ready` confirmed the index state before and after indexing.
- [x] Completed - The current repository documents a reusable local Qdrant snapshot.
- [x] Completed - Docker Compose configures the API with `QDRANT_PATH: /app/data/index/qdrant`.
- [~] Partial - Qdrant is used as local persistent storage or snapshot inside the current stack; there is no separate Qdrant container in `compose.yaml`.

## Real Retrieval

- [x] Completed - Real retrieval queried local Qdrant for the validated policies case.
- [x] Completed - Real retrieval used `text-embedding-3-small`.
- [x] Completed - `/ask` completed against real indexed policy data.
- [x] Completed - Retrieval returned citable source payloads used in the API response.
- [x] Completed - The validated policies response used `gpt-4.1-mini` and was not mock.
- [x] Completed - Manual grounding against cited PDF pages was completed for the first policies case.
- [~] Partial - Web retrieval is partially validated because one specific web query still returns HTTP 500.
- [x] Completed - Policies-mode query with no supporting evidence was executed and did not fabricate unsupported coverage.

## Modes

- [x] Completed - `policies` mode validated from Chainlit.
- [x] Completed - `combined` mode validated from Chainlit.
- [~] Partial - `web` mode partially validated from Chainlit.
- [x] Completed - `auto` mode manual validation was executed for a general knowledge question and routed to `web`.
- [x] Completed - Out-of-scope manual validation was executed in policies mode.

## Draft Generation

- [x] Completed - `/draft` command syntax validation works.
- [x] Completed - Successful draft generation works from Chainlit.
- [x] Completed - `POST /generate-policy` works from Swagger.
- [x] Completed - Draft generation returns sources, metadata, and disclaimer.
- [x] Completed - Responsible handling of missing limits, deductibles, and catastrophic coverage details was observed.
- [~] Partial - Some internal citation labels may be unclear for end users and remain a UX improvement.

## Demo Preparation

- [x] Completed - `docs/demo.md` documents Docker Compose startup, validation, demo cases, evidence to capture, logs, and shutdown.
- [x] Completed - `README.md` documents Docker Compose startup, local API startup, local Chainlit startup, endpoints, Chainlit commands, and indexing commands.
- [x] Completed - A validated policies question is documented as a demo candidate.
- [~] Partial - `FE-COMB-001` is a validated combined candidate, but the final demo question set is not selected.
- [~] Partial - General web mode works, and the recommended demo flow excludes the specific historical `FE-WEB-001` query.
- [x] Completed - Recommended demo question list is documented in `docs/qa/demo_runbook.md`.
- [x] Completed - Final demo evidence screenshots were created under `docs/qa/screenshots/`.

## QA Scope Completion

- [x] Completed - All planned manual QA scenarios for the documented project scope were executed or documented as historical observations.
- [x] Completed - QA evidence package is finalized in `docs/qa/screenshots/`.
- [x] Completed - Demo runbook is finalized in `docs/qa/demo_runbook.md`.

## Optional Future Improvements

- Second-person runbook validation as a handoff improvement, if requested later.
