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