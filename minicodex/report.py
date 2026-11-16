"""Summarize every run under results/runs/ into results/summary.md (+ CSV).

    minicodex-report                  # or: python -m minicodex.report
    minicodex-report --runs results/runs --out results

Per run and suite: pass@1 with a Wilson 95% CI, mean iterations, time and
tokens, total cost and cost per solved task. Also the failure taxonomy,
router statistics, repeat-run reliability, and the no-retry vs full-loop gain
(a run with --max-iterations 1 is paired with the full-loop run of the same
model).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from minicodex.dataset import REPO_ROOT
from minicodex.metrics import failure_taxonomy, reliability, router_stats, summarize_rows

FAILURES = ("wrong_fix", "budget_exhausted", "invalid_action", "guardrail_block", "api_error")


def load_runs(runs_dir: Path) -> dict[str, list[dict[str, Any]]]:
    runs: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(runs_dir.glob("*/results.csv")):
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            runs[path.parent.name] = rows
    return runs


def _pct(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}%"


def _usd(x: float) -> str:
    return "n/a" if math.isnan(x) else f"${x:.4f}"


def suite_table(runs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for label, rows in runs.items():
        suites = sorted({r["suite"] for r in rows})
        for suite in [*suites, "all"]:
            subset = rows if suite == "all" else [r for r in rows if r["suite"] == suite]
            s = summarize_rows(subset)
            out.append({"run": label, "suite": suite, **s})
    return out


def retry_pairs(runs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Pair each no-retry run with the full-loop run of the same single model."""

    def key(rows: list[dict[str, Any]]) -> tuple[str, str]:
        r = rows[0]
        return r["backend"], r["models_used"] if r["router"] == "none" else ""

    full = {
        key(rows): (label, rows)
        for label, rows in runs.items()
        if rows[0]["max_iterations"] != "1"
        and rows[0]["router"] == "none"
        and ">" not in rows[0]["models_used"]
    }
    pairs = []
    for label, rows in runs.items():
        if rows[0]["max_iterations"] != "1" or key(rows) not in full:
            continue
        full_label, full_rows = full[key(rows)]
        for suite in sorted({r["suite"] for r in rows}) + ["all"]:
            nr = [r for r in rows if suite in ("all", r["suite"])]
            fl = [r for r in full_rows if suite in ("all", r["suite"])]
            nr_solved = {r["task"] for r in nr if r["solved"] == "True"}
            fl_solved = {r["task"] for r in fl if r["solved"] == "True"}
            a, b = summarize_rows(nr), summarize_rows(fl)
            pairs.append(
                {
                    "suite": suite,
                    "no_retry_run": label,
                    "full_run": full_label,
                    "no_retry_pass": a["pass_at_1"],
                    "full_pass": b["pass_at_1"],
                    "gain_pp": 100 * (b["pass_at_1"] - a["pass_at_1"]),
                    "rescued_by_retry": len(fl_solved - nr_solved),
                    "lost_with_retry": len(nr_solved - fl_solved),
                    "no_retry_cost": a["total_cost_usd"],
                    "full_cost": b["total_cost_usd"],
                }
            )
    return pairs


