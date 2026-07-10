"""Graph wiring: supervisor -> {sql | rag | analyst | hybrid} -> critic gate -> answer."""
import sqlite3

from langgraph.graph import StateGraph, START, END

from copilot.agents.critic import run_critic
from copilot.agents.knowledge import run_knowledge
from copilot.agents.sql_analyst import run_sql_analyst
from copilot.config import DB_URI
from copilot.llm import ask_llm
from copilot.state import AgentState
from copilot.tools import analytics, cache

ROUTER_PROMPT = """Classify the user's question into exactly one word:
- sql: answerable by querying product/review statistics (counts, averages, rankings, prices)
- rag: requires reading review/product texts (opinions, complaints, experiences)
- analyst: asks about trends, changes over time, or biggest movers (rating trend, review volume)
- hybrid: needs BOTH a trend/statistic AND reading reviews to explain it (e.g. "which product declined most and why")
- reject: not about home-appliance products or their reviews at all
Answer with one word only: sql, rag, analyst, hybrid, or reject."""

SYNTH_PROMPT = "Turn this data into a concise, readable answer. Round numbers sensibly. Cite [asin] sources when present."


def supervisor_node(state: AgentState) -> dict:
    q = state["question"]
    cached = cache.get(q)
    if cached:
        return {"route_plan": ["cache"], "final_answer": cached,
                "trace": [{"agent": "supervisor", "route": "cache"}]}
    route = ask_llm(ROUTER_PROMPT, q).strip().lower()
    if route not in {"sql", "rag", "analyst", "hybrid", "reject"}:
        route = "rag"
    return {"route_plan": [route], "retry_count": 0,
            "trace": [{"agent": "supervisor", "route": route}]}


def sql_node(state: AgentState) -> dict:
    r = run_sql_analyst(state["question"])
    if r["error"]:
        answer = f"I could not answer this via SQL: {r['error']}"
    else:
        answer = ask_llm(SYNTH_PROMPT,
                         f"Question: {state['question']}\nSQL: {r['query']}\nRows: {r['rows']}")
    cache.put(state["question"], answer)
    return {"sql_result": r, "final_answer": answer,
            "trace": state["trace"] + [{"agent": "sql_analyst"}]}


def analyst_node(state: AgentState) -> dict:
    """Deterministic analytics; the LLM only narrates the numbers."""
    conn = sqlite3.connect(DB_URI, uri=True)
    movers = analytics.top_movers(conn, n=5)
    volume = analytics.review_volume(conn)
    data = f"Top movers (asin, first-year avg, last-year avg, change): {movers}\n" \
           f"Review volume by year: {volume}"
    answer = ask_llm(SYNTH_PROMPT, f"Question: {state['question']}\n{data}")
    cache.put(state["question"], answer)
    return {"analyst_result": {"movers": movers, "volume": volume},
            "final_answer": answer,
            "trace": state["trace"] + [{"agent": "market_analyst"}]}


def rag_node(state: AgentState) -> dict:
    """RAG with a critic gate: ungrounded answers get ONE retry, then honest fallback."""
    q = state["question"]
    retry = state.get("retry_count", 0)
    hint = "" if retry == 0 else " Answer strictly from the context; remove any unsupported claim."
    r = run_knowledge(q + hint)
    if r["error"] or not r["answer"]:
        answer = f"Retrieval failed: {r['error']}"
        cache.put(q, answer)
        return {"rag_result": r, "final_answer": answer,
                "trace": state["trace"] + [{"agent": "knowledge", "retry": retry}]}

    verdict = run_critic(r["answer"], r["context"])
    trace = state["trace"] + [{"agent": "knowledge", "retry": retry},
                              {"agent": "critic", "verdict": verdict["verdict"]}]

    if verdict["verdict"] != "grounded" and retry < 1:
        return {"rag_result": r, "critic_verdict": verdict,
                "retry_count": retry + 1, "trace": trace}   # no final_answer -> loop back

    if verdict["verdict"] == "grounded":
        answer = r["answer"] + (f"\n\nSources: {', '.join(r['sources'])}" if r["sources"] else "")
    else:
        answer = ("I could not verify parts of the answer against the data, so here is "
                  "only what is supported: " + r["answer"])
    cache.put(q, answer)
    return {"rag_result": r, "critic_verdict": verdict, "final_answer": answer, "trace": trace}


def hybrid_node(state: AgentState) -> dict:
    """Analyst numbers first, then RAG explains them, critic-gated, synthesized."""
    q = state["question"]
    conn = sqlite3.connect(DB_URI, uri=True)
    movers = analytics.top_movers(conn, n=3)
    top_asin = movers[0][0] if movers else None
    trend = analytics.rating_trend(conn, top_asin) if top_asin else []

    rag = run_knowledge(q, where={"parent_asin": top_asin} if top_asin else None)
    rag_part = rag["answer"] if rag["answer"] else "No review evidence found."

    verdict = run_critic(rag_part, rag.get("context", ""))
    if verdict["verdict"] != "grounded":
        rag_part = "Review evidence could not be verified; reporting numbers only."

    data = (f"Question: {q}\nTop movers: {movers}\nTrend for {top_asin}: {trend}\n"
            f"Review evidence: {rag_part}")
    answer = ask_llm(SYNTH_PROMPT, data)
    if rag.get("sources"):
        answer += f"\n\nSources: {', '.join(rag['sources'])}"
    cache.put(q, answer)
    return {"analyst_result": {"movers": movers, "trend": trend}, "rag_result": rag,
            "critic_verdict": verdict, "final_answer": answer,
            "trace": state["trace"] + [{"agent": "market_analyst"},
                                       {"agent": "knowledge"},
                                       {"agent": "critic", "verdict": verdict["verdict"]},
                                       {"agent": "supervisor", "action": "synthesize"}]}


def reject_node(state: AgentState) -> dict:
    return {"final_answer": ("I can only answer questions about home-appliance products "
                             "and their reviews in this dataset."),
            "trace": state["trace"] + [{"agent": "reject"}]}


def _route(state: AgentState) -> str:
    if state.get("final_answer"):
        return "done"
    return state["route_plan"][0]


def _after_rag(state: AgentState) -> str:
    return "done" if state.get("final_answer") else "rag"   # retry loop


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("sql", sql_node)
    g.add_node("rag", rag_node)
    g.add_node("analyst", analyst_node)
    g.add_node("hybrid", hybrid_node)
    g.add_node("reject", reject_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"sql": "sql", "rag": "rag", "analyst": "analyst",
                             "hybrid": "hybrid", "reject": "reject", "done": END})
    g.add_conditional_edges("rag", _after_rag, {"rag": "rag", "done": END})
    g.add_edge("sql", END)
    g.add_edge("analyst", END)
    g.add_edge("hybrid", END)
    g.add_edge("reject", END)
    return g.compile()