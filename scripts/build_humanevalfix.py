"""Build the `humanevalfix` benchmark suite from bigcode/humanevalpack.

HumanEvalFix (Muennighoff et al., 2023, "OctoPack") takes the 164 HumanEval
problems and injects one human-written bug into each canonical solution. This
script draws a fixed-seed sample of the Python split and wraps every sampled
problem as a mini task repo in the same shape as the hand-written tasks:

    benchmark/suites/humanevalfix/<name>/
        issue.md               docstring + "tests fail, fix the bug"
        task.json              metadata (source id, bug type, difficulty, ...)
        repo/<module>.py       prompt + buggy solution (what the agent edits)
        repo/tests/test_<module>.py   the dataset's unit tests, as pytest
        repo/conftest.py       empty; makes the repo root importable

Usage:
    python scripts/build_humanevalfix.py                 # 30 tasks, seed 7400
    python scripts/build_humanevalfix.py --n 50 --seed 1
    python scripts/build_humanevalfix.py --verify        # also check that the
        # buggy code fails and the canonical fix passes every generated test

Data is fetched from the Hugging Face datasets-server REST API (no extra
dependencies). Pass --source path/to/rows.json[l] to build from a local copy.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "benchmark" / "suites" / "humanevalfix"
DATASET = "bigcode/humanevalpack"
ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=bigcode%2Fhumanevalpack"
    "&config=python&split=test&offset={offset}&length={length}"
)
TOTAL_ROWS = 164
DEFAULT_SEED = 7400  # the course number; any fixed value works
DEFAULT_N = 30


def fetch_rows(source: str | None = None) -> list[dict]:
    """Return all 164 Python rows, from a local file or the HF REST API."""
    if source:
        text = Path(source).read_text(encoding="utf-8")
        if source.endswith(".jsonl"):
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        data = json.loads(text)
        return [r.get("row", r) for r in data.get("rows", data)]
    rows: list[dict] = []
    for offset in range(0, TOTAL_ROWS, 100):
        url = ROWS_URL.format(offset=offset, length=100)
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
            payload = json.load(resp)
        rows.extend(item["row"] for item in payload["rows"])
    if len(rows) != TOTAL_ROWS:
        raise RuntimeError(f"expected {TOTAL_ROWS} rows, got {len(rows)}")
    return rows


def sample_rows(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Deterministic sample, returned in dataset order."""
    ordered = sorted(rows, key=lambda r: int(r["task_id"].split("/")[1]))
    picked = sorted(random.Random(seed).sample(range(len(ordered)), n))
    return [ordered[i] for i in picked]


def difficulty_of(row: dict) -> str:
    """A transparent size heuristic: lines in the reference solution."""
    lines = [ln for ln in row["canonical_solution"].splitlines() if ln.strip()]
    if len(lines) <= 3:
        return "easy"
    if len(lines) <= 9:
        return "medium"
    return "hard"


def module_name(entry_point: str) -> str:
    name = entry_point.lower()
    if name in sys.stdlib_module_names or name in {"test", "tests", "conftest"}:
        name = f"{name}_impl"
    return name


def build_test_file(row: dict, module: str) -> str:
    """Turn the dataset's `check(candidate)` harness into a pytest test."""
    entry = row["entry_point"]
    test_code = row["test"]
    # The harness ends with a module-level call such as `check(foo)`; pytest
    # should call it instead, so drop that line and wrap it in a test function.
    test_code = re.sub(
        rf"^check\({re.escape(entry)}\)\s*$", "", test_code, flags=re.MULTILINE
    ).strip("\n")
    header = (
        f'"""Unit tests from HumanEvalFix ({row["task_id"]}), '
        f'bigcode/humanevalpack, MIT license."""\n\n'
    )
    imports = row.get("test_setup", "").strip()
    return (
        header
        + (imports + "\n" if imports else "")
        # HumanEval runs its checks in the solution's namespace, so helpers
        # defined next to the entry point (e.g. encode_cyclic) must be visible.
        + f"from {module} import *  # noqa: F403\n"
        + f"from {module} import {entry}\n\n\n"
        + test_code
        + f"\n\n\ndef test_{entry}():\n    check({entry})\n"
    )


def build_issue(row: dict, module: str) -> str:
    docstring = row["docstring"].strip()
    quoted = "\n".join(f"> {line}" if line else ">" for line in docstring.splitlines())
    return (
        f"# Bug: `{row['entry_point']}` returns wrong results\n\n"
        f"`{row['signature']}` in `{module}.py` is supposed to do the following:\n\n"
        f"{quoted}\n\n"
        f"The unit tests in `tests/` fail. Find and fix the bug in `{module}.py` "
        f"so that all tests pass. Do not modify the tests.\n"
    )


def write_task(row: dict, out_dir: Path) -> Path:
    number = int(row["task_id"].split("/")[1])
    entry = row["entry_point"]
    module = module_name(entry)
    name = f"hef_{number:03d}_{entry}"
    task_dir = out_dir / name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    (task_dir / "repo" / "tests").mkdir(parents=True)

    source = row["prompt"].rstrip("\n") + "\n" + row["buggy_solution"].rstrip() + "\n"
    (task_dir / "repo" / f"{module}.py").write_text(source, encoding="utf-8")
    (task_dir / "repo" / "conftest.py").write_text("", encoding="utf-8")
    (task_dir / "repo" / "tests" / f"test_{module}.py").write_text(
        build_test_file(row, module), encoding="utf-8"
    )
    (task_dir / "issue.md").write_text(build_issue(row, module), encoding="utf-8")
    meta = {
        "name": name,
        "suite": "humanevalfix",
        "difficulty": difficulty_of(row),
        "category": row["bug_type"],
        "failure_symptoms": row["failure_symptoms"],
        "source": f"{DATASET} python {row['task_id']}",
        "entry_point": entry,
        "module": f"{module}.py",
    }
    (task_dir / "task.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # Keep the reference fix out of the agent's repo, but available to --verify.
    return task_dir


def verify(task_dir: Path, row: dict) -> tuple[bool, bool]:
    """(buggy code fails, canonical code passes) for one generated task."""
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    results = []
    for body in (row["buggy_solution"], row["canonical_solution"]):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(task_dir / "repo", work)
            src = row["prompt"].rstrip("\n") + "\n" + body.rstrip() + "\n"
            (work / meta["module"]).write_text(src, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            results.append(proc.returncode == 0)
    buggy_passes, canonical_passes = results
    return (not buggy_passes, canonical_passes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--source", default=None, help="local JSON/JSONL copy of the rows instead of the API"
    )
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    rows = sample_rows(fetch_rows(args.source), args.n, args.seed)
    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    manifest = []
    ok = True
    for row in rows:
        task_dir = write_task(row, out_dir)
        entry = {"name": task_dir.name, "task_id": row["task_id"], "bug_type": row["bug_type"]}
        if args.verify:
            fails, fixed = verify(task_dir, row)
            entry.update(buggy_fails=fails, canonical_passes=fixed)
            ok &= fails and fixed
            print(f"{task_dir.name:40s} buggy fails: {fails}  canonical passes: {fixed}")
        manifest.append(entry)
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "config": "python",
                "split": "test",
                "seed": args.seed,
                "n": args.n,
                "tasks": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(manifest)} tasks to {out_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
