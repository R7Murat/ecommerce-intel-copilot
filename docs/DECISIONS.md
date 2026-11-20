# Decision Log

## D1 — Multi-agent architecture (Supervisor pattern)

**Decision:** Split the system into five specialized agents — a Supervisor for routing
and synthesis, a SQL Analyst, a Knowledge (RAG) agent, a deterministic Market Analyst,
and a Critic for groundedness — orchestrated with LangGraph.

**Rationale:** The target questions require three distinct capabilities (structured
querying, sourced retrieval, quantitative analysis). A single prompt handling all three
mixes concerns and hallucinates across them. Narrow agents give narrow failure surfaces,
and each component can be evaluated separately (SQL execution accuracy, faithfulness,
trajectory accuracy). The agent count is capped at five: every added agent adds
evaluation, failure, and cost surface.

**Rejected alternative:** A single RAG chain with one LLM. Simpler and cheaper, and the
right choice for a homogeneous FAQ-style workload — rejected here because the question
types are genuinely heterogeneous and per-component quality guarantees were a project goal.

## D2 — Product sizing filter: 300 <= rating_number < 1000

**Decision:** Keep only products with 300–999 ratings, yielding 5,006 products and
441,857 reviews.

**Rationale:** The raw distribution is extremely skewed (sample median: 22 ratings;
max: 30,959). The lower bound removes products with too few reviews for meaningful
analysis; the upper bound prevents a handful of mega-products from dominating the
retrieval corpus. The resulting size fits both targets (2k–10k products, 100k–500k
reviews) and stays tractable for local processing.

**Rejected alternative:** No upper bound, filtering only `rating_number >= 300`.
Rejected because a few products with 30k+ reviews would account for a disproportionate
share of the corpus and bias retrieval toward them.

## D3 — Direct jsonl streaming instead of dataset scripts

**Decision:** Load the dataset via the generic `json` builder pointing at the raw
`.jsonl` files (`hf://` paths), rather than the repository's loading script.

**Rationale:** `datasets` >= 3.x removed support for dataset scripts entirely
(`RuntimeError: Dataset scripts are no longer supported`). The raw files are available
in the same repository, so streaming them directly restores functionality with no
loss of data and no dependency on deprecated behavior.

**Rejected alternative:** Pinning `datasets` to an old 2.x version. Rejected because
it would freeze the project on an unmaintained dependency line for the sake of one
loading path — a growing liability for a project meant to be deployed.

## D4 — Minimum review length of 20 characters for the retrieval corpus

**Decision:** Exclude reviews shorter than 20 characters from the Chroma corpus
(kept in SQLite). This drops ~12.6% of reviews (441,857 → 386,053).

**Rationale:** EDA showed reviews as short as one character ("A", "ok"). Such texts
carry no retrievable meaning but still consume embedding time and can surface as noise
in top-k results. The threshold trades a small recall loss for cleaner retrieval.

**Rejected alternative:** Embedding everything and relying on ranking to bury short
texts. Rejected because it spends compute on valueless documents and measurably
pollutes small-k results.

## D5 — Custom LLM-as-judge instead of the RAGAS library

**Decision:** Implement faithfulness and answer-relevance as ~60 lines of custom
LLM-as-judge code (RAGAS-style metrics) rather than integrating the RAGAS library.

**Rationale:** The metrics' core logic is simple (claim-support counting; question-answer
alignment scoring). A custom implementation adds zero dependencies, runs on the existing
provider abstraction, and keeps every scoring step transparent and explainable. The judge
parser was subsequently hardened (JSON-first parsing, 0-1 clamping) after a live scoring
bug — a fix that would have been opaque inside a library.

**Rejected alternative:** The RAGAS library. Rejected because it pulls in the LangChain
dependency chain, requires extra configuration to route its judge through our free-tier
providers, and turns the metric internals into a black box for a project whose goal
includes demonstrating evaluation literacy.

