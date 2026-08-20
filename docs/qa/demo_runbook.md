# Demo Runbook

This runbook documents the current demo flow using commands already present in `README.md`, `docs/demo.md`, and `compose.yaml`.

Do not place real credentials or real `.env` values in this document.

## 1. Prerequisites

- Docker Desktop must be running.
- A local `.env` file must exist.
- `.env` must include the required OpenAI key expected by Docker Compose.
- Do not commit `.env` or share API keys.

The current Docker Compose stack has two services:

- `api`: FastAPI on `http://127.0.0.1:8000`.
- `frontend`: Chainlit on `http://127.0.0.1:8001`.

Qdrant is used as local persistent storage or a reusable snapshot through `QDRANT_PATH: /app/data/index/qdrant` in the API service. There is no separate Qdrant container in `compose.yaml`.

## 2. Create Or Configure `.env`

If `.env` does not exist yet:

```powershell
Copy-Item .env.example .env
```

After copying `.env.example`, fill the local `.env` file outside version control.

Do not paste real secrets into documentation, issue comments, screenshots, or pull request descriptions.

## 3. Start The Docker Compose Stack

From the repository root:

```powershell
docker compose config
docker compose up --build -d
docker compose ps
```

Expected high-level result:

- The API service is running.
- The frontend service is running.
- Chainlit is available at `http://127.0.0.1:8001`.
- FastAPI is available at `http://127.0.0.1:8000`.

