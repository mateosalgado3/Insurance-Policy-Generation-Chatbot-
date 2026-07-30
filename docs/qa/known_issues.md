# Known Issues

## Starlette/TestClient Deprecation Warning

- Impact: low
- Status: non-blocking
- Notes: recorded during the test execution. No dependency or package changes are proposed in this task.

## Initial Non-Reproducible Tcl/Tk Failure

- Impact: low at this time
- Status: monitor
- Notes: an initial `test_run_profiling_end_to_end` execution failed with a Tcl/Tk error. The isolated test passed without code changes, and the later full suite passed without code changes.

## Frontend Is Not Present

- Impact: blocks end-to-end QA
- Status: pending implementation
- Notes: no frontend startup command or UI flow is currently available in the repository.

## Qdrant And Indexing Procedure Is Not Versioned

- Impact: blocks real `/ask` execution and reproducible demo
- Status: pending implementation or documentation
- Notes: no versioned Docker command for Qdrant and no indexing pipeline into `data/index/qdrant` are currently available.

## Possible Documentation And Runtime Misalignment

- Impact: medium
- Status: confirm with the team
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
