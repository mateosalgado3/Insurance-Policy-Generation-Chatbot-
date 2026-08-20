# Test Execution Log

## Recorded Execution

- Date: 2026-07-29
- Operating system: Windows
- Python: 3.12.1
- Pytest: 9.1.1
- Command: `pytest -v -p no:cacheprovider`
- Final result: 24 tests collected, 24 passed, 0 failed, 1 warning
- Duration: 4.72 seconds
- Git status after tests: `git status --short` showed no changes

## Post-Merge Execution From `origin/main`

- Date: 2026-07-29
- Branch: `feature/qa-integration-demo`
- Environment: Windows, Python 3.12.1, pytest 9.1.1
- Installation command: `pip install -e ".[dev]"`
- Installation result: completed successfully
- Test command: `pytest -v -p no:cacheprovider`
- Final result: 25 tests collected, 25 passed, 0 failed, 1 warning
- Duration: 17.32 seconds
- Git status after tests: `git status --short` showed no changes

This execution includes automated coverage for:

- API.
- Embeddings.
- Indexing.
- Dataset profiling.
- RAG retrieval.
- Grounded answers with citations.
- Abstention when no evidence is found.
- Missing-index handling.

## Historical Manual Indexing And Readiness Validation

- Date: 2026-07-29
- Branch: `feature/qa-integration-demo`
- FastAPI state before indexing: stopped before running the indexing command
- Indexing command: `python -m insurance_chatbot.indexing`
- Indexing result: `Indexed 487 chunks from 9 documents into 'queplan_policies' using text-embedding-3-small.`
- Indexing status: Passed
- FastAPI state after indexing: started again before rechecking readiness
- Errors observed during indexing: none

The indexing result confirms only that:

- 9 documents were processed.
- 487 chunks were generated.
- The `queplan_policies` collection was created or updated.
- The `text-embedding-3-small` model was used.
- The command completed without errors.

This historical indexing run predates the final reusable Docker snapshot, where
`/ready` reports 262 indexed chunks. It does not define the final release corpus
size and does not validate retrieval quality or answer quality manually.

### Readiness Before Indexing

- Endpoint: `GET /ready`
- Result:

```json
{
  "status": "not_ready",
  "openai_configured": true,
  "index_ready": false,
  "collection": "queplan_policies",
  "indexed_chunks": 0,
  "detail": "Qdrant collection 'queplan_policies' does not exist; run the indexing command first"
}
```

- Status: Passed

Confirmed behavior:

- The endpoint detected that OpenAI was configured.
- The endpoint detected that the collection did not exist yet.
- The endpoint returned `not_ready`.
- The endpoint provided a clear diagnostic message.

### Readiness After Indexing

- Endpoint: `GET /ready`
- Result:

```json
{
  "status": "ready",
  "openai_configured": true,
  "index_ready": true,
  "collection": "queplan_policies",
  "indexed_chunks": 487,
  "detail": null
}
```

- Status: Passed

Confirmed behavior:

- OpenAI appears configured.
- The index appears available.
- The correct collection was detected.
- 487 chunks were reported.
- The system changed correctly from `not_ready` to `ready`.

## Manual Functional `/ask` Validation From Swagger

- Date: 2026-07-29
- Endpoint: `POST /ask`
- Execution client: Swagger UI
- Request:

```json
{
  "question": "¿Qué coberturas hospitalarias contempla la póliza?",
  "policy_id": "POL320190074"
}
```

- HTTP status: 200 OK
- Execution mode: real execution, not mock
- Model: `gpt-4.1-mini`
- Embedding model: `text-embedding-3-small`
- Policy ID: `POL320190074`
- Retrieved chunks: 5
- Response time: 9185.69 ms
- Status: Passed

Sources returned:

- `POL320190074.pdf - Página 20 - ARTÍCULO Nº 2`
- `POL320190074.pdf - Página 19 - ARTÍCULO Nº 2`
- `POL320190074.pdf - Página 1 - ARTÍCULO 2º`
- `POL320190074.pdf - Página 35 - ARTÍCULO N° 3`
- `POL320190074.pdf - Página 18 - ARTÍCULO Nº 2`

Retrieval scores:

- 0.7047
- 0.6797
- 0.6747
- 0.6671
- 0.6669

Observed answer summary:

- The answer described hospital coverage such as bed days, hospital services, surgical medical fees, and dental surgery due to accident.
- The answer included textual references `[Fuente 1]`, `[Fuente 2]`, and `[Fuente 3]`.