## 4. Verify Backend Readiness

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/config
```

Expected high-level result:

- `/health` reports the API as healthy.
- `/ready` reports `status=ready`.
- `/ready` reports the indexed chunk count from the current local snapshot.
- `/config` returns the current model, embedding, vector store, collection, and mode configuration.

`docs/demo.md` records the final expected snapshot readiness as `indexed_chunks=262`. Older QA evidence recorded a local manual indexing run with 487 chunks; that value is historical and does not define the final release corpus size.

## 5. Open Swagger

Open:

```text
http://127.0.0.1:8000/docs
```

Useful endpoints for demo validation:

- `GET /health`
- `GET /ready`
- `GET /config`
- `POST /ask`
- `POST /generate-policy`

## 6. Open Chainlit

Open:

```text
http://127.0.0.1:8001
```

Useful Chainlit commands:

```text
/config
/mode auto|policies|web|combined
/policy POL320200071
/policy clear
/draft POL320200071,POL320150503 | Combine las cláusulas de cobertura
```

## 7. Select Modes And Policy Filters

Use explicit modes for deterministic demo behavior:

```text
/mode policies
```

```text
/mode web
```

```text
/mode combined
```

To select a policy filter:

```text
/policy POL320190074
```

To clear the policy filter:

```text
/policy clear
```

## 8. Previous QA / Historical Demo Candidates

The cases in this section are retained as useful historical QA evidence. The
current final 0.5.0 live-demo flow is documented in
[Final Release Demo Questions](#12-final-release-demo-questions---2026-08-1920).

### Policies Candidate

Validated through Chainlit as `FE-POL-001`.

```text
/mode policies
/policy POL320190074
What hospitalization expenses are covered by this policy?
```

Expected checks:

- Route displayed as `policies`.
- The response is complete.
- The response is not mock.
- PDF sources are visible in Chainlit.
- Main claims are supported by the cited PDF pages.

Validated sources included:

- `POL320190074.pdf - Página 16 - ARTÍCULO Nº 2`
- `POL320190074.pdf - Página 20 - ARTÍCULO Nº 2`
- `POL320190074.pdf - Página 1 - ARTÍCULO 2º`
- `POL320190074.pdf - Página 3 - ARTÍCULO 3º`
- `POL320190074.pdf - Página 4 - ARTÍCULO 4º`

### Swagger Policies Candidate

Validated through Swagger as `QA-API-004`.

```json
{
  "question": "¿Qué coberturas hospitalarias contempla la póliza?",
  "policy_id": "POL320190074"
}
```

Expected checks:

- HTTP 200 OK.
- Response includes `answer`, `sources`, and `metadata`.
- Metadata includes real execution values, including `is_mock: false`.
- PDF sources are returned.
- Main claims are supported by cited PDF pages.

### Combined Candidate

Validated through Chainlit as `FE-COMB-001`.

```text
/mode combined
Compare the catastrophic coverage described in the policy with recent developments in Ecuador's insurance sector.
```

Expected checks:

- Route displayed as `combined`.
- Response contains separate policy evidence and current web information sections.
- PDF sources are displayed.
- Web sources with URLs are displayed.
- No HTTP 500 occurs.

### General Web Candidate

Validated through Chainlit as `FE-WEB-002`.

```text
/mode web
What is artificial intelligence?
```

Expected checks:

- Route displayed as `web`.
- The response is coherent.
- No HTTP 500 occurs.

This confirms general web mode can work, but it is not a final insurance-sector demo question.

### Auto Routing Candidate

Validated through Chainlit as `FE-AUTO-001`.

```text
/mode auto
Who won the FIFA World Cup in 2022?
```

Expected checks:

- Route displayed as `web`.
- The assistant answers that Argentina won the 2022 FIFA World Cup.
- The question is treated as general knowledge rather than a policy-corpus query.

This validates historical routing behavior and is not part of the final 0.5.0 live-demo question list.

### Policies No-Evidence Candidate

Validated through Chainlit as `FE-POL-NOEVIDENCE-001`.

```text
/mode policies
/policy POL320190074
Does this policy cover damages caused by a spacecraft collision?
```

Expected checks:

- The assistant does not fabricate policy content.
- The assistant states that the policy does not explicitly mention spacecraft collisions.
- The assistant explains that the available evidence is insufficient to determine whether such coverage exists.
- Retrieved policy sources are cited.

This validates historical no-evidence behavior in policies mode and is not part of the final 0.5.0 live-demo question list.

### Out-Of-Scope Candidate

Validated through Chainlit as `FE-OOS-001`.

```text
/mode policies
Write a short poem about the ocean.
```

Expected checks:

- The assistant does not generate unsupported creative content.
- The assistant explains that no literary information about the ocean is available in the retrieved policy corpus.
- The assistant declines to generate the poem based on unsupported evidence.
- Retrieved policy sources are cited.

This validates historical out-of-scope behavior in policies mode and is not part of the final 0.5.0 live-demo question list.

### Draft Candidate

Validated through Chainlit as `FE-DRAFT-002`.

```text
/draft POL320190074 | Create a new health insurance policy for adults. Keep hospitalization, emergency care and surgery coverage, strengthen catastrophic coverage, include outpatient consultations and diagnostic tests, and exclude pre-existing conditions and cosmetic procedures.
```

Expected checks:

- Draft is generated.
- No backend error occurs.
- PDF sources are cited.
- Disclaimer or review warning is included.
- Missing limits, deductibles, or catastrophic coverage details are left for manual definition instead of invented.

## 9. Historical Web Regression Case

The following historical `FE-WEB-001` question is retained as a regression case,
but the live demo uses a Chile-specific regulatory query:

```text
/mode web
What are the most relevant recent developments in Ecuador's insurance sector?
```

Final result:

- The historical failure was caused by an empty final model output after the
  previous output budget was consumed.
- The backend now uses a larger output budget and converts empty final text into
  a controlled degraded response.
- The exact original question returns HTTP 200 with web sources.
- Final evidence for the Chile demo query is stored in `13-web-final.png`.

## 10. Check That Sources Are Displayed

For policies mode:

- Confirm source labels are visible in Chainlit.
- Confirm each source includes PDF filename and page/article information when available.

For combined mode:

- Confirm PDF sources are visible.
- Confirm web sources with URLs are visible.
- Confirm policy evidence and web information are displayed as separate sections.

For draft generation:

- Confirm PDF sources are cited.
- Confirm the draft includes a disclaimer or review warning.

## 11. QA Evidence Package

All manual QA execution evidence is stored in:

```text
docs/qa/screenshots/
```

| Screenshot | Description |
|---|---|
| `01-policy-setup.png` | Policies mode selection and policy selection before querying |
| `02-policy-response.png` | Successful policy answer with retrieved sources |
| `03-no-evidence-setup.png` | No-evidence scenario setup |
| `04-no-evidence-response.png` | No-evidence response showing insufficient evidence and retrieved sources |
| `05-auto-route-web.png` | Automatic routing to the web route |
| `06-out-of-scope.png` | Out-of-scope request handled without hallucination |
| `07-api-unreachable.png` | Frontend behavior when the backend is unavailable |
| `08-timeout.png` | Frontend timeout handling |
| `09-health-endpoint.png` | Health endpoint verification |
| `10-config-endpoint.png` | Configuration endpoint verification |

Do not include `.env` values or API keys in screenshots.

## 12. Final Release Demo Questions - 2026-08-19/20

These are the final 0.5.0 demo questions validated after the clean Docker
rebuild. Older candidates above remain useful as regression evidence but should
not be treated as the current release script.

### Demo 1 - Policies Mode

Commands:

```text
/mode policies
/policy POL320190074
```

Question:

```text
¿Qué es el período de carencia y desde cuándo se cuenta?
```

Purpose:

- Demonstrate policy retrieval.
- Demonstrate grounded answers.
- Demonstrate retrieved sources.
- Show route `policies`.
- Validate the official offline backup question with `POL320190074`.

### Demo 2 - Web Mode

Command:

```text
/mode web
```

Question:

```text
¿Cuáles son las tendencias actuales en inteligencia artificial aplicada al sector de seguros?
```

Purpose:

- Demonstrate current web search.
- Show route `web`.
- Show current web sources with URLs.

### Demo 3 - Combined Mode

Command:

```text
/mode combined
/policy POL320190074
```

Question:

```text
Compara la cobertura catastrófica de la póliza con información actual del sector asegurador.
```

Purpose:

- Demonstrate policy and web evidence in one response.
- Show route `combined`.
- Confirm policy evidence and current web information remain separated.

### Demo 4 - Draft Generation

Command:

```text
/draft POL320200071,POL320150503 | Combine the hospitalization coverage clauses and identify the information that requires human definition.
```

Purpose:

- Demonstrate review-only policy drafting.
- Confirm both source policies are used.
- Confirm sources and legal/actuarial/compliance review warning are displayed.

## 13. Final Release Demo Flow

Recommended live presentation order:

1. Start Chainlit.
2. Switch to policies mode.
3. Select policy `POL320190074`.
4. Ask the official offline backup question.
5. Show the retrieved sources.
6. Switch to web mode and ask the current AI-in-insurance trends question.
7. Switch to combined mode, keep policy `POL320190074`, and ask the catastrophic-coverage comparison question.
8. Run the draft command with `POL320200071,POL320150503`.
9. Conclude by mentioning that API unreachable, timeout, no-evidence, auto-routing, and out-of-scope scenarios were validated during historical QA and are documented in the QA evidence package, without reproducing them live.

Presenter notes:

- Keep the demo under 5-7 minutes.
- Scroll to the sources section when answering policy questions.
- Emphasize that answers are grounded in retrieved evidence.
- Mention that backend failure scenarios were already validated during QA and are documented separately.

## 14. Stop The Stack

Before shutting down, optionally inspect recent logs:

```powershell
docker compose logs --tail 100
```

Stop the stack:

```powershell
docker compose down
```

## 15. Basic Troubleshooting

### `/ready` Is Not Ready

- Confirm Docker Desktop is running.
- Confirm the stack was started with `docker compose up --build -d`.
- Confirm `/ready` reports the expected collection and indexed chunk count.
- Record the exact `/ready` response before changing anything.

### Chainlit Cannot Reach The Backend

- Confirm `docker compose ps` shows both services running.
- Confirm `http://127.0.0.1:8000/health` responds.
- Confirm Chainlit is opened at `http://127.0.0.1:8001`.

### Web Query Returns HTTP 500

- Check whether the question is the known `FE-WEB-001` query.
- Use the validated general web query only as a smoke check.
- Do not claim a definitive root cause without backend traceback or reproduced diagnostic evidence.

### Backend Request Times Out

- `FE-TIMEOUT-001` validated that Chainlit displays `The backend took too long to respond. Please try again.`
- The frontend should remain responsive.
- No traceback, crash, or infinite loading should be visible to the user.

### Draft Citation Labels Are Hard To Interpret

- This is a documented UX observation.
- Draft generation is still functionally validated.
- Do not classify citation-label wording as a backend failure unless draft generation itself fails.

### Swagger Examples Look Outdated

- This is a documented OpenAPI/documentation issue.
- Prefer actual endpoint responses over Swagger example values during QA.
