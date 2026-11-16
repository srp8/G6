"""Benchmark suites: loader and the HumanEvalFix conversion."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from minicodex.dataset import SUITES_DIR, load_suite, load_task, load_tasks

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_humanevalfix as builder  # noqa: E402


def test_suites_have_expected_sizes():
    assert len(load_suite("custom")) == 8
    assert len(load_suite("humanevalfix")) == 30
    assert len(load_tasks("all")) == 38


def test_limit_applies_per_suite():
    tasks = load_tasks("all", limit=3)
    assert [t.suite for t in tasks] == ["custom"] * 3 + ["humanevalfix"] * 3


def test_unknown_suite_raises():
    with pytest.raises(FileNotFoundError):
        load_suite("nope")


def test_every_task_is_well_formed():
    for task in load_tasks("all"):
        assert task.issue.strip()
        assert (task.repo / "tests").is_dir()
        assert task.difficulty in {"easy", "medium", "hard"}
        assert not any(p.name == "manifest.json" for p in task.repo.rglob("*"))


def test_manifest_records_seed_and_source():
    manifest = json.loads((SUITES_DIR / "humanevalfix" / "manifest.json").read_text())
    assert manifest["dataset"] == "bigcode/humanevalpack"
    assert manifest["seed"] == builder.DEFAULT_SEED and manifest["n"] == 30
    names = sorted(t["name"] for t in manifest["tasks"])
    assert names == [t.name for t in load_suite("humanevalfix")]


def test_sampling_is_deterministic():
    rows = [{"task_id": f"Python/{i}"} for i in range(164)]
    a = builder.sample_rows(rows, 30, 7400)
    b = builder.sample_rows(list(reversed(rows)), 30, 7400)
    assert a == b and len(a) == 30


FAKE_ROW = {
    "task_id": "Python/999",
    "prompt": (
        'def double(x: int) -> int:\n    """Return twice x.\n    >>> double(2)\n    4\n    """\n'
    ),
    "buggy_solution": "    return x + 2\n",
    "canonical_solution": "    return 2 * x\n",
    "bug_type": "operator misuse",
    "failure_symptoms": "incorrect output",
    "entry_point": "double",
    "test_setup": "",
    "test": (
        "\n\ndef check(double):\n    assert double(3) == 6\n"
        "    assert double(0) == 0\n\ncheck(double)\n"
    ),
    "signature": "double(x: int) -> int",
    "docstring": "Return twice x.\n>>> double(2)\n4",
}


def test_conversion_wraps_a_row_as_a_failing_task(tmp_path):
    task_dir = builder.write_task(FAKE_ROW, tmp_path)
    task = load_task(task_dir)
    assert task.suite == "humanevalfix" and task.name == "hef_999_double"
    assert "Return twice x." in task.issue and "Do not modify the tests" in task.issue
    test_src = (task.repo / "tests" / "test_double.py").read_text()
    assert "def test_double():" in test_src and "\ncheck(double)\n" not in test_src
    assert builder.verify(task_dir, FAKE_ROW) == (True, True)


def test_buggy_humanevalfix_task_fails_as_shipped(tmp_path):
    task = load_suite("humanevalfix")[0]
    work = tmp_path / "repo"
    shutil.copytree(task.repo, work)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
