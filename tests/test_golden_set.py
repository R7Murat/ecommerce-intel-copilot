"""Golden set v2 hygiene: schema, no leakage into demo/smoke/prompts, runnable reference SQL."""
import ast
import itertools
import json
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = [json.loads(line) for line in (ROOT / "eval" / "golden_v2.jsonl").read_text(
    encoding="utf-8").splitlines() if line.strip()]
ROUTES = {"sql", "rag", "analyst", "hybrid", "reject"}
LEAK_JACCARD = 0.5


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb)


def _demo_examples() -> list[str]:
    tree = ast.parse((ROOT / "src" / "copilot" / "ui" / "app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "examples" for t in node.targets):
            return [e.value for e in node.value.elts]
    raise AssertionError("examples list not found in app.py")


def _prompt_lines() -> list[str]:
    from copilot import graph
    from copilot.agents import critic, knowledge, sql_analyst
    prompts = [graph.ROUTER_PROMPT, graph.SYNTH_PROMPT, critic.CRITIC_PROMPT,
               knowledge.SYSTEM_PROMPT, sql_analyst.SYSTEM_PROMPT]
    return [line for p in prompts for line in p.splitlines() if len(_tokens(line)) >= 4]


def test_schema():
    ids = [q["id"] for q in GOLDEN]
    assert len(ids) == len(set(ids))
    for q in GOLDEN:
        if q["type"] == "injection":
            assert q["expected_route"] is None and isinstance(q["checks"], dict)
        else:
            assert q["expected_route"] in ROUTES
        if q["type"] == "sql":
            assert q["reference_sql"].upper().startswith("SELECT")
        if q["type"] == "hybrid":
            assert q["direction"] in {"up", "down", "any"}


def test_no_leak_into_demo_smoke_or_prompts():
    smoke = [json.loads(line)["question"] for line in
             (ROOT / "eval" / "smoke.jsonl").read_text(encoding="utf-8").splitlines() if line]
    others = _demo_examples() + smoke + _prompt_lines()
    leaks = [(q["id"], o) for q in GOLDEN for o in others
             if _jaccard(q["question"], o) >= LEAK_JACCARD]
    assert not leaks, leaks


def test_no_near_duplicates_inside_set():
    dups = [(a["id"], b["id"]) for a, b in itertools.combinations(GOLDEN, 2)
            if _jaccard(a["question"], b["question"]) >= LEAK_JACCARD]
    assert not dups, dups


@pytest.mark.skipif(not (ROOT / "data" / "products.db").exists(), reason="needs data/products.db")
def test_reference_sql_runs_and_returns_rows():
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'products.db'}?mode=ro", uri=True)
    for q in GOLDEN:
        if q["type"] == "sql":
            assert conn.execute(q["reference_sql"]).fetchall(), q["id"]
