"""Benchmark runner: score the agent on a suite and write a results CSV.

Examples:
    minicodex-bench                                    # mock backend, all suites
    minicodex-bench --suite custom --limit 3           # quick smoke run
    minicodex-bench --backend openai --model openai/gpt-6.1-sol
    minicodex-bench --backend openai --router jev --cascade
    minicodex-bench --backend openai --model openai/gpt-6.1-sol --max-iterations 1

Every attempt is graded against the task's *pristine* tests (copied back in
after the agent finishes), so an agent cannot pass by editing the checks.
Output: results/runs/<label>/results.csv, run_config.json and one JSONL
trace per attempt under traces/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from minicodex.agent import Agent, AgentResult
from minicodex.backends import get_backend
from minicodex.backends.base import Usage
from minicodex.dataset import REPO_ROOT, Task, load_tasks
from minicodex.guardrails import Sandbox
from minicodex.metrics import failure_taxonomy, router_stats, summarize_rows
from minicodex.router import (
    CHEAP_MODEL,
    DEFAULT_CONFIDENCE_THRESHOLD,
    STRONG_MODEL,
    RouteDecision,
    Router,
    make_router,
)
from minicodex.tools import ToolBox
from minicodex.trace import TraceLogger

RESULTS_DIR = REPO_ROOT / "results" / "runs"

COLUMNS = [
    "run",
    "suite",
    "task",
    "difficulty",
    "category",
    "repeat",
    "backend",
    "model",
    "models_used",
    "router",
    "route_tier",
    "route_source",
    "router_choice",
    "router_confidence",
    "router_p_cheap",
    "router_p_strong",
    "router_latency_ms",
    "router_cost_usd",
    "escalated",
    "solved",
    "agent_reported_solved",
    "failure_reason",
    "stop_reason",
    "iterations",
    "max_iterations",
    "steps",
    "test_runs",
    "invalid_actions",
    "guardrail_blocks",
    "api_retries",
    "action_mode",
    "wall_time_s",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "cost_usd",
    "cost_source",
    "files_changed",
    "changed_paths",
    "error",
]


@dataclass
class RunConfig:
    backend: str = "mock"
    model: str | None = None  # used when router is "none" and no cascade
    cheap_model: str = CHEAP_MODEL
    strong_model: str = STRONG_MODEL
    router: str = "none"
    cascade: bool = False
    cascade_after: int = 2
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_iterations: int = 6
    suite: str = "all"
    limit: int | None = None
    repeat: int = 1
    workers: int = 1
    reasoning_effort: str | None = None
    action_mode: str = "auto"
    max_cost_usd: float | None = None
    label: str = ""

    def resolved_model(self) -> str:
        if self.backend == "mock":
            return self.model or "mock-strong"
        return self.model or os.environ.get("MINICODEX_MODEL") or self.strong_model


def default_label(cfg: RunConfig) -> str:
    if cfg.router != "none" or cfg.cascade:
        name = f"{cfg.router}" + ("_cascade" if cfg.cascade else "")
    else:
        name = cfg.resolved_model().split("/")[-1]
    if cfg.max_iterations == 1:
        name += "_noretry"
    label = f"{cfg.backend}_{name}_{cfg.suite}"
    if cfg.limit:
        label += f"_limit{cfg.limit}"
    if cfg.repeat > 1:
        label += f"_x{cfg.repeat}"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", label)


def resolve_run(backend_name: str | None, model: str | None) -> tuple[str, str, str]:
    """(backend, model, filename-safe label); kept for scripts and tests."""
    cfg = RunConfig(
        backend=(backend_name or os.environ.get("MINICODEX_BACKEND") or "mock").lower(), model=model
    )
    resolved = cfg.resolved_model() if cfg.backend != "mock" else "rule-playbook"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", resolved).strip("-")
    label = cfg.backend if cfg.backend == "mock" else f"{cfg.backend}_{safe}"
    return cfg.backend, resolved, label


def grade(task: Task, workdir: Path) -> bool:
    """Re-run the task's original tests against the agent's working copy."""
    original_tests = task.repo / "tests"
    if original_tests.is_dir():
        shutil.rmtree(workdir / "tests", ignore_errors=True)
        shutil.copytree(original_tests, workdir / "tests")
    for name in ("conftest.py",):
        if (task.repo / name).exists():
            shutil.copy2(task.repo / name, workdir / name)
    return ToolBox(Sandbox(workdir)).run_tests().passed


def _attempt(
    task: Task, cfg: RunConfig, model: str, max_iterations: int, trace: TraceLogger
) -> tuple[AgentResult, bool]:
    workdir = Path(tempfile.mkdtemp(prefix=f"minicodex-{task.name}-")) / "repo"
    shutil.copytree(task.repo, workdir)
    try:
        backend = get_backend(cfg.backend, model=model, reasoning_effort=cfg.reasoning_effort)
        agent = Agent(
            backend=backend, max_iterations=max_iterations, action_mode=cfg.action_mode, trace=trace
        )
        result = agent.run(workdir, task.issue)
        passed = grade(task, workdir)
        trace.log("graded", model=model, passed=passed)
        return result, passed
    finally:
        shutil.rmtree(workdir.parent, ignore_errors=True)


def run_task(
    task: Task, cfg: RunConfig, router: Router, repeat: int, trace_dir: Path, label: str
) -> dict[str, Any]:
    suffix = f"_r{repeat}" if cfg.repeat > 1 else ""
    trace = TraceLogger(trace_dir / task.suite / f"{task.name}{suffix}.jsonl")
    decision: RouteDecision = router.route(task.issue, task.repo)
    if cfg.router == "none":
        tier = "cheap" if cfg.cascade else "fixed"
        first_model = cfg.cheap_model if cfg.cascade else cfg.resolved_model()
    else:
        tier, first_model = decision.tier, decision.model
    if cfg.backend == "mock" and first_model in (cfg.cheap_model, cfg.strong_model):
        first_model = "mock-cheap" if first_model == cfg.cheap_model else "mock-strong"
    trace.log("route", **decision.to_dict(), effective_model=first_model)

    escalate_possible = cfg.cascade and tier == "cheap"
    first_budget = (
        min(cfg.cascade_after, cfg.max_iterations) if escalate_possible else cfg.max_iterations
    )
    usage = Usage()
    result, passed = _attempt(task, cfg, first_model, first_budget, trace)
    usage.add(result.usage)
    models_used = [first_model]
    iterations, steps, wall = result.iterations, result.steps, result.wall_time_s
    tests, invalid, blocks = result.test_runs, result.invalid_actions, result.guardrail_blocks
    escalated = False
    if escalate_possible and not passed:
        strong = "mock-strong" if cfg.backend == "mock" else cfg.strong_model
        trace.log(
            "escalate",
            from_model=first_model,
            to_model=strong,
            reason=result.failure_reason or "tests failed",
        )
        escalated = True
        result, passed = _attempt(task, cfg, strong, cfg.max_iterations, trace)
        usage.add(result.usage)
        models_used.append(strong)
        iterations += result.iterations
        steps += result.steps
        wall += result.wall_time_s
        tests += result.test_runs
        invalid += result.invalid_actions
        blocks += result.guardrail_blocks

    failure = "" if passed else (result.failure_reason or "wrong_fix")
    probs = decision.probabilities
    return {
        "run": label,
        "suite": task.suite,
        "task": task.name,
        "difficulty": task.difficulty,
        "category": task.category,
        "repeat": repeat,
        "backend": cfg.backend,
        "model": models_used[-1],
        "models_used": ">".join(models_used),
        "router": cfg.router,
        "route_tier": tier,
        "route_source": decision.source,
        "router_choice": decision.choice,
        "router_confidence": "" if decision.confidence is None else round(decision.confidence, 4),
        "router_p_cheap": probs.get("cheap", ""),
        "router_p_strong": probs.get("strong", ""),
        "router_latency_ms": decision.latency_ms,
        "router_cost_usd": round(decision.cost_usd, 8),
        "escalated": escalated,
        "solved": passed,
        "agent_reported_solved": result.solved,
        "failure_reason": failure,
        "stop_reason": result.stop_reason,
        "iterations": iterations,
        "max_iterations": cfg.max_iterations,
        "steps": steps,
        "test_runs": tests,
        "invalid_actions": invalid,
        "guardrail_blocks": blocks,
        "api_retries": usage.api_retries,
        "action_mode": result.action_mode,
        "wall_time_s": round(wall, 2),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": round(usage.cost_usd + decision.cost_usd, 6),
        "cost_source": usage.cost_source if cfg.backend != "mock" else "free",
        "files_changed": len(result.files_changed),
        "changed_paths": ";".join(result.files_changed),
        "error": result.error or decision.error,
    }


def run_benchmark(cfg: RunConfig, output_dir: str | Path | None = None) -> list[dict[str, Any]]:
    label = cfg.label or default_label(cfg)
    out_dir = Path(output_dir) if output_dir else RESULTS_DIR / label
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = out_dir / "traces"
    if trace_dir.exists():
        shutil.rmtree(trace_dir)
    tasks = load_tasks(cfg.suite, limit=cfg.limit)
    router = make_router(
        cfg.router,
        cheap_model=cfg.cheap_model,
        strong_model=cfg.strong_model,
        confidence_threshold=cfg.confidence_threshold,
        offline=cfg.backend == "mock",
        default_model=cfg.resolved_model(),
    )
    (out_dir / "run_config.json").write_text(
        json.dumps(
            {
                **asdict(cfg),
                "label": label,
                "tasks": len(tasks),
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"run {label}: {len(tasks)} task(s) x {cfg.repeat} repeat(s), "
        f"backend={cfg.backend} router={cfg.router} cascade={cfg.cascade} "
        f"max_iterations={cfg.max_iterations}",
        flush=True,
    )
    jobs = [(t, r) for r in range(1, cfg.repeat + 1) for t in tasks]
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()
    spent = 0.0
    stop = threading.Event()

    def job(task: Task, rep: int) -> dict[str, Any] | None:
        if stop.is_set():
            return None
        return run_task(task, cfg, router, rep, trace_dir, label)

    with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
        futures = [pool.submit(job, t, r) for t, r in jobs]
        for fut in as_completed(futures):
            row = fut.result()
            if row is None:
                continue
            with lock:
                rows.append(row)
                spent += float(row["cost_usd"])
                status = "SOLVED" if row["solved"] else f"failed ({row['failure_reason']})"
                print(
                    f"[{len(rows):3d}/{len(jobs)}] {row['suite']}/{row['task']}"
                    f" r{row['repeat']} via {row['models_used']}: {status}, "
                    f"{row['iterations']} it, {row['wall_time_s']}s, "
                    f"${float(row['cost_usd']):.4f} (total ${spent:.3f})",
                    flush=True,
                )
                if cfg.max_cost_usd is not None and spent >= cfg.max_cost_usd:
                    if not stop.is_set():
                        print(
                            f"cost cap ${cfg.max_cost_usd} reached; not starting new tasks",
                            flush=True,
                        )
                    stop.set()

    order = {(t.suite, t.name): i for i, t in enumerate(tasks)}
    rows.sort(key=lambda r: (r["repeat"], order[(r["suite"], r["task"])]))
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print_summary(rows)
    print(f"results: {out_dir / 'results.csv'}\ntraces:  {trace_dir}/")
    return rows


def print_summary(rows: list[dict[str, Any]]) -> None:
    suites = sorted({r["suite"] for r in rows})
    for suite in [*suites, "all"]:
        subset = rows if suite == "all" else [r for r in rows if r["suite"] == suite]
        if not subset or (suite == "all" and len(suites) == 1):
            continue
        s = summarize_rows(subset)
        print(
            f"{suite:13s} pass@1 {s['solved']}/{s['n']} = {100 * s['pass_at_1']:.1f}% "
            f"[95% CI {100 * s['ci_low']:.1f}-{100 * s['ci_high']:.1f}]  "
            f"iters {s['mean_iterations']:.2f}  time {s['mean_wall_time_s']:.1f}s  "
            f"cost ${s['total_cost_usd']:.4f}  per solved ${s['cost_per_solved_usd']:.4f}"
        )
    tax = failure_taxonomy(rows)
    if tax:
        print("failures:", ", ".join(f"{k}={v}" for k, v in tax.most_common()))
    rs = router_stats(rows)
    if rs:
        print(
            f"router: tiers={rs['tiers']} sources={rs['sources']} "
            f"escalated={rs['escalated']} mean latency {rs['mean_latency_ms']:.0f} ms"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="G6 Unit benchmark runner")
    p.add_argument(
        "--backend",
        default=os.environ.get("MINICODEX_BACKEND", "mock"),
        help="mock (default, offline) or openai",
    )
    p.add_argument(
        "--model", default=None, help="model id when not routing, e.g. openai/gpt-6.1-sol"
    )
    p.add_argument("--suite", default="all", choices=["custom", "humanevalfix", "all"])
    p.add_argument("--limit", type=int, default=None, help="first N tasks per suite")
    p.add_argument(
        "--max-iterations",
        type=int,
        default=int(os.environ.get("MINICODEX_MAX_ITERATIONS", 6)),
        help="edit-and-test attempts per task (1 = no-retry baseline)",
    )
    p.add_argument("--router", default="none", choices=["none", "jev", "heuristic"])
    p.add_argument(
        "--cascade",
        action="store_true",
        help="start on the cheap model; escalate to strong on failure",
    )
    p.add_argument(
        "--cascade-after",
        type=int,
        default=2,
        help="cheap-model iterations before escalating (default 2)",
    )
    p.add_argument("--cheap-model", default=CHEAP_MODEL)
    p.add_argument("--strong-model", default=STRONG_MODEL)
    p.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="below this router confidence, use the strong model",
    )
    p.add_argument("--repeat", type=int, default=1, help="repeat runs for reliability")
    p.add_argument("--workers", type=int, default=1, help="tasks run in parallel")
    p.add_argument(
        "--reasoning-effort",
        default=os.environ.get("MINICODEX_REASONING_EFFORT"),
        help="reasoning effort for reasoning models (e.g. low)",
    )
    p.add_argument("--action-mode", default="auto", choices=["auto", "tools", "json"])
    p.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="stop starting new tasks once this many USD are spent",
    )
    p.add_argument("--tag", default="", help="run label (default: derived from flags)")
    p.add_argument("--output-dir", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = RunConfig(
        backend=args.backend.lower(),
        model=args.model,
        cheap_model=args.cheap_model,
        strong_model=args.strong_model,
        router=args.router,
        cascade=args.cascade,
        cascade_after=args.cascade_after,
        confidence_threshold=args.confidence_threshold,
        max_iterations=args.max_iterations,
        suite=args.suite,
        limit=args.limit,
        repeat=args.repeat,
        workers=args.workers,
        reasoning_effort=args.reasoning_effort,
        action_mode=args.action_mode,
        max_cost_usd=args.max_cost,
        label=args.tag,
    )
    rows = run_benchmark(cfg, args.output_dir)
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
