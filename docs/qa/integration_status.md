# Integration Status

## Available

- FastAPI application.
- `GET /health`.
- `GET /config`.
- `POST /ask`.
- API schemas and response contracts.
- `RealRAGService`.
- `FakeRAGService` used in tests through FastAPI `dependency_overrides`.
- Qdrant integration.
- Indexing pipeline.
- Retrieval that returns citable source chunks.
- API tests.
- Embedding tests.
- Dataset profiling tests.
- Indexing tests.
- RAG service tests.
- Automated coverage for grounded answers with citations.
- Automated coverage for abstention when no evidence is found.
- Automated coverage for missing-index handling.

## Manually Validated After Local Indexing

- OpenAI configuration was detected by `GET /ready`.
- The Qdrant collection `queplan_policies` was created or updated by `python -m insurance_chatbot.indexing`.
- The local index was reported as available by `GET /ready`.
- `GET /ready` is operational before and after indexing.
- The readiness state changed from `not_ready` before indexing to `ready` after indexing.
- The index reported 487 chunks from 9 documents using `text-embedding-3-small`.

This manual validation confirms index creation and readiness only. It does not yet validate retrieval quality, answer quality, or citation correctness.

## Manually Validated Functional `/ask` Path

- FastAPI to Qdrant to OpenAI to response flow worked for the first Swagger `/ask` case.
- Retrieval returned 5 chunks.
- Real policy sources were returned for `POL320190074.pdf`.
- Real metadata was returned, including `model: "gpt-4.1-mini"`, `embedding_model: "text-embedding-3-small"`, `policy_id: "POL320190074"`, `retrieved_chunks: 5`, and `is_mock: false`.
- The response included citations in the answer text.

## Manually Validated Grounding For First `/ask` Case

- Grounding of the first `/ask` answer against `POL320190074.pdf` was manually validated.
- The main answer claims matched the cited pages.
- No contradictions were detected.
- No evident hallucinations were detected in this case.
- Page 35 was confirmed as additional context rather than direct support for every listed coverage.
- The first complete end-to-end flow is manually validated: FastAPI to Qdrant to OpenAI to cited answer to PDF page review.

## Current Service Behavior

The normal application path uses `RealRAGService`.

`FakeRAGService` is used by tests through dependency overrides. It should not be treated as the normal runtime service, and this task does not suggest changing the application to use the fake service.

## Pending Or Blocked

- Frontend.
- UI to API flow.
- Source visualization in the UI.
- Frontend validation.
- End-to-end manual validation.
- Versioned command for starting Qdrant with Docker.
- Additional manual `/ask` validation.
- Manual verification of additional answers against cited pages.
- Manual out-of-scope question validation.
- Manual controlled failure validation.
- Selection of final demo questions.
- Real end-to-end demo.

## Detected Inconsistencies To Confirm

- Current sources are returned as `list[str]`.
- The architecture document mentions a more detailed source format with PDF, article, and page.

These differences should be confirmed with the team. They are not corrected in this task.
