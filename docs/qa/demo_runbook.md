# Demo Runbook

This runbook lists only commands that already exist in the repository documentation or configuration and have been identified for the current project state.

Do not place real credentials or real `.env` values in this document.

## Local Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

After copying `.env.example`, fill the local `.env` file outside version control.

## Tests

```powershell
pytest -v -p no:cacheprovider
```

## Start The API

```powershell
python -m uvicorn insurance_chatbot.app:app --app-dir src --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## API Checks

- `GET /health`
- `GET /config`
- `POST /ask`

## Candidate Demo Questions

### Hospital Coverage

```json
{
  "question": "¿Qué coberturas hospitalarias contempla la póliza?",
  "policy_id": "POL320190074"
}
```

Status: validated candidate.

Notes:

- This question produced a real HTTP 200 response from Swagger with retrieved sources and metadata.
- Pages 20, 19, 1, and 18 support the answer.
- Page 35 provides additional context through related definitions.
- This question can remain a demo candidate.
- It is not yet marked as a final demo question until the final demo question set is selected.

## Pending Demo Steps

- Start the frontend: pending; no repository command exists yet.
- Start Qdrant with Docker: pending; no versioned repository command exists yet.
- Index documents: pending; no indexing command exists yet.
- Run the complete real end-to-end demo: pending.
