# Project Plan — E-Commerce Product Intelligence Copilot

A multi-agent Retrieval-Augmented Generation (RAG) system that answers natural-language
questions over Amazon product and review data by orchestrating specialized agents for
structured querying, semantic retrieval, and quantitative analysis.

This document is the single source of truth for scope, architecture, and delivery phases.
Any change to scope or architecture is made deliberately and recorded here with a version note.

---

## 1. Overview

| Field | Value |
|-------|-------|
| **Project** | E-Commerce Product Intelligence Copilot |
| **Goal** | An end-to-end, deployed multi-agent RAG system demonstrating agent orchestration, retrieval, and evaluation |
| **Core skills** | Multi-agent orchestration (LangGraph Supervisor), RAG, text-to-SQL, agent-level evaluation (trajectory), Infrastructure-as-Code, CI/CD |
| **Data** | Amazon Reviews 2023 (McAuley Lab, Hugging Face) — `Appliances` category |
| **Repository** | github.com/R7Murat/ecommerce-intel-copilot |
| **Deployment** | Docker image to (a) Hugging Face Spaces — persistent live demo, (b) AWS via Terraform — provisioned, validated, and torn down |
| **Language** | Code and repository in English |

### 1.1 Engineering Principles

1. **Plan, then build** — each phase opens against a defined spec and closes against explicit acceptance criteria.
2. **Walking skeleton first** — a thin end-to-end slice precedes heavy infrastructure.
3. **Quality gates** — "it runs" is not sufficient; a phase closes only when measurable thresholds are met.
4. **Scope discipline** — the agent set is capped at five. Additions are deferred to the backlog.
5. **Test-first for critical paths** — especially the SQL safety guard, tests precede implementation.
6. **Traceable changes** — every change maps to a phase spec; prior phases are not modified without cause.
7. **Documented decisions** — significant choices, and the alternatives rejected, are recorded in `docs/DECISIONS.md`.

### 1.2 Model & Cost Strategy

The application's agents call a hosted LLM through a single provider-abstraction layer
(`litellm`), configured via environment variables:

| Role | Provider | Notes |
|------|----------|-------|
| Primary agent LLM | Google Gemini Flash (free tier) | 1,500 requests/day |
| Fallback (rate limit) | Groq — Llama 3.3 70B (free tier) | Automatic failover on HTTP 429 |

Rate-limit handling uses exponential backoff with automatic fallback. A response cache
(question hash to answer) is active from Phase 1; evaluation runs bypass the cache.

---

## 2. Data Specification

### 2.1 Source
- Dataset: `McAuley-Lab/Amazon-Reviews-2023`; configs `raw_review_Appliances` and
  `raw_meta_Appliances`. Attribution to Hou et al., 2024 (arXiv:2403.03952) is required in the README.
- **Sizing decision:** the band `300 <= rating_number < 1000` yields roughly 5,006 products
  and 441,857 reviews — enough product diversity for structured queries and a rich review
  corpus for retrieval, while keeping local processing tractable.

### 2.2 SQLite Schema (`data/products.db`, read-only connection)
```sql
CREATE TABLE products (
    parent_asin    TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    store          TEXT,
    main_category  TEXT,
    price          REAL,
    average_rating REAL,
    rating_number  INTEGER,
    details_json   TEXT
);
CREATE TABLE reviews (
    review_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_asin    TEXT REFERENCES products(parent_asin),
    rating         REAL NOT NULL,
    title          TEXT,
    text           TEXT,
    helpful_vote   INTEGER,
    verified       INTEGER,
    ts             INTEGER
);
CREATE INDEX idx_reviews_asin ON reviews(parent_asin);
CREATE INDEX idx_reviews_ts   ON reviews(ts);
```

### 2.3 Retrieval Corpus
- Content: product description and features (one document per product), plus review text (chunked).
- Embeddings: local `sentence-transformers/all-MiniLM-L6-v2` (no API cost).
- Vector store: Chroma, persisted under `data/chroma/`; each chunk carries `parent_asin`
  and `source_type` metadata.

### 2.4 Data Limitations (recorded in the system card)
- `price` is a single crawl-time value, not a price history. Time-series analysis is derived
  from review and rating signals over time.
- The data ends in September 2023; the system does not reflect the current state of Amazon.

---

## 3. Agent Architecture (LangGraph — Supervisor Pattern)

The agent set is capped at five.

```
user -> SUPERVISOR -> { SQL ANALYST | KNOWLEDGE (RAG) | MARKET ANALYST } -> CRITIC -> answer
              ^                                                                | (retry, max 1)
              +----------------------------------------------------------------+
```

| Agent | Responsibility | Backing |
|-------|----------------|---------|
| Supervisor | Classify the question, order the relevant agents, synthesize the final answer | LLM |
| SQL Analyst | Text-to-SQL over a read-only connection, guarded to SELECT-only | LLM + SQLite |
| Knowledge (RAG) | Top-k retrieval from Chroma; answers strictly from context with sources | LLM + Chroma |
| Market Analyst | Deterministic Python analytics (rating trend, review volume, top movers) | Python (LLM only narrates results) |
| Critic / Verifier | Groundedness check; on ungrounded output, one retry, then falls back to "not answerable" | LLM |

**Graph state** (`AgentState`): `question`, `route_plan`, `sql_result`, `rag_result`,
`analyst_result`, `draft_answer`, `critic_verdict`, `retry_count` (<= 1), `final_answer`, `trace`.

**SQL safety guard (mandatory):** a SELECT-only allowlist, regex rejection of
`INSERT|UPDATE|DELETE|DROP|ALTER|PRAGMA|ATTACH`, a read-only connection URI
(`file:...?mode=ro`), and a 50-row result cap. This is the most safety-critical component
and is developed test-first.

