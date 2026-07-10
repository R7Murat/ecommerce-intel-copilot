| 2026-07-10 | 2 | 92% | — | — | 100% |

- sql_09 FAIL analyzed: LLM returned parent_asin instead of title for "which product" —
  semantically correct (same product, same count 1434); kept as FAIL rather than loosening
  the matcher (strict matching prevents masking real errors).
- Gemini 2.5 Flash free tier measured at 20 requests/day (5/min) — far below planning
  assumptions. Primary/fallback swapped: Groq (1,000/day) now primary. The litellm
  abstraction made this a two-line change.

# STATUS — updated: 2026-07-10

Active phase: 2 (Evaluation Harness) — pending gate approval | Completed: Phase 0, Phase 1

## Prerequisites
- [x] Repository initialized (clean history)
- [x] Local clone and `.env` (GOOGLE_API_KEY, GEMINI_API_KEY, GROQ_API_KEY configured)
- [ ] Langfuse account (before Phase 4)

## Acceptance Evidence — Phase 1
- LangGraph skeleton: state, conditional routing (supervisor -> sql | rag | reject).
- SQL guard developed test-first: 11 tests green (destructive statements, multi-statement
  injection, case tricks rejected; row cap enforced).
- SQL Analyst: LLM-generated SQL matches hand-written Q1 exactly (Melitta 4.7 top result);
  guard on the mandatory path; one self-correction retry.
- Knowledge (RAG) agent: grounded answers with [asin] citations; honest-refusal rule in prompt.
- Three evidence questions pass end-to-end: sql route, rag route, reject route.
- Answer cache verified live (second run served from disk, zero LLM calls).
- LLM abstraction: primary (Gemini 2.5 Flash) + fallback (Groq Llama 3.3 70B), both
  verified live; silent-failure handling replaced with loud stderr logging.

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

## Notes
- Full-corpus embedding completed in 92.7 min, single uninterrupted run (resumable design).

## Backlog
- Standalone `docs/data_quality_report.md` (findings currently live in the notebook).
- Improve `[llm]` failure log to name the failing model (currently says "primary" even
  when an explicitly passed model fails).

## Known Issues
(none)