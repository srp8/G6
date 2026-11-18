"""Run the agent on a single task from the command line.

A task directory contains:
    repo/      the small Python project with failing tests
    issue.md   the issue description given to the agent

The task repo is copied to a scratch directory first -- the agent never
touches the original (sandbox guardrail). Examples:

    minicodex --task benchmark/suites/custom/04_two_file_bug
    minicodex --task benchmark/suites/humanevalfix/hef_046_fib4 \\
        --backend openai --router jev
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from minicodex.agent import Agent
from minicodex.backends import get_backend
from minicodex.router import CHEAP_MODEL, STRONG_MODEL, make_router
from minicodex.trace import TraceLogger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G6 Unit: run one task")
    parser.add_argument(
        "--task", required=True, help="task directory containing repo/ and issue.md"
    )
    parser.add_argument("--backend", default=None, help="mock (default, offline) or openai")
    parser.add_argument(
        "--model", default=None, help="model id for the openai backend, e.g. openai/gpt-6.1-sol"
    )
    parser.add_argument(
        "--router",
        default="none",
        choices=["none", "jev", "heuristic"],
        help="pick the cheap or strong model per task",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=int(os.environ.get("MINICODEX_MAX_ITERATIONS", 6))
    )
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument(
        "--trace", default=None, help="path for the JSONL trace (default: <tmp>/trace.jsonl)"
    )
    args = parser.parse_args(argv)

    task_dir = Path(args.task)
    repo = task_dir / "repo"
    issue_file = task_dir / "issue.md"
    if not repo.is_dir() or not issue_file.is_file():
        print(f"error: {task_dir} must contain repo/ and issue.md", file=sys.stderr)
        return 2
    issue = issue_file.read_text(encoding="utf-8")
    backend_name = (args.backend or os.environ.get("MINICODEX_BACKEND") or "mock").lower()

    scratch = Path(tempfile.mkdtemp(prefix="minicodex-"))
    workdir = scratch / "repo"
    shutil.copytree(repo, workdir)
    # Keep the trace OUTSIDE the working copy so the agent never sees it.
    trace_path = Path(args.trace) if args.trace else scratch / "trace.jsonl"
    trace = TraceLogger(trace_path)

    model = args.model
    if args.router != "none":
        decision = make_router(args.router, offline=backend_name == "mock").route(issue, repo)
        trace.log("route", **decision.to_dict())
        model = decision.model
        if backend_name == "mock":
            model = "mock-cheap" if decision.model == CHEAP_MODEL else "mock-strong"
        conf = "n/a" if decision.confidence is None else f"{decision.confidence:.2f}"
        print(
            f"router: {decision.router} ({decision.source}) chose {decision.tier} "
            f"-> {model}; confidence {conf}; p={decision.probabilities}"
        )
    elif backend_name == "openai" and not model:
        model = os.environ.get("MINICODEX_MODEL", STRONG_MODEL)

    agent = Agent(
        backend=get_backend(backend_name, model=model, reasoning_effort=args.reasoning_effort),
        max_iterations=args.max_iterations,
        trace=trace,
    )
    result = agent.run(workdir, issue)

    print(f"\n=== G6 Unit result: {task_dir.name} ===")
    print(
        f"solved:        {result.solved}"
        + ("" if result.solved else f"  (failure: {result.failure_reason})")
    )
    print(f"iterations:    {result.iterations} (max {args.max_iterations})")
    print(f"steps:         {result.steps} ({result.action_mode} actions)")
    print(f"wall time:     {result.wall_time_s}s")
    print(f"tokens:        {result.usage.total_tokens} (${result.usage.cost_usd:.4f})")
    print(f"files changed: {', '.join(result.files_changed) or '(none)'}")
    print(f"working copy:  {workdir}")
    print(f"trace:         {trace_path}")
    print("\n--- diff for human review ---")
    print(result.diff)
    return 0 if result.solved else 1


__all__ = ["main", "CHEAP_MODEL"]

if __name__ == "__main__":
    raise SystemExit(main())
