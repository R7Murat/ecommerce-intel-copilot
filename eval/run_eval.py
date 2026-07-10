"""Evaluation harness. Phase 2.2: SQL execution accuracy + trajectory (route) accuracy."""
import json
import sqlite3
import time
from pathlib import Path

from copilot.agents.sql_analyst import run_sql_analyst
from copilot.config import DB_URI
from copilot.llm import ask_llm

QUESTIONS = Path(__file__).parent / "questions.jsonl"

ROUTER_PROMPT = """Classify the user's question into exactly one word:
- sql: answerable by querying product/review statistics (counts, averages, rankings, prices, dates)
- rag: requires reading review/product texts (opinions, complaints, experiences, descriptions)
- reject: not about home-appliance products or their reviews at all
Answer with one word only: sql, rag, or reject."""


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]


def rows_match(reference_rows: list, candidate_rows: list) -> bool:
    """Reference values must appear in the candidate, row by row, in order.
    Tolerates extra columns in the candidate and float rounding differences."""
    if len(reference_rows) != len(candidate_rows):
        return False
    for ref_row, cand_row in zip(reference_rows, candidate_rows):
        cand_norm = [_norm(v) for v in cand_row]
        for ref_val in ref_row:
            if _norm(ref_val) not in cand_norm:
                return False
    return True


def _norm(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def eval_sql(items: list[dict]) -> dict:
    conn = sqlite3.connect(DB_URI, uri=True)
    passed, details = 0, []
    for it in items:
        ref_rows = conn.execute(it["reference_sql"]).fetchall()
        result = run_sql_analyst(it["question"])
        ok = result["error"] is None and rows_match(ref_rows, result["rows"])
        passed += ok
        details.append({"id": it["id"], "pass": ok,
                        "note": result["error"] or ("" if ok else f"mismatch: ref={ref_rows[:2]} got={result['rows'][:2]}")})
        time.sleep(2)  # stay under free-tier per-minute limits
    return {"metric": "sql_execution_accuracy", "score": passed / len(items), "details": details}


def eval_routes(items: list[dict]) -> dict:
    passed, details = 0, []
    for it in items:
        route = ask_llm(ROUTER_PROMPT, it["question"]).strip().lower()
        ok = route == it["expected_route"]
        passed += ok
        details.append({"id": it["id"], "pass": ok, "note": "" if ok else f"expected {it['expected_route']}, got {route}"})
        time.sleep(4)
    return {"metric": "trajectory_accuracy", "score": passed / len(items), "details": details}


if __name__ == "__main__":
    qs = load_questions()
    sql_items = [q for q in qs if q["type"] == "sql"]

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
    print(f"score: {r2['score']:.0%}")