"""Aggregate raw + judge files into eval_results JSON with bootstrap 95% CIs; parity; README table.

Usage (repo root):
  python eval/report.py summary cloud_low          -> eval_results/v3_<date>_cloud_low.json
  python eval/report.py parity cloud_low local_low -> eval_results/v3_<date>_parity.json
  python eval/report.py table eval_results/v3_<date>_cloud_low.json   (markdown to stdout)

CI method (pre-registered): average each question over runs first, then resample questions
(B=10000, seed 0, percentile). Runs of one question are not independent samples.
"""
import datetime
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "eval_results" / "raw"
B, SEED = 10_000, 0

# name -> (question types, value from merged row; None = not scored)
METRICS = {
    "route_accuracy": ({"sql", "rag", "analyst", "hybrid", "reject"}, lambda r: r["route_ok"]),
    "sql_execution_accuracy": ({"sql"}, lambda r: r.get("sql_ok")),
    "rag_faithfulness": ({"rag"}, lambda r: r.get("faithfulness")),
    "rag_relevance": ({"rag"}, lambda r: r.get("relevance")),
    "analyst_tool_faithfulness": ({"analyst"}, lambda r: r.get("faithfulness")),
    "analyst_relevance": ({"analyst"}, lambda r: r.get("relevance")),
    "hybrid_faithfulness": ({"hybrid"}, lambda r: r.get("faithfulness")),
    "hybrid_relevance": ({"hybrid"}, lambda r: r.get("relevance")),
    "hybrid_evidence_direction_ok": ({"hybrid"}, lambda r: r.get("evidence_direction_ok")),
    "hybrid_critic_grounded": ({"hybrid"}, lambda r: r.get("critic") == "grounded"),
    "reject_accuracy": ({"reject"}, lambda r: r["route_ok"]),
    "injection_defense": ({"injection"}, lambda r: r.get("defended")),
}


def load_runs(tag: str) -> list[list[dict]]:
    runs = []
    for raw in sorted(RAW.glob(f"v3_{tag}_r*.jsonl")):
        if raw.name.endswith(".judge.jsonl"):
            continue
        judged = raw.with_suffix(".judge.jsonl")
        scores = {j["id"]: j for j in map(json.loads, judged.read_text(encoding="utf-8")
                                          .splitlines())} if judged.exists() else {}
        rows = [r | scores.get(r["id"], {}) for r in map(json.loads,
                                                         raw.read_text(encoding="utf-8").splitlines())]
        runs.append(rows)  # system errors stay in and score as failures
    if not runs:
        sys.exit(f"no raw files for {tag}")
    return runs


# Files that shape an answer; commits that differ only elsewhere (docs, scripts) still compare.
GENERATION_PATHS = ["src", "eval/run_eval.py", "eval/harness.py", "eval/golden_v2.jsonl"]


def same_generation_code(commits: set[str]) -> bool:
    first, *rest = sorted(commits)
    return all(subprocess.run(["git", "diff", "--quiet", first, c, "--", *GENERATION_PATHS],
                              cwd=ROOT).returncode == 0 for c in rest)


def check(runs: list[list[dict]]) -> dict:
    """Refuse to aggregate mixed code, mixed models, fallback answers or incomplete runs."""
    rows = [r for run in runs for r in run]
    commits = {r["commit"] for r in rows}
    models = {r["primary_model"] for r in rows}
    assert not any(r["dirty_tree"] for r in rows), "run made from a dirty tree"
    assert same_generation_code(commits), f"generation code differs across {commits}"
    assert len(models) == 1, f"mixed models: {models}"
    judges = {r["judge_model"] for r in rows if "judge_model" in r}
    assert len(judges) <= 1, f"mixed judge models: {judges}"
    assert all(r.get("fallback_calls", 0) == 0 for r in rows), "fallback answers present"
    ids = [sorted(r["id"] for r in run) for run in runs]
    assert all(i == ids[0] for i in ids), "runs cover different questions"
    return {"commits": sorted(commits), "primary_model": models.pop(),
            "profile": rows[0]["profile"], "reasoning_effort": rows[0]["reasoning_effort"],
            "runs": len(runs), "n_questions": len(ids[0]),
            "judge_model": judges.pop() if judges else None}


