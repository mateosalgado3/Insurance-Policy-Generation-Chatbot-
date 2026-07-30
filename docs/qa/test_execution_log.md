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
