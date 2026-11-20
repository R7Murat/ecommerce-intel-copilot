"""OpenTelemetry spans for graph nodes, retrieval, tools and LLM calls.

Span names follow the GenAI semantic conventions: "<operation> <name>".
No prompt or answer text is recorded, only metadata.
"""
import base64
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


def langfuse_exporter_args(env=os.environ) -> dict | None:
    """OTLP endpoint and Basic auth header for Langfuse; None unless all three vars are set."""
    host, pk, sk = (env.get(k) for k in
                    ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"))
    if not (host and pk and sk):
        return None
    token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    return {"endpoint": f"{host.rstrip('/')}/api/public/otel/v1/traces",
            "headers": {"Authorization": f"Basic {token}"}}


class OtlpFileExporter:
    """Append each span batch as one base64 OTLP protobuf line, for hosts that cannot
    reach Langfuse (Kaggle); scripts/replay_traces.py sends the file later."""

    def __init__(self, path: str):
        self.path = path

    def export(self, spans):
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
        from opentelemetry.sdk.trace.export import SpanExportResult
        with open(self.path, "a", encoding="ascii") as f:
            f.write(base64.b64encode(encode_spans(spans).SerializeToString()).decode() + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def setup_tracing() -> bool:
    """Export spans to COPILOT_TRACES_FILE, else over OTLP/HTTP to Langfuse (LANGFUSE_*
    vars) or the standard OTEL_EXPORTER_OTLP_* target; no-op when none is configured."""
    global _configured
    lf = langfuse_exporter_args()
    file_path = os.getenv("COPILOT_TRACES_FILE")
    if _configured or not (file_path or lf or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")):
        return _configured
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "copilot"}))
    exporter = OtlpFileExporter(file_path) if file_path else OTLPSpanExporter(**(lf or {}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    return True