def render(runs: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# Benchmark summary",
        "",
        "Written by `minicodex-report` from `results/runs/*/results.csv`. "
        "pass@1 is the share of task attempts solved by a single agent run (no "
        "best-of-k), graded against the pristine tests; with --repeat 3 each task "
        "counts three times. The interval is a Wilson 95% CI. Cost is "
        "OpenRouter's reported billed cost (plus the Jev router's per-token "
        "price where used).",
        "",
    ]
    lines += [
        "## Results by run and suite",
        "",
        "| run | suite | solved | pass@1 | 95% CI | mean iters | mean time (s) "
        "| mean tokens | total cost | cost / solved |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in suite_table(runs):
        lines.append(
            f"| {t['run']} | {t['suite']} | {t['solved']}/{t['n']} | {_pct(t['pass_at_1'])} "
            f"| {_pct(t['ci_low'])}–{_pct(t['ci_high'])} | {t['mean_iterations']:.2f} "
            f"| {t['mean_wall_time_s']:.1f} | {t['mean_tokens']:,.0f} "
            f"| {_usd(t['total_cost_usd'])} | {_usd(t['cost_per_solved_usd'])} |"
        )
    lines += [
        "",
        "## Failure taxonomy (unsolved attempts)",
        "",
        "| run | " + " | ".join(FAILURES) + " |",
        "|---|" + "---|" * len(FAILURES),
    ]
    for label, rows in runs.items():
        tax = failure_taxonomy(rows)
        lines.append(f"| {label} | " + " | ".join(str(tax.get(k, 0)) for k in FAILURES) + " |")
    pairs = retry_pairs(runs)
    if pairs:
        lines += [
            "",
            "## Retry loop vs no-retry baseline",
            "",
            "| suite | no-retry run | full-loop run | no-retry pass@1 | full pass@1 "
            "| gain (pp) | rescued by retry | cost no-retry | cost full |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for p in pairs:
            lines.append(
                f"| {p['suite']} | {p['no_retry_run']} | {p['full_run']} "
                f"| {_pct(p['no_retry_pass'])} | {_pct(p['full_pass'])} "
                f"| {p['gain_pp']:+.1f} | {p['rescued_by_retry']} "
                f"| {_usd(p['no_retry_cost'])} | {_usd(p['full_cost'])} |"
            )
    routed = {k: v for k, v in runs.items() if router_stats(v)}
    if routed:
        lines += [
            "",
            "## Router decisions",
            "",
            "| run | tasks | cheap-first | strong | sources | escalated "
            "| cheap solved w/o escalation | mean confidence | mean / p95 latency "
            "| router cost |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for label, rows in routed.items():
            rs = router_stats(rows)
            lines.append(
                f"| {label} | {rs['tasks']} | {rs['tiers'].get('cheap', 0)} "
                f"| {rs['tiers'].get('strong', 0)} | {json.dumps(rs['sources'])} "
                f"| {rs['escalated']} | {rs['cheap_solved_without_escalation']} "
                f"| {rs['mean_confidence']:.2f} | {rs['mean_latency_ms']:.0f} / "
                f"{rs['p95_latency_ms']:.0f} ms | ${rs['router_cost_usd']:.6f} |"
            )
    rel = {k: reliability(v) for k, v in runs.items()}
    rel = {k: v for k, v in rel.items() if v["repeats"] >= 2}
    if rel:
        lines += [
            "",
            "## Reliability (repeat runs)",
            "",
            "| run | repeats | pass@1 per repeat | stdev | same outcome every repeat |",
            "|---|---|---|---|---|",
        ]
        for label, r in rel.items():
            per = ", ".join(_pct(x) for x in r["per_repeat_pass_at_1"])
            lines.append(
                f"| {label} | {r['repeats']} | {per} | "
                f"{100 * r['stdev_pass_at_1']:.1f} pp | {_pct(r['consistent_share'])} |"
            )
    total = sum(float(r["cost_usd"]) for rows in runs.values() for r in rows)
    lines += ["", f"Total cost across all runs: **${total:.4f}**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", default=str(REPO_ROOT / "results" / "runs"))
    p.add_argument("--out", default=str(REPO_ROOT / "results"))
    p.add_argument(
        "--include", nargs="*", default=None, help="only these run labels (default: all)"
    )
    args = p.parse_args(argv)
    runs = load_runs(Path(args.runs))
    if args.include:
        runs = {k: v for k, v in runs.items() if k in args.include}
    if not runs:
        print("no runs found")
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text(render(runs), encoding="utf-8")
    table = suite_table(runs)
    with (out / "summary_by_suite.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    print(f"wrote {out / 'summary.md'} and {out / 'summary_by_suite.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