---

## 4. Technology Stack

Python 3.11+ · LangGraph · litellm (Gemini / Groq) · Chroma · sentence-transformers ·
SQLite (read-only) · RAGAS and a custom evaluation harness · Langfuse (observability) ·
Streamlit · Docker · Terraform (AWS, local state) · GitHub Actions.

## 5. Repository Layout
```
ecommerce-intel-copilot/
├── PROJECT_PLAN.md · STATUS.md · README.md · .gitignore
├── docs/            DECISIONS.md, data_quality_report.md, architecture.md, aws-deployment.md
├── notebooks/       01_data_pipeline.ipynb
├── pyproject.toml · Dockerfile · .github/workflows/
├── src/copilot/     config.py, llm.py, data/, agents/, graph.py, tools/, ui/app.py
├── eval/            questions.jsonl, run_eval.py, thresholds.py
├── infra/terraform/ main.tf, ecr.tf, apprunner.tf, iam.tf, outputs.tf
└── tests/           SQL guard and agent unit tests
```

---

## 6. Delivery Phases

Each phase closes only when its acceptance criteria are met and recorded in `STATUS.md`,
followed by a commit.

### Phase 0 — Data Pipeline
Built in `notebooks/01_data_pipeline.ipynb`.
- Environment setup: virtual environment, `pyproject.toml`, core dependencies.
- Exploratory analysis on a streamed sample: null rates, rating distribution, date range.
- Type-integrity handling for the `ts` column (pandas nullable integers can serialize to
  SQLite as BLOB via numpy scalars; the pipeline coerces to native integers, verified by a regression test).
- Schema creation and ingestion functions (HF to SQLite).
- Full-set materialization of `data/products.db`.
- Retrieval corpus construction in Chroma.

**Acceptance:** `products.db` populated; a data-quality report in `docs/`; at least five
hand-written SQL queries returning correct results (recorded in `STATUS.md`); the sizing
decision recorded in `docs/DECISIONS.md`.

### Phase 1 — Walking Skeleton (Supervisor + SQL + RAG)
- LangGraph state and graph skeleton.
- SQL safety guard, developed test-first (destructive statements are rejected).
- SQL Analyst agent, first end-to-end query.
- Knowledge (RAG) agent with source attribution.
- Supervisor routing across question types, plus the response cache.

**Acceptance:** three evidence questions (SQL, RAG, and an out-of-scope rejection) answered
end-to-end with sources, recorded in `STATUS.md`.

### Phase 2 — Evaluation Harness
- A ~30-question set (SQL, RAG, and rejection/mixed) with expected routes and, for SQL,
  expected results. Evaluation content is never leaked into prompts or the index.
- SQL execution-accuracy harness.
- RAGAS integration (faithfulness, answer relevance).
- Trajectory-accuracy measurement (correct agent set selected).

**Acceptance (thresholds):** SQL execution accuracy >= 80%; faithfulness >= 0.80;
answer relevance >= 0.75; trajectory accuracy >= 85%; rejection questions 100% correct.
Scores recorded in `STATUS.md`.

### Phase 3 — Market Analyst + Critic
- Deterministic analytics tools with unit tests: rating trend, review volume,
  sentiment summary, top movers.
- Critic agent with a single-retry grounding loop.
- Supervisor hybrid routing for multi-step questions.

**Acceptance:** Phase 2 thresholds hold, and three multi-step evidence questions pass with
their traces recorded in `STATUS.md`.

### Phase 4 — Interface & Observability
- Streamlit interface (question to answer).
- Agent-path visualization, source list, and latency/token counters.
- Langfuse tracing across nodes.

**Acceptance:** the agent path renders correctly for three questions, and an end-to-end
Langfuse trace is captured.

### Phase 5a — Hugging Face Spaces Deployment
- Multi-stage Dockerfile; deployment to Spaces (Docker SDK); the API key stored in Secrets.

**Acceptance:** a live URL answers three evidence questions.

### Phase 5b — AWS Deployment (Terraform)
- Terraform for ECR, App Runner, least-privilege IAM, and CloudWatch; a manually triggered
  GitHub Actions workflow (build, push, apply, smoke test). State is local for this project.

**Acceptance:** `terraform apply` yields a working URL; evidence (screenshots and pipeline
logs) recorded in `docs/aws-deployment.md`; `terraform destroy` verified to leave no
residual resources. The provision–validate–destroy cycle is repeatable.

### Phase 6 — Documentation & Release
- README (architecture, live demo link, evaluation results, AWS deployment evidence,
  setup instructions, data attribution).
- System card (capabilities, limitations, data recency).
- Finalized `docs/DECISIONS.md` and an architecture diagram.

**Acceptance:** a newcomer can set the project up locally within ten minutes using the README.

---

## 7. Out of Scope
A sixth agent; additional tools beyond those specified; price-history analysis; live scraping;
Postgres/pgvector; Kubernetes/EKS; remote Terraform state; custom domains; authentication;
fine-tuning; and additional categories prior to Phase 6.

## 8. Prerequisites
- [x] Repository initialized; local clone; `GOOGLE_API_KEY` configured in `.env` (git-ignored)
- [ ] `GROQ_API_KEY` before Phase 1
- [ ] Langfuse account before Phase 4
- [ ] Hugging Face Space and token before Phase 5a
- [ ] AWS IAM (scoped policy) and repository secrets before Phase 5b

## 9. STATUS.md Format
```markdown
# STATUS — updated: <date>
Active phase: <N> | Completed: ...
## Acceptance Evidence
## Evaluation History | Date | Phase | SQL | Faithfulness | Relevance | Trajectory |
## Notes
## Backlog | Known Issues
```

---
*Version 1.0 — 6 July 2026.*
