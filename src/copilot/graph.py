"""Graph wiring: supervisor routing -> specialist agents -> final answer."""
from langgraph.graph import StateGraph, START, END

from copilot.agents.knowledge import run_knowledge
from copilot.agents.sql_analyst import run_sql_analyst
from copilot.llm import ask_llm
from copilot.state import AgentState
from copilot.tools import cache

ROUTER_PROMPT = """Classify the user's question into exactly one word:
- sql: answerable by querying product/review statistics (counts, averages, rankings, prices, dates)
- rag: requires reading review/product texts (opinions, complaints, experiences, descriptions)
- reject: not about home-appliance products or their reviews at all
Answer with one word only: sql, rag, or reject."""


def supervisor_node(state: AgentState) -> dict:
    q = state["question"]
    cached = cache.get(q)
    if cached:
        return {"route_plan": ["cache"], "final_answer": cached,
                "trace": [{"agent": "supervisor", "route": "cache"}]}
    route = ask_llm(ROUTER_PROMPT, q).strip().lower()
    if route not in {"sql", "rag", "reject"}:
        route = "rag"  # safe default: grounded path
    return {"route_plan": [route],
            "trace": [{"agent": "supervisor", "route": route}]}


def sql_node(state: AgentState) -> dict:
    r = run_sql_analyst(state["question"])
    if r["error"]:
        answer = f"I could not answer this via SQL: {r['error']}"
    else:
        synthesis = ask_llm(
            "Turn this SQL result into a concise, readable answer. Round numbers sensibly.",
            f"Question: {state['question']}\nSQL: {r['query']}\nRows: {r['rows']}",
        )
        answer = synthesis
    cache.put(state["question"], answer)
    return {"sql_result": r, "final_answer": answer,
            "trace": state["trace"] + [{"agent": "sql_analyst"}]}


def rag_node(state: AgentState) -> dict:
    r = run_knowledge(state["question"])
    answer = r["answer"] if not r["error"] else f"Retrieval failed: {r['error']}"
    if r["sources"]:
        answer += f"\n\nSources: {', '.join(r['sources'])}"
    cache.put(state["question"], answer)
    return {"rag_result": r, "final_answer": answer,
            "trace": state["trace"] + [{"agent": "knowledge"}]}


def reject_node(state: AgentState) -> dict:
    answer = ("I can only answer questions about home-appliance products and their "
              "reviews in this dataset.")
    return {"final_answer": answer,
            "trace": state["trace"] + [{"agent": "reject"}]}


def _route(state: AgentState) -> str:
    if state.get("final_answer"):
        return "done"
    return state["route_plan"][0]


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("sql", sql_node)
    g.add_node("rag", rag_node)
    g.add_node("reject", reject_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"sql": "sql", "rag": "rag", "reject": "reject", "done": END})
    g.add_edge("sql", END)
    g.add_edge("rag", END)
    g.add_edge("reject", END)
    return g.compile()