# STATUS — updated: 2026-07-15

Active phase: — (all planned phases complete) | Completed: Phase 0–6, 5b

## Acceptance Evidence — Phase 5b (AWS Deployment)
- Full provision-validate-destroy cycle executed on AWS (ECR + App Runner, eu-central-1)
  per docs/AWS_DEPLOYMENT_PLAN.md (kept as an offline working document).
- Live query verified on the AWS URL: hybrid route (supervisor -> market_analyst ->
  knowledge -> critic(grounded) -> supervisor(synthesize)), sourced answer, 9.5s latency.
- WebSocket incompatibility diagnosed and fixed: App Runner's proxy rejected Streamlit's
  WebSocket upgrade; redeployed with the existing Gradio interface (D9). Not an
  application bug — platform-level constraint, confirmed via curl + browser DevTools.
- All resources destroyed and verified absent (App Runner, ECR, IAM role) — cost stayed
  within the planned <$1 budget.
- Full evidence: docs/aws-deployment.md (7 screenshots).

## Acceptance Evidence — Phase 5a (Deployment)
- Live demo on Streamlit Community Cloud:
  https://ecommerce-intel-copilot-u3hzffazrtbv4ayzfqhzet.streamlit.app/
- Data served from a companion HF dataset repo (R7Murat/ecommerce-intel-data, ~2 GB),
  downloaded on first boot.
- Hybrid chain verified live in the UI with sources and latency shown.
- Platform pivot recorded as D8 (HF Spaces free tier removed Gradio/CPU options mid-project).

## Acceptance Evidence — Phase 6 (Documentation)
- README with architecture, evaluation table, safety properties, data attribution, quickstart.
- SYSTEM_CARD.md: capabilities, limitations, honesty behavior, provenance, development notes.
- docs/DECISIONS.md D1-D9 complete; docs/AWS_DEPLOYMENT_PLAN.md and docs/aws-deployment.md
  document the full AWS cycle.

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
- HF Spaces free tier removed Gradio/CPU-basic mid-project; pivoted to Streamlit
  Community Cloud in ~40 minutes thanks to the existing Streamlit UI.
- AWS App Runner rejected Streamlit's WebSocket; pivoted to the existing Gradio interface
  in ~15 minutes (build+push+redeploy) thanks to having both UIs already built.

## Backlog
- Standalone docs/data_quality_report.md (findings live in the notebook).
- Honest-refusal eval category; unify ROUTER_PROMPT into config; Langfuse tracing;
  name failing model in [llm] logs; GitHub Actions workflow for AWS deploy;
  ECS Fargate + ALB migration if Streamlit-on-AWS is required later (see D9).

## Known Issues
(none)