Justification:

- The API responded correctly.
- The contract included `answer`, `sources`, and `metadata`.
- Real retrieval and real generation worked.

Manual PDF review:

- Page 20 directly supports `Días Cama Hospitalización`.
- Page 20 supports `Servicios Hospitalarios`.
- Page 20 supports `Honorarios Médicos Quirúrgicos`.
- Page 20 supports `Cirugía Dental por Accidente`.
- Page 19 supports that benefits must be expressly indicated in the Particular Conditions.
- Page 19 supports that percentages, reimbursement or payment limits, and applicable conditions are established there.
- Page 19 supports the general description of the Hospitalization Benefit.
- Page 1 contains Article 2 for coverages.
- Page 1 supports the start of the Hospitalization Benefit.
- Page 1 supports bed days and hospital services.
- Page 18 introduces the list of grantable coverages.
- Page 18 includes the Hospitalization Benefit as coverage.
- Page 35 provides context through related definitions, such as hospital and hospitalization.
- Page 35 does not directly support all listed coverages.
- Page 35 does not contradict the answer.

Formal conclusion:

- The main claims in the answer are supported by the cited pages.
- No contradictions were detected.
- No evident hallucinations were detected in this case.
- Page 35 was retrieved as additional context.
- The case moved from partial validation to complete validation.
- The case is closed as Passed.
- This question can remain a demo candidate.

## Resolved Historical PowerShell `/ask` Attempt

- Date: 2026-07-29
- Endpoint: `POST /ask`
- Execution client: PowerShell `Invoke-RestMethod`
- Command attempted:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/ask" `
  -ContentType "application/json" `
  -Body $body
```

- Result:

```text
Invoke-RestMethod : {"detail":"There was an error parsing the body"}
```

- Status: Resolved on 2026-08-18

Notes:

- The historical body was malformed before it reached endpoint logic.
- Rebuilding `$body` with `ConvertTo-Json` returned HTTP 200 with `answer`,
  `sources`, and `metadata`, confirming this was not an `/ask` product bug.

Successful retest procedure:

```powershell
$body = @{
  question = "¿Qué coberturas hospitalarias contempla la póliza?"
  policy_id = "POL320190074"
} | ConvertTo-Json

$body

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/ask" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

## Frontend End-To-End Smoke Test

- Date: 2026-07-31
- Case ID: `FE-POL-001`
- Flow: Chainlit frontend -> FastAPI -> Qdrant -> OpenAI -> Chainlit frontend
- Status: Passed
- Later automated suite context: the final release suite passed with 74 tests
  and 2 non-blocking third-party warnings.

Configuration validated from Chainlit with `/config`:

```text
LLM model: gpt-4.1-mini
Router model: gpt-4.1-mini
Web model: gpt-5.6-luna
Embedding model: text-embedding-3-small
Vector store: Qdrant (local persistent)
Collection: queplan_policies
Top k: 5
Score threshold: None
Available modes: auto, policies, web, combined
OpenAI configured: True
```

Commands executed in Chainlit:

```text
/mode policies
/policy POL320190074
```

Question:

```text
What hospitalization expenses are covered by this policy?
```

Functional result:

- The frontend connected correctly to the API.
- `/mode policies` was accepted.
- `/policy POL320190074` was accepted.
- The query reached the backend.
- The response was displayed completely in Chainlit.
- The displayed route was `policies`.
- Sources were rendered in the interface.
- No errors occurred.
- No infinite loading occurred.
- The response was not mock.

Sources displayed by Chainlit:

- `Fuente 1: POL320190074.pdf - Página 16 - ARTÍCULO Nº 2`
- `Fuente 2: POL320190074.pdf - Página 20 - ARTÍCULO Nº 2`
- `Fuente 3: POL320190074.pdf - Página 1 - ARTÍCULO 2º`
- `Fuente 4: POL320190074.pdf - Página 3 - ARTÍCULO 3º`
- `Fuente 5: POL320190074.pdf - Página 4 - ARTÍCULO 4º`

Manual grounding review:

- Page 16 supports the start of coverage.
- Page 16 supports that coverage must be contracted and indicated in the Particular Conditions.
- Page 20 directly supports `Días Cama Hospitalización`.
- Page 20 supports `Servicios Hospitalarios`.
- Page 20 supports `Honorarios Médicos Quirúrgicos`.
- Page 20 supports `Cirugía Dental por Accidente`.
- Page 1 contains Article 2 for coverages.
- Page 1 supports the Hospitalization Benefit.
- Page 1 supports `Días Cama`.
- Page 1 supports `Servicios Hospitalarios`.
- Page 3 provides definitions of accident.
- Page 3 provides definitions of illness.
- Page 3 provides definitions of disability.
- Page 3 provides definitions of reasonable medical expenses.
- Page 3 provides definitions of expenses actually incurred.
- Page 4 corresponds to Article 4 exclusions.
- Page 4 provides additional context.
- Page 4 does not directly support the main coverage list.
- Page 4 does not contradict the response.

Grounding conclusion:

- The main claims are supported by the cited pages.
- No contradictions were detected.
- No evident hallucinations were detected.
- Page 4 was retrieved as additional context.
- Sources were visible and traceable from the frontend.
- The first frontend end-to-end flow was validated.

Language observation:

- The question was submitted in English, while the assistant answered in Spanish, matching the source policy language.
- The expected UX language behavior should be confirmed with the team.

## Frontend Web Mode Execution

- Date: 2026-07-31
- Case ID: `FE-WEB-001`
- Flow: Chainlit -> `/mode web` -> `POST /ask` -> OpenAI web route
- Question: `What are the most relevant recent developments in Ecuador's insurance sector?`
- Status: Failed
- Frontend handling: Passed
- Backend response: HTTP 500
- Root cause: Under investigation

