# Integration Status

## Available

- FastAPI application.
- `GET /health`.
- `GET /config`.
- `POST /ask`.
- API schemas and response contracts.
- `RealRAGService`.
- `FakeRAGService` used in tests through FastAPI `dependency_overrides`.
- API tests.
- Embedding tests.
- Dataset profiling tests.
- RAG service tests.

## Current Service Behavior

The normal application path uses `RealRAGService`.

`FakeRAGService` is used by tests through dependency overrides. It should not be treated as the normal runtime service, and this task does not suggest changing the application to use the fake service.

## Pending Or Blocked

- Frontend.
- UI to API flow.
- Source visualization in the UI.
- Versioned command for starting Qdrant with Docker.
- Indexing pipeline into `data/index/qdrant`.
- Real local index.
- Real end-to-end demo.

## Detected Inconsistencies To Confirm

- `README.md` and `docs/architecture.md` may be outdated regarding the current use of `RealRAGService`.
- `/config` reports `Chroma` by default, while the current code uses Qdrant.
- Current sources are returned as `list[str]`.
- The architecture document mentions a more detailed source format with PDF, article, and page.

These differences should be confirmed with the team. They are not corrected in this task.
