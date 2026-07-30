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