Observed Chainlit message:

```text
The backend returned an error:
Error interno al procesar la solicitud en el motor RAG.
```

Observed logs:

```text
Frontend: POST http://localhost:8000/ask -> HTTP/1.1 500 Internal Server Error
Backend: POST /ask HTTP/1.1 500 Internal Server Error
```

No traceback was available.

Inspection notes:

- Code inspection was performed without modifying files.
- `mode="policies"` works correctly.
- `mode="web"` uses `OpenAIWebSearchService`.
- The backend catches a generic exception and returns HTTP 500.
- The frontend handled the error with a controlled message and did not expose internal details.
- `/ready` returns 200.
- `/config` returns valid configuration.
- The `policies` route works.
- The failure occurs only in the `web` route.
- Root cause was not determined within the completed QA scope.

Investigation notes:

- Possible causes to confirm later include availability or permissions of the configured web model.
- Possible causes to confirm later include compatibility between Responses API and web search.
- Possible causes to confirm later include parameters used by the web call.
- Possible causes to confirm later include permissions associated with the OpenAI account.
- These are investigation hypotheses only and are not confirmed causes.

## Frontend Combined Mode Execution

- Date: 2026-07-31
- Case ID: `FE-COMB-001`
- Flow: Chainlit -> `/mode combined` -> `POST /ask` -> policies route plus web route
- Question: `Compare the catastrophic coverage described in the policy with recent developments in Ecuador's insurance sector.`
- Status: Passed
- Route: `combined`

Observed result:

- The query responded correctly.
- The response showed route `combined`.
- The response included two blocks: `Evidencia de pólizas` and `Información web actual`.
- PDF sources were displayed.
- Web sources with URLs were displayed.
- Sources from `POL320190074.pdf` were retrieved.
- Web sources included domains such as `supercias.gob.ec` and `undp.org`.
- No HTTP 500 occurred.

UX observation:

- The combined response contained mixed languages: the policy section was mostly in Spanish, while part of the web section was in English.
- This is recorded as a language consistency observation, not as a blocking bug.

## Frontend General Web Query Execution

- Date: 2026-07-31
- Case ID: `FE-WEB-002`
- Flow: Chainlit -> `/mode web` -> `POST /ask` -> OpenAI web route
- Question: `What is artificial intelligence?`
- Status: Passed
- Route: `web`

Observed result:

- The query responded correctly.
- The response was shown in Chainlit.
- No HTTP 500 occurred.
- The response was coherent and did not show internal errors.
- General web queries can execute successfully.

Scope update for `FE-WEB-001`:

- `FE-WEB-001` failed with HTTP 500.
- `FE-COMB-001` passed and showed both PDF and web sources.
- `FE-WEB-002` passed with a general web query.
- The web failure scope is reduced to certain queries or processed results.
- There is not enough evidence to state that the model, API key, general permissions, or `web_search` tool are globally broken.
- Current hypotheses remain unconfirmed and include an error processing specific web results, a specific source combination, an edge case in response construction or normalization, or an unmapped exception for one concrete query.

