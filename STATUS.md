# STATUS — updated: 2026-07-11

Active phase: — (all planned phases complete) | Completed: Phase 0–6 (5b deferred)

## Acceptance Evidence — Phase 5a (Deployment)
- Live demo on Streamlit Community Cloud:
  https://ecommerce-intel-copilot-u3hzffazrtbv4ayzfqhzet.streamlit.app/
- Data served from a companion HF dataset repo (R7Murat/ecommerce-intel-data, ~2 GB),
  downloaded on first boot — keeps the app repo under platform storage limits.
- Hybrid chain verified live: supervisor(hybrid) -> market_analyst -> knowledge ->
  critic(grounded) -> supervisor(synthesize), with sources and latency shown in the UI.
- Platform pivot recorded as D8 (HF Spaces free tier removed Gradio/CPU options mid-project).

## Acceptance Evidence — Phase 6 (Documentation)
- README with architecture, evaluation table, safety properties, data attribution, quickstart.
- SYSTEM_CARD.md: capabilities, limitations, honesty behavior, provenance, development notes.
- docs/DECISIONS.md D1–D8 complete; AWS deployment plan prepared (kept as an offline working document)

## Acceptance Evidence — Phase 4 (UI)
- Streamlit UI with agent-path trace panel, latency metric, critic verdict, example prompts.
- Cache route verified in UI (0.0s answer served from disk).

## Acceptance Evidence — Phase 3
- Deterministic analytics tools (4 unit tests on a hand-computed fixture).
- Critic agent: fail-safe parsing, 4 tests (2 live-LLM, marked).
- Graph finalized: analyst + hybrid routes; critic retry loop (max 1).
- Phase 2 thresholds re-verified after wiring: SQL 92%, trajectory 100%, faith 1.00, rel 0.87.

## Acceptance Evidence — Phase 2
- Eval harness: SQL execution accuracy, trajectory accuracy, custom LLM-as-judge
  faithfulness/relevance. Leakage rule enforced; cache bypassed.
- Scores: SQL 92% (one analyzed false negative), trajectory 100%, faith 1.00, rel 0.91.

## Acceptance Evidence — Phase 1
- LangGraph skeleton; SQL guard test-first (11 tests); SQL Analyst matches hand-written
  Q1 exactly; RAG agent with [asin] citations; answer cache verified live.

## Acceptance Evidence — Phase 0
- data/products.db: 5,006 products / 441,857 reviews; type-integrity (Int64->BLOB) bug
  reproduced and fixed with regression coverage; Chroma corpus (386,053 docs) built;
  five hand-written gate queries verified.

## Evaluation History
| Date | Phase | SQL | Faithfulness | Relevance | Trajectory |
|------|-------|-----|--------------|-----------|------------|
| 2026-07-10 | 2 | 92% | 1.00 | 0.91 | 100% |
| 2026-07-11 | 3 | 92% | 1.00 | 0.87 | 100% |

## Notes
- Full-corpus embedding: 92.7 min, single run (resumable design).
- Gemini free tier measured at 20 req/day -> Groq made primary (two-line change via litellm).
- Judge parser bug (score 6.0) caught live -> JSON-first parsing + clamping.
- HF Spaces free tier removed Gradio/CPU-basic mid-project (forum-confirmed rollout);
  pivoted to Streamlit Community Cloud in ~40 minutes thanks to the existing Streamlit UI.

## Backlog
- Execute the AWS provision-validate-destroy plan (offline document)
- Standalone docs/data_quality_report.md (findings live in the notebook).
- Honest-refusal eval category; unify ROUTER_PROMPT into config; Langfuse tracing;
  name failing model in [llm] logs; GitHub Actions workflow for AWS deploy.

## Known Issues
(none)