def per_question(runs: list[list[dict]], types: set, fn) -> dict[str, float]:
    """Mean over runs per question; questions without any score are left out."""
    vals: dict[str, list[float]] = {}
    for run in runs:
        for r in run:
            if r["type"] in types and (v := fn(r)) is not None:
                vals.setdefault(r["id"], []).append(float(v))
    return {q: statistics.fmean(v) for q, v in vals.items()}


def bootstrap(values: list[float]) -> list[float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(SEED)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(B))
    return [round(means[int(0.025 * B)], 3), round(means[int(0.975 * B) - 1], 3)]


def summary(tag: str) -> Path:
    runs = load_runs(tag)
    meta = check(runs)
    metrics = {}
    for name, (types, fn) in METRICS.items():
        pq = per_question(runs, types, fn)
        n_items = len({r["id"] for r in runs[0] if r["type"] in types})
        per_run = [statistics.fmean(v) if (v := [float(fn(r)) for r in run
                   if r["type"] in types and fn(r) is not None]) else None for run in runs]
        metrics[name] = {"mean": round(statistics.fmean(pq.values()), 3) if pq else None,
                         "ci95": bootstrap(list(pq.values())), "n": len(pq),
                         "n_unscored": n_items - len(pq),
                         "per_run": [round(x, 3) if x is not None else None for x in per_run]}
    rows = [r for run in runs for r in run]
    lat = sorted(r["latency_s"] for r in rows if "latency_s" in r)
    ops = {"latency_p50_s": lat[len(lat) // 2], "latency_p95_s": lat[int(0.95 * (len(lat) - 1))],
           "mean_llm_calls": round(statistics.fmean(r.get("llm_calls", 0) for r in rows), 2),
           "mean_tokens": round(statistics.fmean(r.get("input_tokens", 0) + r.get("output_tokens", 0)
                                                 for r in rows)),
           "system_errors": sum(bool(r.get("error")) for r in rows),
           "judge_errors": sum("judge_error" in r for r in rows)}
    out = {"kind": "eval_v3", "date": datetime.date.today().isoformat(), **meta,
           "golden_set": "eval/golden_v2.jsonl", "ci_method": __doc__.split("CI method")[1].strip(),
           "judge": "uncalibrated until Faz 3 (docs/judge_calibration.md)",
           "metrics": metrics, "ops": ops}
    path = ROOT / "eval_results" / f"v3_{out['date']}_{tag}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return path


def parity(tag_a: str, tag_b: str) -> Path:
    """Paired per-question difference b - a, with a bootstrap CI over shared questions."""
    ra, rb = load_runs(tag_a), load_runs(tag_b)
    ma, mb = check(ra), check(rb)
    res = {}
    for name, (types, fn) in METRICS.items():
        qa, qb = per_question(ra, types, fn), per_question(rb, types, fn)
        diffs = [qb[q] - qa[q] for q in sorted(qa.keys() & qb.keys())]
        ci = bootstrap(diffs)
        res[name] = {"mean_diff": round(statistics.fmean(diffs), 3) if diffs else None,
                     "ci95": ci, "n_paired": len(diffs),
                     # 0 inside the CI means "no difference detected", not "equivalent"
                     "difference_detected": bool(ci and (ci[0] > 0 or ci[1] < 0))}
    out = {"kind": "parity_v3", "date": datetime.date.today().isoformat(),
           "a": ma, "b": mb, "diff": f"{tag_b} - {tag_a}", "metrics": res}
    path = ROOT / "eval_results" / f"v3_{out['date']}_parity.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return path


def table(path: str) -> str:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    lines = [f"Measured {d['date']}, commit `{', '.join(d['commits'])}`, {d['primary_model']} "
             f"({d['profile']}, effort {d['reasoning_effort']}), {d['runs']} runs, "
             f"golden set v2 ({d['n_questions']} questions). Source: `{Path(path).name}`.", "",
             "| Metric | Mean | 95% CI | n |", "|---|---|---|---|"]
    for name, m in d["metrics"].items():
        ci = f"{m['ci95'][0]:.2f}–{m['ci95'][1]:.2f}" if m["ci95"] else "–"
        mean = f"{m['mean']:.2f}" if m["mean"] is not None else "–"
        lines.append(f"| {name} | {mean} | {ci} | {m['n']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "table":
        print(table(args[0]))
    else:
        print("->", {"summary": summary, "parity": parity}[cmd](*args))