## Frontend Draft Command Validation

- Date: 2026-07-31
- Case ID: `FE-DRAFT-001`
- Type: Command validation
- Input: `/draft`
- Status: Passed

Observed result:

```text
Use /draft POL1,POL2 | instructions with one to three policy ids and at least 10 characters of instructions.
```

Conclusion:

- Invalid command usage is handled gracefully by showing the expected syntax.

## Frontend Draft Generation

- Date: 2026-07-31
- Case ID: `FE-DRAFT-002`
- Command:

```text
/draft POL320190074 | Create a new health insurance policy for adults. Keep hospitalization, emergency care and surgery coverage, strengthen catastrophic coverage, include outpatient consultations and diagnostic tests, and exclude pre-existing conditions and cosmetic procedures.
```

- Status: Passed

Observed result:

- The draft was generated correctly.
- No backend errors occurred.
- No HTTP 500 occurred.
- Policy information was used.
- PDF sources were cited.
- The document was structured by sections.
- It included a warning that legal and actuarial review is required.
- When specific information was missing, such as limits, deductibles, and catastrophic coverage, the system indicated that it must be defined manually instead of inventing it.

Sources used:

- `POL320190074.pdf`
- Page 16
- Page 2
- Page 6

UX observations:

- References such as `[Fuente 3, u.]` and `[Fuente 3, q.vi]` may be unclear for end users.
- This is classified as a UX improvement, not as a functional bug.
- `Coverage for catastrophic events (to be defined...)` remained deliberately open.
- This is positive responsible-AI behavior because the system preferred not to invent missing information and explicitly left pending fields for human definition.

## Direct API Draft Validation From Swagger

- Date: 2026-07-31
- Endpoint: `POST /generate-policy`
- Execution client: Swagger UI

### API-DRAFT-001 Successful Draft Generation

Payload:

```json
{
  "instructions": "Create a new health insurance policy for adults. Keep hospitalization, emergency care and surgery coverage, strengthen catastrophic coverage, include outpatient consultations and diagnostic tests, and exclude pre-existing conditions and cosmetic procedures.",
  "source_policy_ids": [
    "POL320190074"
  ]
}
```

Result:

- HTTP 200 OK.
- Draft generated correctly.
- Sources present.
- Metadata present.
- Disclaimer present.
- `model = gpt-4.1-mini`.
- `retrieved_chunks = 3`.
- `is_mock = false`.
- No errors occurred.
- Status: Passed.

### API-DRAFT-002 Instruction Length Validation

Payload:

```json
{
  "instructions": "Hi",
  "source_policy_ids": [
    "POL320190074"
  ]
}
```

Result:

- HTTP 422.
- Field: `instructions`.
- Validation: minimum length = 10.
- Status: Passed.

### API-DRAFT-003 Malformed JSON Validation

Scenario:

- Malformed JSON with an additional brace.

Result:

- HTTP 422.
- JSON decode error.
- The parser correctly rejected the JSON before reaching the endpoint logic.
- Robustness test.
- Status: Passed.

### API-DRAFT-004 Minimum Source Policy IDs Validation

Payload:

```json
{
  "instructions": "Create a health insurance policy for adults.",
  "source_policy_ids": []
}
```

Result:

- HTTP 422.
- Field: `source_policy_ids`.
- Validation: minimum items = 1.
- Observed message was equivalent to `List should have at least 1 item after validation.`
- Status: Passed.

## Frontend API-Off Validation

- Date: 2026-07-31
- Case ID: `FE-ERR-API-OFF-001`
- Scenario: frontend behavior when the backend API is unavailable
- Environment: Docker Compose
- Status: Passed

Procedure executed:

1. Started the full stack with `docker compose up -d`.
2. Stopped only the API service with `docker compose stop api`.
3. Verified the frontend remained healthy.
4. Opened Chainlit.
5. Executed `/mode policies`.
6. Executed `/policy POL320190074`.
7. Asked: `What hospital coverage does this policy provide?`
8. Restarted the API with `docker compose start api`.

Observed result:

- The frontend remained responsive.
- The UI displayed: `The backend is unreachable right now. Confirm the API is running and the configured URL is correct.`
- No traceback or internal exception was exposed to the user.
- No infinite loading occurred.
- Chainlit continued running normally.
- Docker logs only contained translation/logo warnings unrelated to the API failure.

Conclusion:

- The frontend handles an unavailable backend API with a controlled user-facing message.
- The failure does not leave the UI stuck in loading state.
- The API was restored after the validation.

