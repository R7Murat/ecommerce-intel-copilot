"""OpenTelemetry spans for graph nodes, retrieval, tools and LLM calls.

Span names follow the GenAI semantic conventions: "<operation> <name>".
No prompt or answer text is recorded, only metadata.
"""
import contextlib
import functools
import os

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

OPERATIONS = {"invoke_agent", "retrieval", "chat", "execute_tool"}
_tracer = trace.get_tracer("copilot")
_configured = False


@contextlib.contextmanager
def span(operation: str, name: str):
    """Open a span "<operation> <name>"; an escaping exception marks it as error."""
    if operation not in OPERATIONS:
        raise ValueError(f"unknown operation {operation!r}")
    with _tracer.start_as_current_span(f"{operation} {name}") as sp:
        sp.set_attribute("gen_ai.operation.name", operation)
        key = "gen_ai.agent.name" if operation == "invoke_agent" else "copilot.step"
        sp.set_attribute(key, name)
        yield sp


def traced_node(operation: str, name: str):
    """Decorator form of span()."""
    if operation not in OPERATIONS:
        raise ValueError(f"unknown operation {operation!r}")

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with span(operation, name):
                return fn(*args, **kwargs)
        return wrapper
    return deco


def set_attrs(attrs: dict) -> None:
    """Set attributes on the current span, skipping None values."""
    sp = trace.get_current_span()
    for k, v in attrs.items():
        if v is not None:
            sp.set_attribute(k, v)


def mark_error(message: str) -> None:
    """Mark the current span as error for failures that are caught, not raised."""
    trace.get_current_span().set_status(Status(StatusCode.ERROR, message[:200]))


def setup_tracing() -> bool:
    """Export spans over OTLP/HTTP when OTEL_EXPORTER_OTLP_ENDPOINT is set; else no-op."""
    global _configured
    if _configured or not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return _configured
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "copilot"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True
    return True
