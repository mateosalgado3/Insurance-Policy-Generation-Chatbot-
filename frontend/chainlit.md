# Insurance Policy RAG Assistant

This chat sends every question to the FastAPI backend at `POST /ask`.
No retrieval or generation happens in this frontend.

Available commands:

- `/policy <id>` — scope subsequent questions to a single policy.
- `/policy clear` — remove the policy scope.
- `/mode auto|policies|web|combined` — choose automatic agent routing or a fixed route.
- `/draft POL1,POL2 | instructions` — create a traceable, review-only draft.
- `/config` — show the active model and index configuration.
