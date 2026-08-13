# Periodo de carencia — RAG tuning and RAGAS diagnostic

## Objective

Investigate the weak `periodo_carencia` evaluation case and determine whether
model-generation or retrieval changes can improve Answer Relevancy without
degrading grounding, citations, or latency.

The official evaluation reported:

- Answer Relevancy: `0.3922`
- Context Relevance: `1.0000`

Evaluation question:

> ¿Qué es el período de carencia y desde cuándo se cuenta?

Policy:

`POL320190074`

Expected relevant chunk:

`POL320190074-art5-001`

The expected chunk contains both requested facts: the definition of the waiting
period and the point from which it starts.

## Baseline reproduction

The case was reproduced locally with the production policy RAG configuration:

- Generator: `gpt-4.1-mini`
- Evaluator: `gpt-4.1-mini`
- Embeddings: `text-embedding-3-small`
- Retrieval: Qdrant
- `top_k=5`

Results:

| Metric | Official | Local reproduction |
|---|---:|---:|
| Answer Relevancy | 0.3922 | 0.3932 |
| Context Relevance | 1.0000 | 1.0000 |

The local result reproduces the official weak case closely.

The baseline answer contained the requested information but also included
repeated explanations and information from additional retrieved chunks.

## Baseline latency

A local single-case latency measurement produced:

| Phase | Time |
|---|---:|
| Time to model | 1739.44 ms |
| Model response time | 6300.07 ms |
| Backend total time | 8039.51 ms |
| Client observed time | 8039.57 ms |

These are single-run measurements that include network and OpenAI response
latency, so they are treated as observational rather than deterministic.

## Experiment 1 — Concise factual-answer prompt

A prompt variant was tested that instructed the generator to answer factual and
definitional questions directly, answer each requested part once, avoid
unsolicited examples and summaries, and preserve source citations.

Results:

| Metric | Baseline | Concise candidate |
|---|---:|---:|
| Answer Relevancy | 0.3932 | 0.3898 |
| Context Relevance | 1.0000 | 1.0000 |
| Backend latency | 8039.51 ms | 4558.84 ms |

The candidate substantially reduced repetition and the observed backend latency,
but Answer Relevancy did not improve.

Decision: **REJECTED**.

The production prompt was restored.

## Experiment 2 — Retrieval depth

Retrieval depth was evaluated independently.

With `top_k=1`, retrieval returned exactly the expected chunk:

`POL320190074-art5-001`

The resulting answer was short, grounded, and directly answered both parts of
the question with a single source citation.

However, repeated testing showed that the Answer Relevancy improvement was not
stable.

An isolated run reached:

`0.6192`

but subsequent repeated runs with the candidate configuration produced:

| Run | Answer Relevancy | Context Relevance |
|---:|---:|---:|
| 1 | 0.3898 | 1.0000 |
| 2 | 0.3898 | 1.0000 |
| 3 | 0.3898 | 1.0000 |

The isolated `0.6192` result was therefore not treated as a reproducible
improvement.

A `top_k=1` latency run produced:

| Phase | Time |
|---|---:|
| Time to model | 1311.65 ms |
| Model response time | 2063.58 ms |
| Backend total time | 3375.24 ms |
| Client observed time | 3375.29 ms |

Although the observed latency was much lower, `top_k=1` was not accepted as a
global production setting because it reduced grounding quality for another
validation case.

For `cirugia_ambulatoria`, Context Relevance was:

- `top_k=1`: `0.5000`
- `top_k=5`: `0.7500`

This demonstrates that globally reducing retrieval depth can remove useful
evidence required by other questions.

Decision: **REJECTED as a global production change**.

## Experiment 3 — Prompt and retrieval combinations

Several general prompt strategies were tested to reduce repetition and better
preserve multipart question structure.

With the final evidence-focused prompt, repeated results were stable:

| Retrieval depth | Run 1 | Run 2 | Run 3 | Context Relevance |
|---|---:|---:|---:|---:|
| top_k=1 | 0.3898 | 0.3898 | 0.3898 | 1.0000 |
| top_k=2 | 0.4023 | 0.4023 | 0.4023 | 1.0000 |
| top_k=5 | 0.4023 | 0.4023 | 0.4023 | 1.0000 |

For `top_k=2`, the retrieved chunks were:

`POL320190074-art5-001`

and

`POL320190074-art3-003`

The second chunk caused the answer to introduce additional information such as
premium payment and death during the waiting period, even though those details
were not required by the question.

Additional prompt tuning did not produce a reproducible score above the `0.60`
health threshold.

Decision: **REJECTED**.

## Cross-case validation

A five-case validation subset was also evaluated to check whether `top_k=1`
could safely be adopted globally.

With the candidate prompt and `top_k=1`:

- Mean Answer Relevancy: `0.6314`
- Mean Context Relevance: `0.9000`
- Minimum Context Relevance: `0.5000`

With the same prompt and `top_k=5`:

