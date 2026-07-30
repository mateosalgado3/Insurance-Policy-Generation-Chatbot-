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