## Manual Invalid `/ask` Validation From PowerShell

- Date: 2026-07-31
- Endpoint: `POST /ask`
- Environment: Docker Compose API at `http://localhost:8000`
- Execution client: PowerShell `Invoke-RestMethod`
- Case range: `QA-API-005` through `QA-API-016`
- Overall status: Passed

Results:

- `QA-API-005`: missing required `question` field with `{"policy_id":"POL320190074"}` returned HTTP 422. Validation: `body.question`, field required. Status: Passed.
- `QA-API-006`: empty JSON object `{}` returned HTTP 422. Validation: `body.question`, field required. Status: Passed.
- `QA-API-007`: empty question `{"question":""}` returned HTTP 422. Validation: `string_too_short`, minimum length 3. Status: Passed.
- `QA-API-008`: question shorter than minimum `{"question":"ab"}` returned HTTP 422. Validation: `string_too_short`, minimum length 3. Status: Passed.
- `QA-API-009`: whitespace-only question `{"question":"   "}` returned HTTP 400 with detail `Parámetros de consulta no válidos: question must not be empty`. Status: Passed.
- `QA-API-010`: numeric question `{"question":123}` returned HTTP 422. Validation: `string_type` for `body.question`. Status: Passed.
- `QA-API-011`: null question `{"question":null}` returned HTTP 422. Validation: `string_type` for `body.question`. Status: Passed.
- `QA-API-012`: numeric `policy_id` with `{"question":"What does the policy cover?","policy_id":123}` returned HTTP 422. Validation: `string_type` for `body.policy_id`. Status: Passed.
- `QA-API-013`: null `policy_id` with `{"question":"What does the policy cover?","policy_id":null}` was accepted and returned a normal answer. Status: Passed.
- `QA-API-014`: unknown extra field with `{"question":"What does the policy cover?","unexpected":"value"}` was accepted and returned a normal answer. Status: Passed.
- `QA-API-015`: JSON array body `[]` returned HTTP 422. Validation: `model_attributes_type`; body must be a valid dictionary or object. Status: Passed.
- `QA-API-016`: JSON string body `"What does the policy cover?"` returned HTTP 422. Validation: `model_attributes_type`; body must be a valid dictionary or object. Status: Passed.
- `QA-API-020`: malformed JSON body `{"question":"What does the policy cover?"` returned HTTP 422. Validation type: `json_invalid`; message: JSON decode error. Status: Passed.
- `QA-API-021`: invalid `Content-Type: text/plain` with body `{"question":"What does the policy cover?"}` returned HTTP 422. Validation type: `model_attributes_type`; message: `Input should be a valid dictionary or object to extract fields from`. Status: Passed.

Notes:

- `QA-API-013` is not an invalid request. The schema allows `policy_id` to be null.
- `QA-API-014` is not rejected by the current schema. Extra fields are ignored.
- `QA-API-009` confirms service-level whitespace validation and returns HTTP 400 after schema parsing.
- `QA-API-020` confirms malformed JSON is rejected before endpoint logic.
- `QA-API-021` confirms plain-text request bodies are rejected by schema validation before endpoint execution.
- The remaining HTTP 422 cases confirm FastAPI/Pydantic schema validation.
- Questions used in successful runtime requests were written in English.
- Any visible character-encoding issue in the PowerShell-rendered answer for `QA-API-013` is treated as a console-display issue only, not an API validation failure.

## Frontend Policies No-Evidence Functional Validation

- Date: 2026-07-31
- Case ID: `FE-POL-NOEVIDENCE-001`
- Flow: Chainlit -> `/mode policies` -> `/policy POL320190074` -> `POST /ask`
- Scenario: policy-specific question about a topic not explicitly covered by the policy
- Question: `Does this policy cover damages caused by a spacecraft collision?`
- Status: Passed

Expected behavior:

- The assistant should not fabricate policy content.
- The assistant should acknowledge that the policy does not explicitly address the scenario.
- The assistant should explain that there is insufficient evidence to conclude whether such coverage exists.
- The assistant should cite retrieved policy sources.

Observed result:

- The assistant explicitly stated that the policy does not mention spacecraft collisions.
- The assistant explained that the available evidence was insufficient to determine whether coverage exists.
- The assistant supported the response with retrieved policy sections.

Conclusion:

- Policies-mode no-evidence behavior was validated.
- This is a functional behavior validation, not an API/schema validation case.

