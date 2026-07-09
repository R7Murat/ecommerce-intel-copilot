"""Shared graph state for the multi-agent system."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    question: str
    route_plan: list[str]
    sql_result: dict | None
    rag_result: dict | None
    analyst_result: dict | None
    draft_answer: str | None
    critic_verdict: dict | None
    retry_count: int
    final_answer: str | None
    trace: list[dict]