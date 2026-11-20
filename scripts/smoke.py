"""Run the 10-question smoke set (not golden) and record route, latency, tokens and quota.

Usage: PYTHONPATH=src python scripts/smoke.py [low|medium|high|default]
Writes eval_results/smoke_<date>_<profile>_<effort>.json. The answer cache is bypassed and untouched.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

EFFORT = sys.argv[1] if len(sys.argv) > 1 else "default"
os.environ["REASONING_EFFORT"] = "" if EFFORT == "default" else EFFORT  # before copilot import

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

import copilot.graph as graph  # noqa: E402
import copilot.llm as llm  # noqa: E402
from copilot.config import PRIMARY_MODEL, PROFILE  # noqa: E402
from copilot.observability import setup_tracing  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [json.loads(line) for line in open(ROOT / "eval" / "smoke.jsonl", encoding="utf-8")]

# Collect spans locally as well as exporting them to Langfuse when configured.
exported = setup_tracing()
if not exported:
    trace.set_tracer_provider(TracerProvider())
collector = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(collector))

graph.cache.get = lambda q: None  # measure real calls, keep the demo cache clean
graph.cache.put = lambda q, a: None

# Keep the provider's rate-limit headers from the latest response (limits, not guesses).
quota = {}
_completion = llm.completion


def _capture(**kw):
    resp = _completion(**kw)
    headers = (getattr(resp, "_hidden_params", None) or {}).get("additional_headers") or {}
    quota.update({k.removeprefix("llm_provider-"): v for k, v in headers.items()
                  if "ratelimit" in k and not k.startswith("x-ratelimit")})
    return resp


llm.completion = _capture


def summarize(spans, result, item):
    chats = [s for s in spans if s.name.startswith("chat ")]
    root = next(s for s in spans if s.name == "invoke_agent copilot")
    a = lambda s, k: s.attributes.get(k) or 0  # noqa: E731
    route = next((t.get("route") for t in result.get("trace", []) if t.get("route")), None)
    return {
        "id": item["id"], "expected_route": item["expected_route"], "route": route,
        "route_ok": route == item["expected_route"],
        "latency_s": round((root.end_time - root.start_time) / 1e9, 2),
        "llm_calls": len(chats),
        "input_tokens": sum(a(s, "gen_ai.usage.input_tokens") for s in chats),
        "output_tokens": sum(a(s, "gen_ai.usage.output_tokens") for s in chats),
        "cost_usd_list_price": round(sum(a(s, "gen_ai.usage.cost") for s in chats), 6),
        "fallback_calls": sum(bool(s.attributes.get("copilot.fallback")) for s in chats),
        "error_spans": sum(s.status.status_code.name == "ERROR" for s in spans),
        "critic": (result.get("critic_verdict") or {}).get("verdict"),
        "tool_s": {s.name.split(" ", 1)[1]: round((s.end_time - s.start_time) / 1e9, 2)
                   for s in spans if s.name.startswith("execute_tool ")},
    }


def wait_for_tokens(min_tokens=6000):
    """Sleep until the per-minute token window resets, so the primary model is not
    pushed onto the fallback by our own pacing (fallback would mix models)."""
    if int(quota.get("x-ratelimit-remaining-tokens", min_tokens)) >= min_tokens:
        return
    m = re.fullmatch(r"(?:(\d+)m)?([\d.]+)s", quota.get("x-ratelimit-reset-tokens", "60s"))
    time.sleep((int(m[1] or 0) * 60 + float(m[2]) if m else 60) + 1)


rows = []
for item in QUESTIONS:
    wait_for_tokens()
    collector.clear()
    result = graph.run(graph.build_graph(), item["question"])
    rows.append(summarize(collector.get_finished_spans(), result, item))
    r = rows[-1]
    print(f"{r['id']:<11} {str(r['route']):<8} ok={r['route_ok']!s:<5} {r['latency_s']:>6}s "
          f"calls={r['llm_calls']} tok={r['input_tokens']}+{r['output_tokens']} "
          f"fb={r['fallback_calls']} err={r['error_spans']} critic={r['critic']}")

lat = sorted(r["latency_s"] for r in rows)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                        text=True, cwd=ROOT).stdout.strip()
out = {
    "kind": "smoke", "date": datetime.date.today().isoformat(), "commit": commit,
    "dirty_tree": bool(subprocess.run(["git", "status", "--porcelain", "src"],
                                      capture_output=True, text=True, cwd=ROOT).stdout),
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
    trace.get_tracer_provider().force_flush()
