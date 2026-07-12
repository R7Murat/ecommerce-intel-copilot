# System Card — E-Commerce Product Intelligence Copilot

## What the system does
Answers natural-language questions about Amazon appliance products and their reviews:
statistics (counts, averages, rankings), review-based insights (complaints, experiences),
temporal trends (rating changes, review volume), and combined questions ("which product
declined most and why").

## What it does not do
- No current data: the corpus ends **September 2023**; the system cannot describe the
  present state of Amazon or any product.
- No price history: `price` is a single crawl-time value; time-series analysis uses
  review/rating signals instead.
- No out-of-domain answers: questions unrelated to the dataset are rejected by design.
- Coverage limits: the corpus is one category (Appliances), filtered to products with
  300–999 ratings; ~12.6% of reviews (under 20 characters) are excluded from retrieval.

## Honesty behavior
When retrieval cannot support an answer, the system says so ("The data does not contain
this information") rather than guessing. A critic agent verifies claims against sources
before answers reach the user; unverifiable claims trigger one retry, then a hedged
response.

## Known limitations
- LLM-as-judge metrics share the weaknesses of the judging model; faithfulness of 1.00
  was measured on a 12-question RAG subset and should be read in that context.
- The router and judges depend on free-tier LLM providers; rate limits can add latency
  (an automatic provider fallback is in place).
- Terraform state for the AWS deployment plan is local (single-developer project);
  production would use a remote backend.

## Data provenance & privacy
Public dataset (Amazon Reviews 2023, McAuley Lab; Hou et al., 2024, arXiv:2403.03952).
Free-tier LLM providers may use submitted content for training; all content sent is
already public. No user accounts or personal data are collected by the demo.

## Development notes
Architecture, evaluation design, data decisions, and quality gates were human-led;
implementation was AI-assisted. Every significant decision, including rejected
alternatives, is recorded in docs/DECISIONS.md; phase-by-phase acceptance evidence
lives in STATUS.md.
