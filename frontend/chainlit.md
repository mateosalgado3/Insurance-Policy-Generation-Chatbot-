# Insurance Policy RAG Assistant

This chat sends every question to the FastAPI backend at `POST /ask`.
No retrieval or generation happens in this frontend.

Available commands:

- `/policy <id>` — scope subsequent questions to a single policy.
- `/policy clear` — remove the policy scope.
- `/config` — show the active model and index configuration.
