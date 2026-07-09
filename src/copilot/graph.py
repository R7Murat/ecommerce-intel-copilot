"""Graph wiring. Nodes are stubs in Phase 1.1; real agents replace them incrementally."""
from langgraph.graph import StateGraph, START, END

from copilot.state import AgentState


def supervisor_node(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append({"agent": "supervisor", "note": "stub — routing not implemented yet"})
    return {"route_plan": ["echo"], "trace": trace}


def echo_node(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append({"agent": "echo", "note": "stub"})
    return {"final_answer": f"ECHO: {state['question']}", "trace": trace}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("echo", echo_node)
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", "echo")
    g.add_edge("echo", END)
    return g.compile()