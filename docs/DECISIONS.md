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