## Frontend Auto Routing Validation

- Date: 2026-07-31
- Case ID: `FE-AUTO-001`
- Flow: Chainlit -> `/mode auto` -> `POST /ask`
- Scenario: automatic routing for a general knowledge question
- Question: `Who won the FIFA World Cup in 2022?`
- Status: Passed

Expected behavior:

- The router should classify the question as a general knowledge query.
- The request should use the web route.
- The answer should be produced without querying the policy corpus.

Observed result:

- The assistant correctly answered that Argentina won the 2022 FIFA World Cup.
- Chainlit displayed route `web`.

Conclusion:

- Automatic routing to the web route was validated for a general knowledge question.
- This is a routing behavior validation, not an API/schema validation case.

## Frontend Out-Of-Scope Functional Validation

- Date: 2026-07-31
- Case ID: `FE-OOS-001`
- Flow: Chainlit -> `/mode policies` -> `POST /ask`
- Scenario: out-of-scope creative request while operating in policies mode
- Question: `Write a short poem about the ocean.`
- Status: Passed

Expected behavior:

- The assistant should not generate unsupported creative content.
- The assistant should explain that the request is outside the available policy evidence.
- The assistant should avoid hallucinating.

Observed result:

- The assistant stated that no literary information about the ocean was available in the retrieved policy corpus.
- The assistant declined to generate the requested poem based on unsupported evidence.
- The assistant cited the retrieved policy sources.

Conclusion:

- Out-of-scope behavior was validated in policies mode.
- This is a functional behavior validation, not an API/schema validation case.

## Frontend Timeout Validation

- Date: 2026-07-31
- Case ID: `FE-TIMEOUT-001`
- Scenario: frontend behavior when the backend exceeds the response timeout
- Procedure: paused the API container and submitted a policy query from the frontend
- Status: Passed

Expected behavior:

- The frontend should detect the timeout.
- The frontend should display a user-friendly error message.
- The frontend should remain responsive.
- The frontend should not crash or load indefinitely.

Observed result:

```text
The backend took too long to respond. Please try again.
```

- The application remained responsive.
- No crash occurred.
- No traceback was exposed.
- No infinite loading occurred.

Conclusion:

- Frontend timeout handling was validated.
- This is a functional frontend resilience validation, not an API/schema validation case.

## Observation

During an initial execution, `test_run_profiling_end_to_end` failed with a Tcl/Tk error.

The isolated test passed without code changes. A later full suite execution also passed without code changes.

- Current status: not currently reproducible
- Code changes made for this issue: none

## Warning

The run reported a Starlette/TestClient deprecation warning.

- Priority: low
- Blocking status: non-blocking
- Action in this task: record only

## Historical Docker E2E Certification

- Date: 2026-08-18
- Environment: clean Docker Compose rebuild using the release-candidate worktree
- API: healthy, version 0.5.0
- Frontend: healthy
- Readiness: `ready`, OpenAI configured, Qdrant collection `queplan_policies`, 262 chunks
- Automated suite: 74 passed; two third-party deprecation warnings; zero failures
- Limited log scan: zero error, traceback, exception, timeout or rate-limit
  lines in the last 200 lines of both services for this historical run.

Observed real-service flows:

| Flow | Result | Sources/chunks | Total latency |
|---|---|---:|---:|
| `policies` with `POL320190074` | HTTP 200, grounded answer | 5 / 5 | 10.82 s |
| `web` with Chile regulation query | HTTP 200, current web answer | 12 web sources | 12.77 s |
| `combined` | HTTP 200, policy and web sections | 17 sources | 15.89 s |
| `auto` | HTTP 200, routed to policies | 5 / 5 | 17.19 s outer request |
| `/generate-policy` | HTTP 200, review-only draft and disclaimer | 6 / 6 | 13.33 s |
| `/ask/stream` | Complete SSE response | 13 status + 116 token events | completed without error |

Controlled invalid input returned HTTP 422. Browser QA confirmed route chips,
policy filter, sources, clickable web links, streaming states, latency labels and
mobile layout without horizontal overflow.

Final evaluation smoke checks on the same release candidate:

- OpenAI retrieval, 52 cases: Hit Rate@5 `1.0000`, Recall@5 `0.9341`, MRR `0.8078`.
- RAGAS, two-case smoke subset: Answer Relevancy `0.7487`, Context Relevance
  `1.0000`, overall `0.8743`; both relevance metrics passed the internal `0.60`
  health threshold.
