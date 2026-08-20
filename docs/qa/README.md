# QA Documentation

This folder contains the finalized QA, integration, and demo-preparation notes for the Insurance Policy Generation Chatbot repository.

The documents are intended to help another person understand what has been verified, review the evidence package, and run the documented demo flow without changing the RAG logic or API contracts.

## Chronology And Evidence Layers

- **Previous QA:** earlier manual, API, frontend, negative-path, resilience, and exploratory validation. These entries keep their original execution dates and are not presented as rerun during the final release session.
- **Final Release QA - 2026-08-19/20:** final validation for commit `369dbc3aaf23cf15d8ede4d83538e16b4b1a571d` and clean Docker build API `0.5.0`. This includes the final Docker/E2E replay, 74-test automated suite, final evaluation replay, 262 indexed chunks, and no blocking defects.
- **Historical/Superseded Evidence:** traceability records that no longer represent the final release, including the earlier Docker image that reported API `0.3.0`, the older 487-chunk local index, older demo candidates, and earlier release-candidate checks.
- **Presentation Baselines:** retrieval, RAGAS, and latency reference metrics used in the final slides. These are kept separate from the final replay metrics and should not be overwritten by variable replay results.

## Documents

- [QA checklist](qa_checklist.md): verification checklist for environment, API, Git hygiene, integration, sources, Qdrant, retrieval, and demo readiness.
- [API manual test cases](api_manual_test_cases.md): previous manual API cases plus the limited final release API endpoint evidence.
- [Test execution log](test_execution_log.md): chronological execution evidence; detailed final release evidence lives here.
- [Integration status](integration_status.md): concise current implementation status with a short final release summary.
- [Demo runbook](demo_runbook.md): current final demo flow, with older demo candidates marked historical.
- [Known issues](known_issues.md): active non-blocking warnings and resolved historical issues.