- Mean Answer Relevancy: `0.6082`
- Mean Context Relevance: `0.9500`
- Minimum Context Relevance: `0.7500`

The drop in Context Relevance confirms that `top_k=1` is too aggressive as a
global retrieval setting.

## RAGAS AnswerRelevancy investigation

The installed RAGAS implementation uses `AnswerRelevancy(strictness=3)`.

For each evaluated answer it:

1. generates three questions from the answer using an evaluator LLM;
2. embeds the original user question;
3. embeds each generated question;
4. computes cosine similarity between the original question and each generated
   question;
5. returns their mean similarity, unless the response is classified as
   noncommittal.

The generated question does not receive the original user question as input.

For the following grounded RAG answer:

> El período de carencia es un lapso durante el cual el asegurado no recibe la
> cobertura prevista en la póliza. Este período se cuenta desde la fecha de
> inicio de la vigencia individual del asegurado en la póliza hasta una fecha
> posterior determinada y especificada en las Condiciones Particulares
> [Fuente 1].

the default evaluator generated exactly the same English question three times:

> What is the waiting period in an insurance policy?

Results:

| Generated question | Cosine similarity |
|---|---:|
| Question 1 | 0.3898 |
| Question 2 | 0.3898 |
| Question 3 | 0.3898 |

Final Answer Relevancy:

`0.3898`

The generated question has two important differences from the original user
question.

Original:

> ¿Qué es el período de carencia y desde cuándo se cuenta?

Generated:

> What is the waiting period in an insurance policy?

The evaluator both changes the language from Spanish to English and drops the
second intent asking when the waiting period starts.

## Embedding diagnostic

To isolate these effects, several manually controlled questions were embedded
using the same `text-embedding-3-small` model and compared against the original
question.

| Comparison question | Cosine similarity |
|---|---:|
| `What is the waiting period in an insurance policy?` | 0.3898 |
| `¿Qué es el período de carencia en una póliza?` | 0.7616 |
| `What is the waiting period in an insurance policy and when does it start?` | 0.3933 |
| Original Spanish compound question | 1.0000 |

This diagnostic indicates that the cross-language transformation is the largest
factor affecting this particular Answer Relevancy score.

Preserving Spanish while still omitting the second intent increased similarity
from `0.3898` to `0.7616`.

Adding the missing second intent while remaining in English changed similarity
only from `0.3898` to `0.3933`.

## Same-language RAGAS diagnostic

A final diagnostic reproduced the RAGAS question-generation process under two
conditions.

Default RAGAS behavior:

| Run | Generated question | Similarity |
|---:|---|---:|
| 1 | `What is the waiting period in an insurance policy?` | 0.3899 |
| 2 | `What is the waiting period in an insurance policy?` | 0.3899 |
| 3 | `What is the waiting period in an insurance policy?` | 0.3899 |

Mean:

`0.3899`

Diagnostic condition with only one additional instruction — generate the
question in the same language as the answer:

| Run | Generated question | Similarity |
|---:|---|---:|
| 1 | `¿Qué es el período de carencia en una póliza de seguro?` | 0.7339 |
| 2 | `¿Qué es el período de carencia en una póliza de seguro?` | 0.7340 |
| 3 | `¿Qué es el período de carencia en una póliza de seguro?` | 0.7339 |

Mean:

`0.7339`

Absolute difference:

`+0.3441`

Relative difference:

`+88.25%`

This experiment is diagnostic only. The official RAGAS prompt, evaluator,
threshold, question dataset, and baseline were not changed.

## Final decision

No production model or retrieval change was accepted.

The evidence shows that:

- the expected `POL320190074-art5-001` chunk is retrieved correctly;
- the generated answer contains both requested facts;
- source citation and traceability are preserved;
- Context Relevance remains `1.0` for the target case;
- prompt changes did not produce a reproducible Answer Relevancy improvement;
- globally reducing `top_k` can reduce grounding quality for other questions;
- the low `periodo_carencia` Answer Relevancy score is strongly affected by the
  evaluator generating an English question from a Spanish response and by the
  generated question omitting the second intent.

The production baseline is therefore preserved instead of optimizing the RAG
system for a single evaluator-specific behavior.

The RAGAS language behavior should be treated as an evaluation-system finding
and can be reviewed separately from production model/retrieval tuning.

## Reproduction

Baseline target-case evaluation:

```powershell
python scripts\evaluate_ragas.py `
  --questions-path outputs\periodo_carencia_subset.json `
  --output-path outputs\periodo_carencia_before_ragas.json `
  --top-k 5
```

Baseline latency:

```powershell
python scripts\evaluate_latency.py `
  --questions-path outputs\periodo_carencia_subset.json `
  --output-path outputs\periodo_carencia_before_latency.json `
  --top-k 5
```

Final repository validation:

```powershell
python -m ruff check src scripts frontend tests
$env:MPLBACKEND="Agg"
python -m pytest -q
```