- Latency, two-case smoke subset: mean time-to-model `648.42 ms`, mean model
  time `11,132.05 ms`, mean backend total `11,780.47 ms`.

The two-case latency smoke was slower than the versioned 12-case baseline and
is recorded as provider/network variability, not as a new benchmark or SLA. The
versioned baseline remains the correct summary for the presentation because it
uses more observations.

## Historical Daisy Substitute Sign-Off

- Date: 2026-08-18
- Owner: Mateo Salgado, replacing Daisy Llivisaca for final QA and presentation
- Commit and release: `85f1dc0`, tag `v0.5.0`
- Docker status: API and frontend healthy
- Presentation: eight slides rendered; overflow test passed
- Browser: final home screen loaded with 262 chunks, route chips, configuration
  panel and policy filter visible
- Controlled invalid request: HTTP 422
- Limited Docker log scan: zero matching error lines in the inspected window.

Final real-service replay:

| Flow | Result | Evidence | Backend total |
|---|---|---:|---:|
| `policies` | Passed | 5 PDF sources / 5 chunks | 8.47 s |
| `web` | Passed | 12 web sources | 20.34 s |
| `combined` | Passed | 17 sources | 12.93 s |
| `/generate-policy` | Passed | 6 chunks and review disclaimer | 17.19 s |
| `/ask/stream` | Passed | 10 status, 126 token, 1 complete, 0 error events | completed |

The web and draft timings demonstrate provider variability and are not used as
an SLA. The offline backup question, filtered to `POL320190074`, remains the
required fallback for the live presentation.

## Historical/Superseded Docker Replay From Previous Image

- Date: 2026-08-19
- Validated commit: `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`
- Short commit: `369dbc3`
- Commit message: `Document Daisy QA handoff and final replay`
- Environment: Docker Compose using the latest project version at the exact
  commit above
- API container: healthy
- Frontend container: healthy
- `GET /health`: HTTP 200, `status: healthy`, version `0.3.0`
  from a previous Docker image
- `GET /ready`: HTTP 200
- Readiness fields: `openai_configured: true`, `index_ready: true`,
  `collection: queplan_policies`, `indexed_chunks: 262`
- Historical status: passed for the previous Docker image, then superseded by
  the later clean Docker rebuild that validated API version `0.5.0`.
- Scope note: this replay is retained only to explain the temporary `0.3.0`
  observation. Detailed final release flow evidence is recorded once in
  `Final Release QA - 2026-08-19/20`.

Conclusion:

- This replay passed against commit `369dbc3`, but it is not the final Docker
  build evidence because it used a previous image that reported API `0.3.0`.
- The later clean Docker rebuild replay supersedes the `0.3.0` image-version
  observation and validates the final build as API version `0.5.0`.
- No blocking issue was found.
- No new QA requirement or pending QA task was created by this replay.

## Final Release QA - 2026-08-19/20

- Date: 2026-08-19/20
- Validated commit: `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`
- Short commit: `369dbc3`
- Commit message: `Document Daisy QA handoff and final replay`
- Validated build: clean Docker image rebuild from scratch for final API
  version `0.5.0`.
- Rebuild result: Docker images rebuilt cleanly and the project was started
  again.
- `GET /health`: `healthy`, service `Insurance Policy RAG API`, version
  `0.5.0`.
- `GET /ready`: previously confirmed `ready`, OpenAI configured, index
  available, collection `queplan_policies`, and `262` indexed chunks.
- Docker containers: API healthy; frontend healthy.
- Blocking defects: none found.

Clarification:

- Earlier QA evidence that recorded API version `0.3.0` came from a previous
  Docker image. After the clean rebuild, the validated final Docker build is
  API version `0.5.0`.

### Final E2E Replay On Docker Build `0.5.0`

Conversational Chainlit flows used `POST /ask/stream`. Draft generation used
`POST /generate-policy`.

| Flow | Input | Result | Evidence | Total |
|---|---|---|---|---:|
| Policies | Policy `POL320190074`; `¿Qué es el período de carencia y desde cuándo se cuenta?` | Passed | Correct policy sources displayed. Offline backup question validated. | 8.3 s |
| Web | `¿Cuáles son las tendencias actuales en inteligencia artificial aplicada al sector de seguros?` | Passed | Current web sources displayed. | 8.2 s |
| Combined / Pólizas + web | Policy `POL320190074`; compare catastrophic coverage with current sector information. | Passed | Documentary evidence plus current web evidence displayed. | 7.7 s |
| Draft | `POL320200071,POL320150503`; combine hospitalization clauses and identify information requiring human definition. | Passed | Uses both policies, includes sources and legal/actuarial/compliance review warning. | 17.7 s |

