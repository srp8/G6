"""Evaluation statistics used by the benchmark summary and the notebook."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

Z_95 = 1.959963984540054


def wilson_ci(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (Wilson, 1927).

    Better behaved than the normal approximation for small n and for rates
    near 0 or 1, which is exactly the regime of a 38-task benchmark.
    """
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes")


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def summarize_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Headline metrics for a set of task attempts (one row = one attempt)."""
    n = len(rows)
    solved = sum(_truthy(r["solved"]) for r in rows)
    lo, hi = wilson_ci(solved, n)
    cost = sum(_num(r.get("cost_usd")) for r in rows)
    return {
        "n": n,
        "solved": solved,
        "pass_at_1": solved / n if n else 0.0,
        "ci_low": lo,
        "ci_high": hi,
        "mean_iterations": sum(_num(r["iterations"]) for r in rows) / n if n else 0.0,
        "mean_wall_time_s": sum(_num(r["wall_time_s"]) for r in rows) / n if n else 0.0,
        "mean_tokens": sum(_num(r["total_tokens"]) for r in rows) / n if n else 0.0,
        "total_cost_usd": cost,
        "cost_per_solved_usd": cost / solved if solved else float("nan"),
    }


def failure_taxonomy(rows: Iterable[dict[str, Any]]) -> Counter[str]:
    return Counter(
        r["failure_reason"] for r in rows if not _truthy(r["solved"]) and r.get("failure_reason")
    )


def reliability(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Repeat-run consistency: share of tasks with the same outcome every run."""
    by_task: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for r in rows:
        by_task[(r["suite"], r["task"])].append(_truthy(r["solved"]))
    repeats = max((len(v) for v in by_task.values()), default=0)
    if repeats < 2:
        return {
            "repeats": repeats,
            "consistent_share": float("nan"),
            "per_repeat_pass_at_1": [],
            "stdev_pass_at_1": float("nan"),
        }
    consistent = sum(1 for v in by_task.values() if len(set(v)) == 1)
    per_repeat = []
    for i in range(repeats):
        outcomes = [v[i] for v in by_task.values() if len(v) > i]
        per_repeat.append(sum(outcomes) / len(outcomes))
    mean = sum(per_repeat) / len(per_repeat)
    sd = math.sqrt(sum((x - mean) ** 2 for x in per_repeat) / (len(per_repeat) - 1))
    return {
        "repeats": repeats,
        "consistent_share": consistent / len(by_task),
        "per_repeat_pass_at_1": per_repeat,
        "stdev_pass_at_1": sd,
    }


def router_stats(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    routed = [r for r in rows if r.get("router") not in (None, "", "none")]
    if not routed:
        return {}
    tiers = Counter(r["route_tier"] for r in routed)
    sources = Counter(r["route_source"] for r in routed)
    lat = [_num(r["router_latency_ms"]) for r in routed]
    conf = [_num(r["router_confidence"]) for r in routed if r.get("router_confidence") != ""]
    escalated = sum(_truthy(r.get("escalated")) for r in routed)
    cheap_first = [r for r in routed if r["route_tier"] == "cheap"]
    return {
        "tasks": len(routed),
        "tiers": dict(tiers),
        "sources": dict(sources),
        "cheap_share": tiers.get("cheap", 0) / len(routed),
        "escalated": escalated,
        "cheap_solved_without_escalation": sum(
            _truthy(r["solved"]) and not _truthy(r.get("escalated")) for r in cheap_first
        ),
        "mean_confidence": sum(conf) / len(conf) if conf else float("nan"),
        "mean_latency_ms": sum(lat) / len(lat),
        "p95_latency_ms": sorted(lat)[max(0, math.ceil(0.95 * len(lat)) - 1)],
        "router_cost_usd": sum(_num(r.get("router_cost_usd")) for r in routed),
    }
