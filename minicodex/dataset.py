"""Benchmark task discovery.

A suite is a directory under ``benchmark/suites/`` holding one folder per
task; each task folder has ``task.json``, ``issue.md`` and ``repo/``.

- ``custom``: 8 hand-written seeded bugs (multi-file, feature request, ...).
- ``humanevalfix``: a fixed-seed sample of 30 HumanEvalFix Python problems,
  built by ``scripts/build_humanevalfix.py`` (see DATASET.md).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SUITES_DIR = Path(os.environ.get("MINICODEX_SUITES_DIR", REPO_ROOT / "benchmark" / "suites"))
SUITES = ("custom", "humanevalfix")


@dataclass
class Task:
    name: str
    suite: str
    path: Path
    difficulty: str = "unknown"
    category: str = "unknown"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def repo(self) -> Path:
        return self.path / "repo"

    @property
    def issue(self) -> str:
        return (self.path / "issue.md").read_text(encoding="utf-8")


def load_task(task_dir: str | Path, suite: str | None = None) -> Task:
    task_dir = Path(task_dir)
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    for required in ("issue.md", "repo"):
        if not (task_dir / required).exists():
            raise FileNotFoundError(f"{task_dir} is missing {required}")
    return Task(
        name=meta.get("name", task_dir.name),
        suite=meta.get("suite", suite or task_dir.parent.name),
        path=task_dir,
        difficulty=meta.get("difficulty", "unknown"),
        category=meta.get("category", "unknown"),
        meta=meta,
    )


def load_suite(
    suite: str, suites_dir: str | Path | None = None, limit: int | None = None
) -> list[Task]:
    """Tasks of one suite, sorted by name; ``limit`` keeps the first N."""
    root = Path(suites_dir or SUITES_DIR) / suite
    if not root.is_dir():
        raise FileNotFoundError(f"unknown suite {suite!r}: {root} does not exist")
    tasks = [load_task(d, suite) for d in sorted(root.iterdir()) if (d / "task.json").exists()]
    return tasks[:limit] if limit else tasks


def load_tasks(
    suite: str = "all", suites_dir: str | Path | None = None, limit: int | None = None
) -> list[Task]:
    """``suite`` is a suite name or ``all``; ``limit`` applies per suite."""
    names = SUITES if suite == "all" else (suite,)
    return [t for name in names for t in load_suite(name, suites_dir, limit)]
