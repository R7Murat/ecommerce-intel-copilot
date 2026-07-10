"""Critic must catch fabricated claims and pass grounded ones (live LLM test)."""
import pytest

from copilot.agents.critic import run_critic, _parse

SOURCES = "The ice maker leaks after 15 months. Users report loud noise at night."


def test_parse_handles_fenced_json():
    raw = '```json\n{"verdict": "grounded", "issues": []}\n```'
    assert _parse(raw) == {"verdict": "grounded", "issues": []}


def test_parse_fails_safe_on_garbage():
    assert _parse("I think it looks fine!")["verdict"] == "ungrounded"


@pytest.mark.llm
def test_grounded_answer_passes():
    r = run_critic("Users report leaking after 15 months [src].", SOURCES)
    assert r["verdict"] == "grounded"


@pytest.mark.llm
def test_fabricated_answer_caught():
    r = run_critic("The ice maker was recalled by the manufacturer in 2019.", SOURCES)
    assert r["verdict"] in {"ungrounded", "partial"}