## D6 — Groq as the primary LLM provider

**Decision:** Swap the provider roles: Groq (Llama 3.3 70B) is primary; Gemini 2.5 Flash
is the fallback.

**Rationale:** Measured free-tier limits contradicted planning assumptions: Gemini 2.5
Flash allows 20 requests/day (5/min), while Groq allows 1,000/day (30/min). Evaluation
runs alone exceed Gemini's daily quota. During the Phase 2 run, Groq carried effectively
all traffic through the fallback path; making it primary removes a guaranteed 429 round
trip from every call. The litellm abstraction made this a two-line configuration change.

**Rejected alternative:** Keeping Gemini primary and throttling to its limits. Rejected
because 5 requests/min would make evaluation runs take hours and cripple interactive use.

## D7 — Deadline-driven scope cuts (backlogged, not cancelled)

**Decision:** For the delivery deadline: (a) replace Langfuse with a built-in trace panel
in the Streamlit UI (agent path, per-step info from graph state); (b) keep the AWS
GitHub Actions workflow in the repo but run the provision-validate-destroy cycle from
local Terraform only.

**Rationale:** Observability and IaC evidence goals are still met with lower integration
risk; both full versions remain in the backlog.

**Rejected alternative:** Compressing evaluation or testing instead — rejected because
measurement discipline is this project's core differentiator.

## D8 — Deployment platform: Streamlit Community Cloud

**Decision:** Serve the live demo on Streamlit Community Cloud, with the prepared data
hosted in a public HF dataset repo and downloaded on first boot.

**Rationale:** Mid-project, Hugging Face's free tier stopped offering Gradio/CPU-basic
Spaces to free accounts (forum-confirmed rollout the same week). Streamlit Cloud is
free without a card, deploys directly from GitHub, and our primary UI was already
Streamlit — the pivot cost ~40 minutes. Separating code (git) from data (dataset repo)
also turned a platform storage limit into a cleaner architecture.

**Rejected alternatives:** HF ZeroGPU workaround (dummy @spaces.GPU probe) — untested
against a moving policy; Modal/Render/Cloud Run — new learning curve, RAM limits, or
card requirements under a same-day deadline.

## D9 — App Runner deployment: Gradio over Streamlit (WebSocket incompatibility)

**Decision:** Deploy the Gradio interface (`app.py`) to AWS App Runner instead of the
Streamlit UI, despite Streamlit being the primary interface used for local development
and the Streamlit Community Cloud demo.

**Rationale:** The first App Runner deployment served the Streamlit app successfully at
the HTTP level (`curl` returned a healthy `200 OK` with full page HTML) but the page
never rendered live content in a browser. Diagnosis (DNS check, `curl -v`, browser
DevTools Console) isolated the failure to the WebSocket handshake
(`wss://.../_stcore/stream`) that Streamlit requires for live updates — rejected by
App Runner's reverse proxy (Envoy). This is a platform-level constraint, not an
application bug: the same Streamlit code runs correctly on Streamlit Community Cloud,
whose proxy layer handles the WebSocket upgrade differently.

Gradio's default (non-queued) mode uses plain HTTP request/response per interaction
rather than a persistent WebSocket, which sidesteps the incompatibility entirely and
was confirmed working with a live hybrid-route query on the App Runner URL.

**Rejected alternative:** Migrating to ECS Fargate + an Application Load Balancer,
which natively supports WebSocket. Rejected for this cycle because it would roughly
double the Terraform surface (VPC, subnets, ALB, target groups) for a same-day
deployment window; the Gradio interface was already built and tested (Phase 5a), so
switching it was a five-minute code change versus an hour of new infrastructure.
Documented here as the correct next step if Streamlit-on-App-Runner is required later.

## D10 — Reasoning effort `low` for gpt-oss-20b (provisional)

**Decision:** The primary model runs with `reasoning_effort=low` (config default,
`REASONING_EFFORT` in `.env` overrides; empty means provider default). The fallback
keeps its own default.

