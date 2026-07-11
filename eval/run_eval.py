"""Evaluation harness: SQL execution accuracy, trajectory accuracy, RAG faithfulness/relevance."""
import json
import re
import sqlite3
import time
from pathlib import Path

from copilot.agents.knowledge import run_knowledge
from copilot.agents.sql_analyst import run_sql_analyst
from copilot.config import DB_URI
from copilot.llm import ask_llm

QUESTIONS = Path(__file__).parent / "questions.jsonl"

ROUTER_PROMPT = """Classify the user's question into exactly one word:
- sql: answerable by querying product/review statistics (counts, averages, rankings, prices, dates)
- rag: requires reading review/product texts (opinions, complaints, experiences, descriptions)
- reject: not about home-appliance products or their reviews at all
Answer with one word only: sql, rag, or reject."""

JUDGE_FAITH = """You are a strict evaluator. Given a context and an answer, list every
factual claim in the answer, and count how many are directly supported by the context.
Respond with ONLY a JSON object: {"supported": <int>, "total": <int>}"""

JUDGE_REL = """You are a strict evaluator. Score how well the answer addresses the
question on a 0.0-1.0 scale (1.0 = fully addresses it, 0.0 = unrelated).
Respond with ONLY the number."""


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def rows_match(reference_rows: list, candidate_rows: list) -> bool:
    """Reference values must appear in the candidate, row by row, in order.
    Tolerates extra columns in the candidate and float rounding differences."""
    if candidate_rows is None or len(reference_rows) != len(candidate_rows):
        return False
    for ref_row, cand_row in zip(reference_rows, candidate_rows):
        cand_norm = [_norm(v) for v in cand_row]
        for ref_val in ref_row:
            if _norm(ref_val) not in cand_norm:
                return False
    return True


def eval_sql(items: list[dict]) -> dict:
    conn = sqlite3.connect(DB_URI, uri=True)
    passed, details = 0, []
    for it in items:
        ref_rows = conn.execute(it["reference_sql"]).fetchall()
        result = run_sql_analyst(it["question"])
        ok = result["error"] is None and rows_match(ref_rows, result["rows"])
        passed += ok
        details.append({"id": it["id"], "pass": ok,
                        "note": result["error"] or ("" if ok else f"mismatch: ref={ref_rows[:2]} got={result['rows'][:2] if result['rows'] else None}")})
        time.sleep(2)  # stay under free-tier per-minute limits
    return {"metric": "sql_execution_accuracy", "score": passed / len(items), "details": details}


def eval_routes(items: list[dict]) -> dict:
    passed, details = 0, []
    for it in items:
        route = ask_llm(ROUTER_PROMPT, it["question"]).strip().lower()
        ok = route == it["expected_route"]
        passed += ok
        details.append({"id": it["id"], "pass": ok,
                        "note": "" if ok else f"expected {it['expected_route']}, got {route}"})
        time.sleep(4)
    return {"metric": "trajectory_accuracy", "score": passed / len(items), "details": details}


def _json_score(raw: str) -> float:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(s)
        supported, total = int(obj["supported"]), int(obj["total"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        m = re.search(r'"supported"\s*:\s*(\d+)\s*,\s*"total"\s*:\s*(\d+)', raw)
        if not m:
            return 0.0
        supported, total = int(m.group(1)), int(m.group(2))
    if total == 0:
        return 0.0
    return max(0.0, min(1.0, supported / total))


def eval_rag(items: list[dict]) -> dict:
    faith_scores, rel_scores, details = [], [], []
    for it in items:
        r = run_knowledge(it["question"])
        if r["error"] or not r["answer"]:
            faith_scores.append(0.0)
            rel_scores.append(0.0)
            details.append({"id": it["id"], "faith": 0.0, "rel": 0.0, "note": r["error"] or "no answer"})
            continue
        f_raw = ask_llm(JUDGE_FAITH, f"Context:\n{r['context']}\n\nAnswer:\n{r['answer']}")
        f = _json_score(f_raw)
        time.sleep(2)
        rel_raw = ask_llm(JUDGE_REL, f"Question: {it['question']}\nAnswer: {r['answer']}")
        try:
            rel = max(0.0, min(1.0, float(rel_raw.strip().split()[0])))
        except ValueError:
            rel = 0.0
        faith_scores.append(f)
        rel_scores.append(rel)
        details.append({"id": it["id"], "faith": round(f, 2), "rel": round(rel, 2), "note": ""})
        time.sleep(2)
    n = len(items)
    return {"faithfulness": sum(faith_scores) / n, "relevance": sum(rel_scores) / n, "details": details}


if __name__ == "__main__":
    qs = load_questions()
    sql_items = [q for q in qs if q["type"] == "sql"]
    rag_items = [q for q in qs if q["type"] == "rag"]

    print("== SQL execution accuracy ==")
    r1 = eval_sql(sql_items)
    for d in r1["details"]:
        print(f"  {d['id']}: {'PASS' if d['pass'] else 'FAIL  ' + d['note'][:120]}")
    print(f"score: {r1['score']:.0%}\n")

    print("== Trajectory accuracy (all 30) ==")
    r2 = eval_routes(qs)
    for d in r2["details"]:
        if not d["pass"]:
            print(f"  {d['id']}: FAIL  {d['note']}")
    print(f"score: {r2['score']:.0%}\n")

    print("== RAG: faithfulness & relevance ==")
    r3 = eval_rag(rag_items)
    for d in r3["details"]:
        print(f"  {d['id']}: faith={d['faith']} rel={d['rel']} {d['note'] or ''}")
    print(f"faithfulness: {r3['faithfulness']:.2f}  relevance: {r3['relevance']:.2f}")