# STATUS — updated: 2026-07-10

Active phase: 3 (Market Analyst + Critic) — pending gate approval | Completed: Phase 0, Phase 1, Phase 2

## Prerequisites
- [x] Repository initialized (clean history)
- [x] Local clone and `.env` (GOOGLE_API_KEY, GEMINI_API_KEY, GROQ_API_KEY configured)
- [ ] Langfuse account (before Phase 4)

## Acceptance Evidence — Phase 2
- Evaluation harness (`eval/run_eval.py`): SQL execution accuracy, trajectory accuracy,
  and custom LLM-as-judge faithfulness/relevance (RAGAS-style, zero extra dependencies).
- Scores: SQL 92% (11/12; the one FAIL analyzed as a false negative), trajectory 100%,
  faithfulness 1.00, relevance 0.91 — all thresholds met.
- Leakage rule enforced: eval questions never appear in prompts or the index; harness
  bypasses the answer cache by calling agents directly.

## Acceptance Evidence — Phase 1
- LangGraph skeleton: state, conditional routing (supervisor -> sql | rag | reject).
- SQL guard developed test-first: 11 tests green (destructive statements, multi-statement
  injection, case tricks rejected; row cap enforced).
- SQL Analyst: LLM-generated SQL matches hand-written Q1 exactly (Melitta 4.7 top result);
  guard on the mandatory path; one self-correction retry.
- Knowledge (RAG) agent: grounded answers with [asin] citations; honest-refusal rule in prompt.
- Three evidence questions pass end-to-end: sql route, rag route, reject route.
- Answer cache verified live (second run served from disk, zero LLM calls).
- LLM abstraction: primary + fallback, both verified live; silent-failure handling
  replaced with loud stderr logging.

## Acceptance Evidence — Phase 0
- `data/products.db`: 5,006 products / 441,857 reviews; all `ts` values stored as
  INTEGER (type-integrity fix verified); rating_number band (300, 999); dates 2003–2023.
- Chroma corpus: 5,006 product docs + 386,053 review docs (>= 20 chars),
  local embeddings (all-MiniLM-L6-v2), semantic search verified.
- Type-integrity issue (pandas nullable Int64 -> SQLite BLOB) reproduced, diagnosed,
  and fixed in `notebooks/01_data_pipeline.ipynb`.
- Five hand-written SQL queries with verified results (notebook, "Gate evidence" section).
- Data quality report: pending (carried to backlog) — core findings documented
  in notebook EDA sections.
- `docs/DECISIONS.md`: D1–D4 recorded.

## Evaluation History
| Date | Phase | SQL | Faithfulness | Relevance | Trajectory |
|------|-------|-----|--------------|-----------|------------|
| 2026-07-10 | 2 | 92% | 1.00 | 0.91 | 100% |

## Notes
- Full-corpus embedding completed in 92.7 min, single uninterrupted run (resumable design).
- sql_09 FAIL analyzed: LLM returned parent_asin instead of title for "which product" —
  semantically correct (same product, same count 1434); kept as FAIL rather than loosening
  the matcher (strict matching prevents masking real errors).
- Gemini 2.5 Flash free tier measured at 20 requests/day (5/min) — far below planning
  assumptions. Primary/fallback swapped: Groq (1,000/day) now primary. The litellm
  abstraction made this a two-line change.
- rag_03/rag_10 replaced: original questions were unanswerable from the corpus; the agent
  honestly refused and judges scored 0 — a measurement-point flaw, not an agent flaw.
- Judge parser bug caught live: faithfulness scored 6.0 (regex mis-pairing on a chatty
  judge response). Fixed with JSON-first parsing + 0-1 clamping. Eval instruments need
  testing too.

## Backlog
- Standalone `docs/data_quality_report.md` (findings currently live in the notebook).
- Improve `[llm]` failure log to name the failing model.
- Add "honest refusal" eval category: questions whose answers are absent from the corpus,
  scored PASS when the agent declines instead of hallucinating (rag_03/rag_10 incident).
- Unify ROUTER_PROMPT (currently duplicated in graph.py and run_eval.py) into config.

## Known Issues
(none)