**Rationale:** The rule was written before measuring (`docs/STATUS_v3.md`, 1.4): pick the
lowest level with 10/10 routes, no SQL-route errors, and RAG/hybrid `grounded` count at
most one below `medium`. On the 10-question smoke set (not golden), cloud profile,
2026-11-20, no fallback calls in any run:

| effort | routes | SQL errors | grounded (RAG+hybrid) | output tokens | median latency |
|---|---|---|---|---|---|
| low | 10/10 | 0 | 2 | 1,994 | 3.2 s |
| medium | 10/10 | 0 | 2 | 5,524 | 5.2 s |
| high | 10/10 | 0 | 1 | 13,482 | 5.0 s |

Sources: `eval_results/smoke_2026-11-20_cloud_{low,medium,high}.json`. `low` meets the
rule and cuts output tokens about 2.8x versus `medium`, which matters because the Groq
free tier allows 8,000 tokens per minute (response headers). `high` returned one empty
RAG answer.

**Limits:** Ten questions cannot show a quality difference; "no SQL error" means the query
ran, not that the answer was right. The decision is re-checked in Faz 2 with a paired
comparison on the golden set. The local profile (Ollama) is measured on Kaggle.

**Rejected alternative:** Provider default (`medium`). Same checks passed, at roughly
three times the output tokens and slower RAG answers, which makes full eval runs hit
the per-minute token limit and fall back to another model.

## D11 — Eval v3 design (pre-registered before the first full run)

**Decision:** Golden set v2 (`eval/golden_v2.jsonl`, 75 questions: 18 sql, 17 rag,
12 analyst, 10 hybrid, 8 reject, 10 injection) runs end to end through the graph
(`eval/run_eval.py`), with the answer cache bypassed and the fallback off. Gemini Flash
judges rag, analyst and hybrid answers afterwards (`eval/judge.py`, written rubric, no
examples). `eval/report.py` aggregates three runs.

**Metrics, fixed before measuring:**
- Deterministic: route accuracy (all except injection), SQL execution accuracy (rows of the
  graph's own SQL result against the reference query), reject accuracy, injection defense
  (no system-prompt line, no key or secret value in the answer, database unchanged, plus
  per-item checks), hybrid evidence direction (did the review evidence come from a product
  moving in the asked direction), hybrid critic `grounded` rate.
- Judge: faithfulness = supported claims / claims (no claims = 1.0, relevance carries
  usefulness), relevance in {0, 0.5, 1}. For analyst this is faithfulness to the tool
  output, not analytic correctness (see B16).
- A wrong route scores as a failure on the route's own metric; system errors stay in.
- CI: mean per question over runs, then bootstrap over questions (B=10000, seed 0,
  percentile 95%). Small strata (8–18 questions) give wide intervals; they are reported, not hidden.
- Parity (local − cloud): paired per-question difference with the same bootstrap. Zero
  inside the interval means no difference detected, not equivalence.
- The report refuses mixed commits, a dirty tree, mixed models or any fallback answer.

**Leakage rules:** `tests/test_golden_set.py` fails when a golden question has Jaccard ≥ 0.5
with a demo example, a smoke question, a prompt line or another golden question. Removed from
v1: `rag_01` (identical to a demo example), `sql_05` (near copy of a demo example), `sql_12`
(ambiguous between sql and analyst). Reworded: `rag_09`, `rag_11`, `sql_16`.

**Rubric change before the first run:** a 7-question dry run showed the judge scoring the
hedged guess "reviewers likely praised better performance" as faithful. The rubric now counts
guesses and hedged statements as claims. This is a definition fix, not tuning on scores; the
judge is still uncalibrated until Faz 3.

**Rejected alternative:** Keep scoring components directly (old `run_eval.py`). It measured
the SQL agent, RAG agent and a copy of the router in isolation, not the system users get.
