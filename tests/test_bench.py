"""Benchmark runner and report, end to end on the mock backend (offline)."""

import csv

from minicodex.bench import COLUMNS, RunConfig, default_label, run_benchmark
from minicodex.report import load_runs, render, retry_pairs


def _read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def test_mock_run_writes_full_csv(tmp_path):
    rows = run_benchmark(RunConfig(suite="custom"), tmp_path / "mock")
    assert len(rows) == 8
    saved = _read(tmp_path / "mock" / "results.csv")
    assert list(saved[0]) == COLUMNS
    assert sum(r["solved"] == "True" for r in saved) == 7  # 08 is outside the playbook
    assert (tmp_path / "mock" / "traces" / "custom" / "01_off_by_one.jsonl").exists()


def test_cascade_escalates_cheap_failures(tmp_path):
    cfg = RunConfig(suite="custom", router="jev", cascade=True)
    rows = {r["task"]: r for r in run_benchmark(cfg, tmp_path / "jev")}
    two_file = rows["04_two_file_bug"]
    assert two_file["route_tier"] == "strong"  # fake Jev sees two source files
    easy = rows["01_off_by_one"]
    assert easy["route_tier"] == "cheap" and not easy["escalated"] and easy["solved"]
    assert all(r["route_source"] in {"jev", "low_confidence"} for r in rows.values())


def test_pure_cascade_rescues_multi_file_bug(tmp_path):
    cfg = RunConfig(suite="custom", cascade=True, limit=4)
    rows = {r["task"]: r for r in run_benchmark(cfg, tmp_path / "cascade")}
    r = rows["04_two_file_bug"]
    assert r["escalated"] and r["solved"] and r["models_used"] == "mock-cheap>mock-strong"


def test_noretry_vs_full_and_report(tmp_path):
    runs_dir = tmp_path / "runs"
    run_benchmark(RunConfig(suite="custom", label="full"), runs_dir / "full")
    run_benchmark(
        RunConfig(suite="custom", max_iterations=1, label="noretry"), runs_dir / "noretry"
    )
    runs = load_runs(runs_dir)
    pairs = {p["suite"]: p for p in retry_pairs(runs)}
    assert pairs["custom"]["rescued_by_retry"] == 1  # the two-file bug
    assert pairs["custom"]["gain_pp"] > 0
    md = render(runs)
    assert "Retry loop vs no-retry baseline" in md and "Wilson" in md


def test_repeat_and_limit(tmp_path):
    rows = run_benchmark(RunConfig(suite="all", limit=1, repeat=2), tmp_path / "rep")
    assert len(rows) == 4 and {r["repeat"] for r in rows} == {1, 2}
    assert (tmp_path / "rep" / "traces" / "custom" / "01_off_by_one_r2.jsonl").exists()


def test_default_labels():
    assert (
        default_label(RunConfig(backend="openai", model="openai/gpt-6.1-sol"))
        == "openai_gpt-6.1-sol_all"
    )
    assert (
        default_label(
            RunConfig(backend="openai", router="jev", cascade=True, suite="custom", limit=3)
        )
        == "openai_jev_cascade_custom_limit3"
    )
    assert default_label(RunConfig(max_iterations=1)).endswith("_noretry_all")
