# QA Checklist

## Environment Preparation

- [x] Editable development installation completed with `pip install -e ".[dev]"`.
- [x] Full test suite executed.
- [x] 24 tests passed.
- [ ] Document required local environment variables without exposing credentials.
- [ ] Confirm a second person can install and run the project from a clean checkout.

## Git And Sensitive Files

- [x] Working tree was clean after the recorded test execution.
- [x] `.env` is ignored by Git according to the inspection already performed.
- [x] `.venv` is ignored by Git according to the inspection already performed.
- [x] PDFs under local data folders are ignored by Git according to the inspection already performed.
- [x] Generated `outputs` are ignored by Git according to the inspection already performed.
- [x] Local data and index contents are ignored by Git according to the inspection already performed.
- [ ] Confirm Git ownership or safe-directory setup for every demo machine.

## API

- [ ] Start the API locally for demo validation.
- [ ] Verify `GET /health`.
- [ ] Verify `GET /config`.
- [ ] Verify `POST /ask`.
- [ ] Confirm Swagger is reachable at `http://127.0.0.1:8000/docs`.

## Validations

- [ ] Verify invalid `/ask` payloads return validation errors.
- [ ] Verify empty or whitespace-only questions are handled by the service layer.
- [ ] Verify `policy_id` remains optional.
- [ ] Confirm API response fields remain `answer`, `sources`, and `metadata`.

## Error Handling

- [ ] Verify API behavior for controlled 4xx responses.
- [ ] Verify API behavior for controlled 5xx responses.
- [ ] Verify timeout handling at the API layer.
- [ ] Verify the frontend behavior when the API is off.
- [ ] Verify timeout behavior from the frontend.

## Frontend

- [ ] Frontend exists.
- [ ] Frontend can be started with a documented repository command.
- [ ] Frontend shows loading state.
- [ ] Frontend shows error state.
- [ ] Frontend shows sources in the UI.

## Frontend To API Integration

- [ ] Frontend sends user questions to `POST /ask`.
- [ ] Frontend renders the `answer` field.
- [ ] Frontend renders the `sources` field.
- [ ] Frontend handles API unavailable state.
- [ ] Frontend handles timeout state.
- [ ] Frontend handles 4xx and 5xx responses.

## Sources

- [ ] Confirm current source format with the team.
- [ ] Verify source strings returned by `/ask`.
- [ ] Verify sources are visible in the UI.
- [ ] Confirm whether source labels must include PDF, article, and page.

## Qdrant And Indexing

- [ ] Versioned command exists to start Qdrant with Docker.
- [ ] Qdrant startup procedure is documented.
- [ ] Indexing pipeline exists.
- [ ] Documents can be indexed into `data/index/qdrant`.
- [ ] Local real index exists for demo validation.

## Real Retrieval

- [ ] Real retrieval can query a local Qdrant index.
- [ ] Real retrieval can use the configured embedding provider.
- [ ] `/ask` can complete against real indexed policy data.
- [ ] Retrieval results include source payloads needed by the API response.

## Demo Preparation

- [ ] Demo runbook is reviewed by QA.
- [ ] API can be started from the documented command.
- [ ] Frontend can be started from a documented command.
- [ ] Qdrant can be started from a documented command.
- [ ] Documents can be indexed from a documented command.
- [ ] Real end-to-end demo can be executed.

## Final Validation By A Second Person

- [ ] A second person can install the project.
- [ ] A second person can run the test command.
- [ ] A second person can start the API.
- [ ] A second person can reproduce the demo setup.
- [ ] A second person confirms known issues and pending items are accurate.
