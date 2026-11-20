"""Send one question through the graph and flush its trace (Faz 1 gate check).

Usage: PYTHONPATH=src python scripts/trace_demo.py ["question"]
The default question is not in the golden or calibration sets.
"""
import sys

from opentelemetry import trace

from copilot.graph import build_graph, run
from copilot.observability import setup_tracing

QUESTION = "Which dryer lost the most rating over time, and what do reviews blame?"

if __name__ == "__main__":
    if not setup_tracing():
        raise SystemExit("tracing not configured: set LANGFUSE_* in .env")
    result = run(build_graph(), sys.argv[1] if len(sys.argv) > 1 else QUESTION)
    print("route:", [s.get("route") for s in result.get("trace", []) if s.get("route")])
    print("critic:", (result.get("critic_verdict") or {}).get("verdict"))
    trace.get_tracer_provider().force_flush()
