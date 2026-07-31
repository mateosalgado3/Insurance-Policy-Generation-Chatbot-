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

## Manual Indexing And Readiness Validation

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

This does not yet validate retrieval quality or answer quality manually.

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

## PowerShell `/ask` Attempt Needs Retest

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

- Status: Needs retest

Notes:

- The server rejected the body because it could not parse it as JSON.
- This is not classified as a confirmed `/ask` product bug because the same endpoint responded with HTTP 200 OK from Swagger.
- The probable retest area is the preparation or content of the local `$body` variable, but no definitive cause is recorded without reproducing it.

Suggested retest procedure, not yet executed:

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
- Automated suite context: latest reported suite passed with 54 passed and 2 warnings

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
