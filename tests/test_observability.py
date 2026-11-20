"""Span names, parent-child links, error status and model attribution (B5)."""
from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

import copilot.agents.knowledge as knowledge
import copilot.graph as graph
import copilot.llm as llm
from copilot.observability import langfuse_exporter_args, mark_error, span, traced_node

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)  # global, set once per process


@pytest.fixture(autouse=True)
def clear_spans():
    EXPORTER.clear()
    yield


def fake_resp(content, model="groq/openai/gpt-oss-20b", cost=6.9e-06):
    return SimpleNamespace(
        model=model,
        _hidden_params={"response_cost": cost},
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


def by_name():
    return {s.name: s for s in EXPORTER.get_finished_spans()}


def test_span_name_and_operation():
    @traced_node("invoke_agent", "supervisor")
    def f():
        return 1

    assert f() == 1
    s = by_name()["invoke_agent supervisor"]
    assert s.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert s.attributes["gen_ai.agent.name"] == "supervisor"


def test_unknown_operation_refused():
    with pytest.raises(ValueError):
        traced_node("invoke", "x")


def test_chat_span_is_child_and_has_usage(monkeypatch):
    monkeypatch.setattr(llm, "completion", lambda **kw: fake_resp("ok"))

    @traced_node("invoke_agent", "knowledge")
    def agent():
        return llm.ask_llm("s", "u")

    assert agent() == "ok"
    spans = by_name()
    chat = spans[f"chat {llm.PRIMARY_MODEL}"]
    assert chat.parent.span_id == spans["invoke_agent knowledge"].context.span_id
    assert chat.attributes["gen_ai.response.model"] == "groq/openai/gpt-oss-20b"
    assert chat.attributes["gen_ai.usage.input_tokens"] == 11
    assert chat.attributes["gen_ai.usage.output_tokens"] == 7
    assert chat.attributes["copilot.fallback"] is False
    assert chat.attributes["copilot.cost_usd_list_price"] == pytest.approx(6.9e-06)
    assert chat.attributes["gen_ai.usage.cost"] == pytest.approx(6.9e-06)


def test_unpriced_model_omits_cost(monkeypatch):
    monkeypatch.setattr(llm, "completion", lambda **kw: fake_resp("ok", cost=None))
    llm.ask_llm("s", "u")
    assert "copilot.cost_usd_list_price" not in by_name()[f"chat {llm.PRIMARY_MODEL}"].attributes


def test_raised_error_marks_span_and_propagates():
    @traced_node("execute_tool", "sql_query")
    def boom():
        raise RuntimeError("db locked")

    with pytest.raises(RuntimeError):
        boom()
    assert by_name()["execute_tool sql_query"].status.status_code == StatusCode.ERROR


def test_caught_error_can_be_marked():
    with span("retrieval", "reviews_full"):
        mark_error("collection missing")
    assert by_name()["retrieval reviews_full"].status.status_code == StatusCode.ERROR


def test_fallback_is_visible(monkeypatch):
    if not llm.FALLBACK_MODEL:
        pytest.skip("profile has no fallback")

    def fake(model, **kw):
        if model == llm.PRIMARY_MODEL:
            raise ConnectionError("primary down")
        return fake_resp("from fallback", model=model)

    monkeypatch.setattr(llm, "completion", fake)
    assert llm.ask_llm("s", "u") == "from fallback"
    spans = by_name()
    primary, fallback = spans[f"chat {llm.PRIMARY_MODEL}"], spans[f"chat {llm.FALLBACK_MODEL}"]
    assert primary.status.status_code == StatusCode.ERROR
    assert primary.attributes["copilot.fallback"] is False
    assert fallback.attributes["copilot.fallback"] is True
    assert fallback.attributes["gen_ai.response.model"] == llm.FALLBACK_MODEL


def test_hybrid_question_forms_one_tree(monkeypatch):
    """Faz 1 gate shape: copilot -> supervisor, hybrid -> retrieval, critic -> chat."""
    def fake(model, messages, **kw):
        system = messages[0]["content"]
        if system.startswith("Classify"):
            return fake_resp("hybrid")
        if "strict verifier" in system:
            return fake_resp('{"verdict": "grounded", "issues": []}')
        return fake_resp("answer [B0001]")

    class FakeColl:
        def query(self, **kw):
            return {"documents": [["great fridge"]], "metadatas": [[{"parent_asin": "B0001"}]]}

    monkeypatch.setattr(llm, "completion", fake)
    monkeypatch.setattr(graph.cache, "get", lambda q: None)
    monkeypatch.setattr(graph.cache, "put", lambda q, a: None)
    monkeypatch.setattr(graph.sqlite3, "connect", lambda *a, **k: None)
    monkeypatch.setattr(graph.analytics, "top_movers", lambda conn, n: [("B0001", 4.5, 3.0, -1.5)])
    monkeypatch.setattr(graph.analytics, "rating_trend", lambda conn, asin: [(2020, 4.5)])
    monkeypatch.setattr(knowledge._client, "get_collection", lambda *a, **k: FakeColl())

    result = graph.run(graph.build_graph(), "which product declined most and why")
    assert "Sources: B0001" in result["final_answer"]

    spans = EXPORTER.get_finished_spans()
    ids = {s.context.span_id: s.name for s in spans}
    parent_of = {s.name: ids.get(s.parent.span_id) if s.parent else None for s in spans}
    assert parent_of["invoke_agent copilot"] is None
    assert parent_of["invoke_agent supervisor"] == "invoke_agent copilot"
    assert parent_of["invoke_agent hybrid"] == "invoke_agent copilot"
    assert parent_of["retrieval reviews_full"] == "invoke_agent hybrid"
    assert parent_of["invoke_agent critic"] == "invoke_agent hybrid"
    critic = next(s for s in spans if s.name == "invoke_agent critic")
    assert critic.attributes["copilot.critic.verdict"] == "grounded"
    chats = [s for s in spans if s.name.startswith("chat ")]
    assert len(chats) == 4  # router, knowledge answer, critic, synthesis
    assert {ids[s.parent.span_id] for s in chats} == {
        "invoke_agent supervisor", "invoke_agent hybrid", "invoke_agent critic"}


def test_langfuse_exporter_args():
    env = {"LANGFUSE_HOST": "http://localhost:3000/", "LANGFUSE_PUBLIC_KEY": "pk-lf-a",
           "LANGFUSE_SECRET_KEY": "sk-lf-b"}
    args = langfuse_exporter_args(env)
    assert args["endpoint"] == "http://localhost:3000/api/public/otel/v1/traces"
    assert args["headers"]["Authorization"] == "Basic cGstbGYtYTpzay1sZi1i"  # pk-lf-a:sk-lf-b
    assert langfuse_exporter_args({**env, "LANGFUSE_SECRET_KEY": ""}) is None


def test_analytics_calls_are_traced():
    """B12: deterministic analytics show up as execute_tool spans under their caller."""
    import sqlite3
    from copilot.tools import analytics

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE reviews (parent_asin TEXT, rating REAL, ts INTEGER)")
    conn.executemany("INSERT INTO reviews VALUES (?,?,?)",
                     [("A1", 5.0, 1609459200), ("A1", 3.0, 1641038400)])

    @traced_node("invoke_agent", "hybrid")
    def agent():
        return analytics.top_movers(conn, n=1), analytics.rating_trend(conn, "A1")

    assert agent()[0] == [("A1", 5.0, 3.0, -2.0)]
    spans = by_name()
    for name in ("execute_tool top_movers", "execute_tool rating_trend"):
        assert spans[name].parent.span_id == spans["invoke_agent hybrid"].context.span_id


def test_reasoning_effort_only_on_primary(monkeypatch):
    seen = {}

    def fake(model, **kw):
        seen[model] = kw.get("reasoning_effort")
        if model == llm.PRIMARY_MODEL:
            raise ConnectionError("primary down")
        return fake_resp("ok", model=model)

    monkeypatch.setattr(llm, "REASONING_EFFORT", "low")
    monkeypatch.setattr(llm, "FALLBACK_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setattr(llm, "completion", fake)
    llm.ask_llm("s", "u")
    assert seen == {llm.PRIMARY_MODEL: "low", "gemini/gemini-2.5-flash": None}
    assert by_name()[f"chat {llm.PRIMARY_MODEL}"].attributes["copilot.reasoning_effort"] == "low"


def test_otlp_file_exporter_roundtrip(tmp_path):
    """Kaggle path: spans written to a file decode back to the same OTLP spans."""
    import base64
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    from copilot.observability import OtlpFileExporter

    with span("invoke_agent", "copilot"):
        pass
    path = tmp_path / "traces.otlp"
    OtlpFileExporter(str(path)).export(EXPORTER.get_finished_spans())
    req = ExportTraceServiceRequest.FromString(base64.b64decode(path.read_text().strip()))
    names = [s.name for rs in req.resource_spans for ss in rs.scope_spans for s in ss.spans]
    assert names == ["invoke_agent copilot"]