Final automated suite and evaluation replay details are recorded in the
subsections below.

Conclusion:

- The clean Docker rebuild replay validates the final deliverable build as
  API version `0.5.0`.
- The offline backup question is validated correctly with `POL320190074`.
- Presentation baselines remain distinct from the variable final QA replay
  metrics.
- No new QA requirement or pending QA task was created by this replay.

### Automated Suite

- Date: 2026-08-19
- Validated commit: `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`
- Command: `python -m pytest -q`
- Result: Passed
- Summary: `74 passed, 2 warnings in 37.38s`
- Functional failures: none

Warnings recorded:

- Starlette/httpx deprecation warning.
- Pydantic class-based config deprecation warning.

Conclusion:

- The automated suite passed on the validated commit.
- The two warnings are dependency/deprecation warnings and are not functional
  test failures.
- No new QA requirement or pending QA task was created by this execution record.

### Final Evaluation Replay

- Date: 2026-08-19
- Validated commit: `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`
- Scope: final QA replay of retrieval, RAGAS and latency metrics used in the
  presentation.
- Status: Passed

#### Retrieval

- Command: `python scripts/evaluate_retrieval.py --provider openai --top-k 5`
- Total questions: 52
- Labeled questions: 43
- Hit@5: `1.0000`
- Recall@5: `0.9341`
- MRR: `0.8078`
- Result: matches the documented presentation baseline.

#### RAGAS

- Command: `python scripts/evaluate_ragas.py --health-threshold 0.60 --limit 12`
- Cases: 12
- Answer relevancy mean: `0.7078`
- Context relevance mean: `0.9792`
- Overall mean: `0.8435`
- Healthy: `true`
- Result: small expected variation from the LLM-based baseline; no regression
  identified.

#### Latency

- Command: `python scripts/evaluate_latency.py --limit 12`
- Cases: 12
- Mean time to model: `326.93 ms`
- Mean model response: `4889.07 ms`
- Mean backend total: `5216.01 ms`
- Backend total p95: `8392.25 ms`
- Result: latency variation is observational and environment-sensitive, not a
  functional failure.

#### Presentation Baselines

These are reference metrics used in the final presentation, not another QA
execution date. They must remain distinct from the final replay values above.

- Retrieval baseline: matched exactly by the final replay.
- RAGAS baseline: Answer `0.7053`, Context `0.9792`, Overall `0.8422`.
- Latency baseline: time to model `475.06 ms`, model response `4411.09 ms`,
  backend total `4886.15 ms`.

Conclusion:

- Retrieval reproduced the documented presentation metrics exactly.
- RAGAS remained healthy and within expected LLM-evaluation variation compared
  with the stored presentation baseline.
- Latency remained a non-SLA observational benchmark; variation was not treated
  as a blocker.
- No new QA requirement or pending QA task was created by this evaluation replay.

## Post-Integration Automated Report - 2026-08-20

- Tested source commit: `01f4e26`
- Scope: Daisy's final QA documentation integrated with the consolidated
  automated evaluation runner.
- Command: `uv run python scripts/run_all_checks.py --limit 2`
- Generated report: `docs/evaluation-results.md`
- Overall status: passed.
- Ruff: passed.
- Pytest: 77 passed; zero functional failures.
- Local retrieval, 52 cases: Hit Rate@5 `0.6279`, Recall@5 `0.5930`, MRR `0.3981`.
- OpenAI retrieval, 52 cases: Hit Rate@5 `1.0000`, Recall@5 `0.9341`, MRR `0.8078`.
- RAGAS smoke, 2 cases: Answer Relevancy `0.7922`, Context Relevance `1.0000`, Overall `0.8961`, healthy at threshold `0.60`.
- Latency smoke, 2 cases: time-to-model mean `517.08 ms`, model-response mean
  `6861.03 ms`, backend-total mean `7378.12 ms`.

Interpretation:

- The 77-test result supersedes the automated test count only because three
  tests were added for the consolidated report generator.
- Daisy's 12-case final RAGAS and latency replay remains the stronger release
  evidence. The two-case run only verifies that the newly integrated runner
  executes every evaluation family and regenerates the Markdown correctly.
- No presentation baseline was overwritten and no blocking defect was found.
