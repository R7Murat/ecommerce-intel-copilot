"""Shared eval plumbing: span collection, provider quota pacing, per-question span summary."""
import re
import subprocess
import time
from pathlib import Path

import litellm
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from copilot.observability import setup_tracing

ROOT = Path(__file__).resolve().parents[1]
quota: dict = {}            # latest provider rate-limit headers (limits, not guesses)
state = {"daily_exhausted": False}


def collect_spans() -> tuple[InMemorySpanExporter, bool]:
    """Keep spans in memory, and still export them when tracing is configured."""
    exported = setup_tracing()
    if not exported:
        trace.set_tracer_provider(TracerProvider())
    collector = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(collector))
    return collector, exported


def _reset_seconds(default: float = 60) -> float:
    m = re.fullmatch(r"(?:(\d+)m)?([\d.]+)s", quota.get("x-ratelimit-reset-tokens", ""))
    return (int(m[1] or 0) * 60 + float(m[2]) if m else default) + 1


def install_quota_guard(llm_module, retries: int = 5) -> None:
    """Wrap llm.completion: record rate-limit headers, wait out per-minute limits, and
    flag (not hide) a daily limit. Agents swallow exceptions, so callers check the flag."""
    inner = llm_module.completion

    def wrapped(**kw):
        for attempt in range(retries + 1):
            try:
                resp = inner(**kw)
            except litellm.RateLimitError as e:
                if "per day" in str(e).lower() or attempt == retries:
                    state["daily_exhausted"] = "per day" in str(e).lower()
                    raise
                time.sleep(_reset_seconds())
                continue
            headers = (getattr(resp, "_hidden_params", None) or {}).get("additional_headers") or {}
            quota.update({k.removeprefix("llm_provider-"): v for k, v in headers.items()
                          if "ratelimit" in k and not k.startswith("x-ratelimit")})
            return resp

    llm_module.completion = wrapped


def wait_for_tokens(min_tokens: int = 6000) -> None:
    """Sleep until the per-minute token window resets when too little is left."""
    if int(quota.get("x-ratelimit-remaining-tokens", min_tokens)) < min_tokens:
        time.sleep(_reset_seconds())


def span_ops(spans) -> dict:
    """Latency, LLM calls, tokens, cost, fallback and error counts for one question."""
    chats = [s for s in spans if s.name.startswith("chat ")]
    root = next(s for s in spans if s.name == "invoke_agent copilot")
    a = lambda s, k: s.attributes.get(k) or 0  # noqa: E731
    return {
        "latency_s": round((root.end_time - root.start_time) / 1e9, 2),
        "llm_calls": len(chats),
        "input_tokens": sum(a(s, "gen_ai.usage.input_tokens") for s in chats),
        "output_tokens": sum(a(s, "gen_ai.usage.output_tokens") for s in chats),
        "cost_usd_list_price": round(sum(a(s, "gen_ai.usage.cost") for s in chats), 6),
        "fallback_calls": sum(bool(s.attributes.get("copilot.fallback")) for s in chats),
        "error_spans": sum(s.status.status_code.name == "ERROR" for s in spans),
        "tool_s": {s.name.split(" ", 1)[1]: round((s.end_time - s.start_time) / 1e9, 2)
                   for s in spans if s.name.startswith("execute_tool ")},
    }


def git_state() -> dict:
    run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True,  # noqa: E731
                                    cwd=ROOT).stdout.strip()
    return {"commit": run("rev-parse", "--short", "HEAD"),
            "dirty_tree": bool(run("status", "--porcelain", "src", "eval"))}
