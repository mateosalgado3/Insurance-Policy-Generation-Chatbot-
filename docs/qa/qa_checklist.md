# QA Checklist

This checklist reflects the current QA, integration, and demo-preparation status documented in `docs/qa/api_manual_test_cases.md`, `docs/qa/test_execution_log.md`, `docs/qa/integration_status.md`, `docs/qa/known_issues.md`, `README.md`, `docs/demo.md`, and `compose.yaml`.

Legend:

- `[x] Completed`: supported by executed evidence.
- `[~] Partial`: partially validated or documented, but not fully closed.
- Optional future improvements are listed separately and are not required for the completed QA scope.

## Chronology Summary

- **Previous QA:** earlier API, frontend, negative-path, resilience, grounding,
  and demo-preparation checks. These remain valid evidence but were not all
  rerun during the final release session.
- **Final Release QA - 2026-08-19/20:** commit
  `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`, clean Docker build API `0.5.0`,
  262 indexed chunks, final Docker E2E replay, 74-test automated suite, final
  evaluation replay, and no blocking defects.
- **Historical/Superseded Evidence:** older Docker image `0.3.0`, older
  487-chunk local index, older demo candidates, and previous release-candidate
  checks are retained only for traceability.
- **Presentation Baselines:** RAGAS and latency slide metrics remain separate
  from variable final replay metrics; retrieval matched its baseline exactly.
- **Post-integration automation - 2026-08-20:** Daisy's QA commit and the
  consolidated report runner were combined and validated with 77 tests plus a
  two-case paid smoke. This is an integration check, not a replacement for the
  12-case final replay.

## Environment Preparation

- [x] Completed - Editable development installation was executed with `pip install -e ".[dev]"`.
- [x] Completed - Automated suite execution was recorded after installation.
- [x] Final Release QA - Latest automated suite execution is recorded as `74 passed, 2 warnings in 37.38s` for commit `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`.
- [x] Final Release QA - The two automated-suite warnings are classified as dependency/deprecation warnings, not functional failures.
- [x] Completed - Docker Compose startup commands are documented in `README.md` and `docs/demo.md`.
- [x] Completed - The QA demo runbook is finalized for the documented project scope.
- [x] Final Release QA - Final Docker E2E replay was recorded against exact commit `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`.
- [x] Post-integration - `scripts/run_all_checks.py --limit 2` passed Ruff, 77 Pytest tests, local/OpenAI retrieval, RAGAS, and latency; it replaced `docs/evaluation-results.md` with the current evidence.

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
- [x] Previous QA - `GET /health` was manually validated.
- [x] Previous QA - `GET /ready` was manually validated before and after local indexing.
- [x] Final Release QA - Final clean Docker rebuild replay confirmed `GET /health` HTTP 200 with `status: healthy`, service `Insurance Policy RAG API`, and version `0.5.0`.
- [x] Historical/Superseded - Earlier QA evidence that recorded API version `0.3.0` is clarified as coming from a previous Docker image, not the final clean rebuild.
- [x] Final Release QA - Final Docker replay confirmed `GET /ready` HTTP 200 with OpenAI configured, index ready, collection `queplan_policies`, and 262 indexed chunks.
- [x] Previous QA - `GET /config` was validated and returned the active models, Qdrant configuration and `top_k: 5`.
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
- [x] Final Release QA - Latest final Chainlit replay passed for `policies`, `web`, `combined`, and `/draft` from Docker build `0.5.0`.
- [x] Final Release QA - Conversational final replay used `POST /ask/stream`; draft generation used `POST /generate-policy`.
- [x] Previous QA - Frontend sent a policies question to `POST /ask`.
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
- [x] Historical/Superseded - The previous local indexing run reported 487 chunks; the final release snapshot reports 262 indexed chunks.
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

## Evaluation Replay

- [x] Final Release QA - Final retrieval replay on commit `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d` matched the documented presentation baseline: 52 total questions, 43 labeled, Hit@5 `1.0000`, Recall@5 `0.9341`, MRR `0.8078`.
- [x] Final Release QA - Final RAGAS replay on the same commit used 12 cases and remained healthy: Answer `0.7078`, Context `0.9792`, Overall `0.8435`.
- [x] Presentation Baseline - Stored RAGAS presentation baseline remains distinguished from the final replay: Answer `0.7053`, Context `0.9792`, Overall `0.8422`.
- [x] Final Release QA - Final latency replay on the same commit used 12 cases: mean time to model `326.93 ms`, mean model response `4889.07 ms`, mean backend total `5216.01 ms`.
- [x] Final Release QA - Final latency replay p95 for backend total is recorded as `8392.25 ms`.
- [x] Presentation Baseline - Stored latency presentation baseline remains distinguished from the final replay: `475.06 ms` / `4411.09 ms` / `4886.15 ms`.
- [x] Final Release QA - Latency variation is recorded as observational and environment-sensitive, not a functional failure.

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
- [x] Completed - The final official offline backup question is documented as `¿Qué es el período de carencia y desde cuándo se cuenta?` with policy `POL320190074` in `policies` mode.
- [x] Completed - The final combined demo question and its evidence are recorded in `14-combined-final.png`.
- [x] Completed - The final web demo question for Chile and its evidence are recorded in `13-web-final.png`.
- [x] Completed - The offline backup question was validated again after the clean Docker rebuild with correct `POL320190074` policy sources.
- [x] Completed - Recommended demo question list is documented in `docs/qa/demo_runbook.md`.
- [x] Completed - Final demo evidence screenshots were created under `docs/qa/screenshots/`.

## QA Scope Completion

- [x] Completed - All planned manual QA scenarios for the documented project scope were executed or documented as historical observations.
- [x] Completed - QA evidence package is finalized in `docs/qa/screenshots/`.
- [x] Completed - Demo runbook is finalized in `docs/qa/demo_runbook.md`.

## Optional Future Improvements

- Second-person runbook validation as a handoff improvement, if requested later.
