"""Critic agent: runtime groundedness gate. Verdict: grounded | partial | ungrounded."""
import json
import re

from copilot.llm import ask_llm

CRITIC_PROMPT = """You are a strict verifier. Given source material and a draft answer,
judge whether every factual claim in the answer is supported by the sources.
Respond with ONLY a JSON object:
{"verdict": "grounded" | "partial" | "ungrounded", "issues": ["<unsupported claim>", ...]}
"issues" must be empty when the verdict is "grounded"."""

VALID = {"grounded", "partial", "ungrounded"}


def _parse(raw: str) -> dict:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(s)
        verdict = str(obj.get("verdict", "")).lower()
        issues = [str(i) for i in obj.get("issues", [])]
    except (json.JSONDecodeError, AttributeError):
        m = re.search(r'"verdict"\s*:\s*"(\w+)"', raw)
        verdict = m.group(1).lower() if m else ""
        issues = []
    if verdict not in VALID:
        # unparseable critic output -> fail SAFE: treat as ungrounded
        return {"verdict": "ungrounded", "issues": ["critic output unparseable"]}
    return {"verdict": verdict, "issues": issues}


def run_critic(draft_answer: str, sources_text: str) -> dict:
    """Returns {'verdict': ..., 'issues': [...]} — never raises."""
    try:
        raw = ask_llm(
            CRITIC_PROMPT,
            f"Sources:\n{sources_text}\n\nDraft answer:\n{draft_answer}",
        )
        return _parse(raw)
    except Exception as e:
        return {"verdict": "ungrounded", "issues": [f"critic error: {e}"]}