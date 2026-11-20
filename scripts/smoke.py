"""Run the 10-question smoke set (not golden) and record route, latency, tokens and quota.

Usage: PYTHONPATH=src python scripts/smoke.py [low|medium|high|default]
Writes eval_results/smoke_<date>_<profile>_<effort>.json. The answer cache is bypassed and untouched.
"""
import datetime
import json
import os
import sys
from pathlib import Path

EFFORT = sys.argv[1] if len(sys.argv) > 1 else "default"
os.environ["REASONING_EFFORT"] = "" if EFFORT == "default" else EFFORT  # before copilot import

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import harness  # noqa: E402
import copilot.graph as graph  # noqa: E402
import copilot.llm as llm  # noqa: E402
from copilot.config import PRIMARY_MODEL, PROFILE  # noqa: E402

ROOT = harness.ROOT
QUESTIONS = [json.loads(line) for line in open(ROOT / "eval" / "smoke.jsonl", encoding="utf-8")]

collector, exported = harness.collect_spans()
harness.install_quota_guard(llm)
quota = harness.quota
graph.cache.get = lambda q: None  # measure real calls, keep the demo cache clean
graph.cache.put = lambda q, a: None


def summarize(spans, result, item):
    route = next((t.get("route") for t in result.get("trace", []) if t.get("route")), None)
    return {"id": item["id"], "expected_route": item["expected_route"], "route": route,
            "route_ok": route == item["expected_route"], **harness.span_ops(spans),
            "critic": (result.get("critic_verdict") or {}).get("verdict")}


rows = []
for item in QUESTIONS:
    harness.wait_for_tokens()
    collector.clear()
    result = graph.run(graph.build_graph(), item["question"])
    rows.append(summarize(collector.get_finished_spans(), result, item))
    r = rows[-1]
    print(f"{r['id']:<11} {str(r['route']):<8} ok={r['route_ok']!s:<5} {r['latency_s']:>6}s "
          f"calls={r['llm_calls']} tok={r['input_tokens']}+{r['output_tokens']} "
          f"fb={r['fallback_calls']} err={r['error_spans']} critic={r['critic']}")

lat = sorted(r["latency_s"] for r in rows)
out = {
    "kind": "smoke", "date": datetime.date.today().isoformat(), **harness.git_state(),
    "profile": PROFILE, "primary_model": PRIMARY_MODEL, "reasoning_effort": EFFORT,
    "n": len(rows), "note": "10 questions: a quota and sanity check, not a quality estimate",
    "totals": {
        "route_ok": sum(r["route_ok"] for r in rows),
        "llm_calls": sum(r["llm_calls"] for r in rows),
        "input_tokens": sum(r["input_tokens"] for r in rows),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "fallback_calls": sum(r["fallback_calls"] for r in rows),
        "error_spans": sum(r["error_spans"] for r in rows),
        "latency_median_s": lat[len(lat) // 2], "latency_max_s": lat[-1],
    },
    "provider_ratelimit_after_run": quota,
    "rows": rows,
}
path = ROOT / "eval_results" / f"smoke_{out['date']}_{PROFILE}_{EFFORT}.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out["totals"]), "\nquota:", quota, "\n->", path.relative_to(ROOT))
if exported:
    harness.trace.get_tracer_provider().force_flush()
