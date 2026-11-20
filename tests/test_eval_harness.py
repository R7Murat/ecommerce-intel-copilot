"""Deterministic parts of the eval harness: row matching, injection checks, judge parsing, CI."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import judge  # noqa: E402
import report  # noqa: E402
import run_eval  # noqa: E402


def test_rows_match_tolerates_rounding_and_extra_columns():
    assert run_eval.rows_match([(4.25,)], [(4.2512, "x")])
    assert not run_eval.rows_match([(1,), (2,)], [(2,), (1,)])
    assert not run_eval.rows_match([(1,)], None)


def test_injection_checks_catch_prompt_leak_and_secret(monkeypatch):
    item = {"checks": {"route_in": ["reject"]}}
    leak = run_eval.LEAK_LINES[0]
    assert not run_eval.injection_checks(item, "rag", f"Sure: {leak}", True)["no_prompt_leak"]
    monkeypatch.setenv("FAKE_API_KEY", "abcdefgh12345")
    c = run_eval.injection_checks(item, "reject", "key is abcdefgh12345", True)
    assert not c["no_secret_leak"] and c["route_in"]
    assert all(run_eval.injection_checks(item, "reject", "I can only answer...", True).values())


def test_judge_parse_and_abstention():
    assert judge.parse('{"claims_total": 4, "claims_supported": 3, "relevance": 0.5}')[
        "faithfulness"] == 0.75
    assert judge.parse('```json\n{"claims_total": 0, "claims_supported": 0, "relevance": 0}\n```')[
        "faithfulness"] == 1.0
    with pytest.raises(ValueError):
        judge.parse('{"claims_total": 1, "claims_supported": 2, "relevance": 1}')


def test_bootstrap_ci_contains_mean_and_is_deterministic():
    vals = [1.0] * 15 + [0.0] * 5
    ci = report.bootstrap(vals)
    assert ci[0] <= 0.75 <= ci[1] and ci == report.bootstrap(vals)
    assert report.bootstrap([1.0]) is None


def test_per_question_averages_runs_before_resampling():
    runs = [[{"id": "a", "type": "sql", "sql_ok": True}],
            [{"id": "a", "type": "sql", "sql_ok": False}]]
    assert report.per_question(runs, {"sql"}, lambda r: r["sql_ok"]) == {"a": 0.5}
