# Known Issues

## Active Non-Blocking Items

## Starlette/TestClient Deprecation Warning

- Impact: low
- Status: non-blocking
- Notes: recorded during the latest automated test execution as a dependency/deprecation warning. No dependency or package changes are proposed in this task.

## Pydantic Class-Based Config Deprecation Warning

- Impact: low
- Status: non-blocking
- Notes: recorded during the latest automated test execution as a dependency/deprecation warning. It did not cause any functional test failure.

## Resolved Historical Issues

## Resolved Docker Version Mismatch

- Impact: medium
- Status: resolved
- Notes: earlier QA evidence showed API `0.3.0` because an older Docker image
  was running. After a clean rebuild, final QA validated API `0.5.0`. No
  runtime defect remains from this mismatch.

## Swagger Example Does Not Match The Actual `/health` Response

- Description: Swagger UI displays `"string"` as the example value, while the endpoint actually returns a JSON object containing `status`, `service`, and `version`.
- Impact: low
- Severity: documentation only
- Status: resolved
- Resolution: `HealthResponse` now publishes a representative JSON example in the generated OpenAPI schema.

## Swagger Example For `/ask` Response Appears Outdated

- Type: documentation/OpenAPI
- Priority: low
- Impact: does not affect API execution, but may confuse QA or demo preparation.
- Status: resolved
- Description: the Swagger response 200 example for `/ask` includes outdated values such as `sentence-transformers/all-MiniLM-L6-v2` and `health_policy_inventada.pdf`, while the real execution used `gpt-4.1-mini`, `text-embedding-3-small`, and `POL320190074.pdf`.
- Resolution: the public `AskResponse` example now uses the active model family, embedding model and a real QuePlan policy identifier.

## FE-WEB-001 - Specific Web Query Returns HTTP 500

- Reproducibility: observed during manual Chainlit execution with `/mode web` and the exact question `What are the most relevant recent developments in Ecuador's insurance sector?`
- Impact: limited to certain web queries or processed web results. This exact query is excluded from the recommended demo flow, but the issue does not block the completed QA package.
- Status: resolved and regression-tested
- Observed behavior: Chainlit displayed a controlled backend error message. Frontend logs showed `POST http://localhost:8000/ask` returning HTTP 500, and backend logs showed `POST /ask HTTP/1.1 500 Internal Server Error`.
- Root cause: the web model consumed the previous 700-token output budget while reasoning and returned no final text.
- Evidence narrowing scope: `FE-WEB-002` passed with the general web query `What is artificial intelligence?`; `FE-COMB-001` passed and used web retrieval successfully inside the `combined` flow.
- Resolution: web calls now use low reasoning effort, low verbosity and a 2,000-token output budget. Empty final text degrades to a controlled answer instead of HTTP 500. The exact original query returned HTTP 200 with web sources.

## Chainlit Locale And Logo Warnings

- Impact: none after resolution
- Status: resolved
- Resolution: added the Spanish welcome document and theme-specific logo assets expected by Chainlit.

## Accepted Non-Blocking Limitation

## UX Observation - Draft Citation Labels

- Type: UX improvement
- Impact: non-functional
- Status: accepted non-blocking limitation
- Observation: some internal citation labels, such as `[Fuente 3, q.vi]` and `[Fuente 3, u.]`, may not be meaningful for end users.
- Notes: this is not classified as a functional defect. Draft generation completed successfully and cited policy sources.

## Final release status

No open blocking defect remains as of the 2026-08-19 clean Docker rebuild and
final release replay on commit `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d`.
The remaining items in this document are low-impact dependency warnings or
accepted presentation/UX limitations.
