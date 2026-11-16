"""End-to-end: the full agent loop on real benchmark tasks, mock backend."""

import json
import shutil
from pathlib import Path

from minicodex.agent import Agent
from minicodex.backends import MockBackend

TASKS = Path(__file__).resolve().parent.parent / "benchmark" / "suites" / "custom"


def _run(task_name, tmp_path, max_iterations=6):
    workdir = tmp_path / "work"
    shutil.copytree(TASKS / task_name / "repo", workdir)
    issue = (TASKS / task_name / "issue.md").read_text(encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    agent = Agent(backend=MockBackend(), max_iterations=max_iterations, trace_path=trace)
    return agent.run(workdir, issue), workdir, trace


def test_solves_off_by_one(tmp_path):
    result, workdir, trace = _run("01_off_by_one", tmp_path)
    assert result.solved
    assert result.iterations == 1  # diagnostic run is free; one edit + verify
    assert result.test_runs == 2
    assert result.files_changed == ["mathutils.py"]
    assert "range(1, n + 1)" in (workdir / "mathutils.py").read_text()
    assert "-    for i in range(1, n):" in result.diff

    events = [json.loads(line) for line in trace.read_text().splitlines()]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "start" and "diff_for_human_review" in kinds
    assert any(e["event"] == "test_run" and e["passed"] for e in events)


def test_solves_two_file_bug_in_multiple_iterations(tmp_path):
    result, workdir, _ = _run("04_two_file_bug", tmp_path)
    assert result.solved
    assert result.iterations == 2  # fix constants -> fail, fix cart -> pass
    assert result.files_changed == ["cart.py", "constants.py"]


def test_feature_request_adds_slugify(tmp_path):
    result, workdir, _ = _run("05_feature_request", tmp_path)
    assert result.solved
    assert result.files_changed == ["text_utils.py"]  # tests left untouched
    assert "def slugify" in (workdir / "text_utils.py").read_text()


def test_hard_task_reports_honest_failure(tmp_path):
    result, workdir, _ = _run("08_search_bug", tmp_path)
    assert not result.solved
    assert result.failure_reason == "wrong_fix"
    assert result.files_changed == []  # gave up without touching code
    assert "while lo < hi:" in (workdir / "search.py").read_text()


def test_iteration_budget_is_respected(tmp_path):
    result, _, _ = _run("04_two_file_bug", tmp_path, max_iterations=1)
    assert not result.solved
    assert result.iterations == 1
    assert result.gave_up
    assert result.failure_reason == "budget_exhausted"


def test_usage_is_tracked(tmp_path):
    result, _, _ = _run("02_wrong_condition", tmp_path)
    assert result.usage.total_tokens > 0
    assert result.usage.cost_usd == 0.0  # mock backend is free
