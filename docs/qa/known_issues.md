# Known Issues

## Starlette/TestClient Deprecation Warning

- Impact: low
- Status: non-blocking
- Notes: recorded during the test execution. No dependency or package changes are proposed in this task.

## Possible Documentation And Runtime Misalignment

- Impact: medium
- Status: optional future documentation cleanup
- Notes: repository documentation, `/config`, and the current implementation appear partially misaligned. This task records the issue only and does not correct it.

## Swagger Example Does Not Match The Actual `/health` Response

- Description: Swagger UI displays `"string"` as the example value, while the endpoint actually returns a JSON object containing `status`, `service`, and `version`.
- Impact: low
- Severity: documentation only
- Status: open
- Notes: no functional impact. The endpoint behaves correctly; only the generated OpenAPI example appears inconsistent.

## Swagger Example For `/ask` Response Appears Outdated

- Type: documentation/OpenAPI
- Priority: low
- Impact: does not affect API execution, but may confuse QA or demo preparation.
- Status: open
- Description: the Swagger response 200 example for `/ask` includes outdated values such as `sentence-transformers/all-MiniLM-L6-v2` and `health_policy_inventada.pdf`, while the real execution used `gpt-4.1-mini`, `text-embedding-3-small`, and `POL320190074.pdf`.
- Notes: no code changes are proposed or applied in this task.

## FE-WEB-001 - Specific Web Query Returns HTTP 500

- Reproducibility: observed during manual Chainlit execution with `/mode web` and the exact question `What are the most relevant recent developments in Ecuador's insurance sector?`
- Impact: limited to certain web queries or processed web results. This exact query is excluded from the recommended demo flow, but the issue does not block the completed QA package.
- Status: documented; optional future investigation
- Observed behavior: Chainlit displayed a controlled backend error message. Frontend logs showed `POST http://localhost:8000/ask` returning HTTP 500, and backend logs showed `POST /ask HTTP/1.1 500 Internal Server Error`.
- Root cause: not determined within the completed QA scope.
- Evidence narrowing scope: `FE-WEB-002` passed with the general web query `What is artificial intelligence?`; `FE-COMB-001` passed and used web retrieval successfully inside the `combined` flow.
- Notes: no definitive cause is recorded. The `policies` route works, `/ready` returns 200, `/config` returns valid configuration, general web queries can execute successfully, and combined web retrieval can execute successfully.

## UX Observation - Draft Citation Labels

- Type: UX improvement
- Impact: non-functional
- Status: open
- Observation: some internal citation labels, such as `[Fuente 3, q.vi]` and `[Fuente 3, u.]`, may not be meaningful for end users.
- Notes: this is not classified as a functional defect. Draft generation completed successfully and cited policy sources.
