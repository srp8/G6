"""Evaluation statistics."""

import math

import pytest

from minicodex.metrics import failure_taxonomy, reliability, summarize_rows, wilson_ci


def test_wilson_matches_reference_values():
    # Reference: 8/10 -> [0.490, 0.943] (Wilson 1927; e.g. statsmodels proportion_confint)
    lo, hi = wilson_ci(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3)
    assert hi == pytest.approx(0.9433, abs=1e-3)


def test_wilson_edge_cases():
    assert wilson_ci(0, 0) == (0.0, 0.0)
    lo, hi = wilson_ci(0, 30)
    assert lo == 0.0 and 0.10 < hi < 0.12  # never a degenerate [0, 0]
    lo, hi = wilson_ci(30, 30)
    assert hi == pytest.approx(1.0) and 0.88 < lo < 0.90


def _row(task, solved, cost=0.1, reason="", suite="s"):
    return {
        "task": task,
        "suite": suite,
        "solved": str(solved),
        "iterations": "1",
        "wall_time_s": "2",
        "total_tokens": "100",
        "cost_usd": str(cost),
        "failure_reason": reason,
    }


def test_summary_cost_per_solved():
    rows = [_row("a", True), _row("b", False, reason="wrong_fix"), _row("c", True)]
    s = summarize_rows(rows)
    assert s["solved"] == 2 and s["n"] == 3
    assert s["cost_per_solved_usd"] == pytest.approx(0.15)
    assert failure_taxonomy(rows) == {"wrong_fix": 1}


def test_summary_no_solves_gives_nan_cost_per_solved():
    assert math.isnan(summarize_rows([_row("a", False)])["cost_per_solved_usd"])


def test_reliability_consistency():
    rows = [_row("a", True), _row("b", False), _row("a", True), _row("b", True)]
    r = reliability(rows)
    assert r["repeats"] == 2
    assert r["consistent_share"] == 0.5
    assert r["per_repeat_pass_at_1"] == [0.5, 1.0]
