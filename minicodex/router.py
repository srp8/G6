"""Model routing: send easy bugs to a cheap model and hard ones to a strong one.

Three routers share one interface, ``route(issue, repo_dir) -> RouteDecision``:

- ``none``: no routing; the caller picks the model.
- ``heuristic``: offline rules on the issue text and repo size. Free,
  deterministic, and the fallback whenever Jev is unavailable.
- ``jev``: TypeSafe's Jev System One model answers one typed Choice question
  ("cheap" or "strong") and returns per-option probabilities plus a
  confidence. Following TypeSafe's "routing by confidence" pattern, the cheap
  model is used only when Jev picks it *and* its confidence clears a
  threshold; otherwise the task goes to the strong model.

API: POST https://api.typesafe.ai/v1/systemone with
``{"model": "jev-latest", "state": ..., "questions": {...}}`` and
``Authorization: Bearer $TYPESAFE_API_KEY`` (see docs/REFERENCES.md).
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

CHEAP_MODEL = "openai/gpt-5.6-luna"
STRONG_MODEL = "openai/gpt-6.1-sol"
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_PRICE_PER_M_INPUT = 0.042  # USD; Jev bills input tokens only
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

QUESTION_ID = "model_tier"
JEV_QUESTION: dict[str, Any] = {
    "type": "choice",
    "instructions": (
        "An AI coding agent must fix the bug described in this issue so the "
        "repository's unit tests pass. Which model tier should it use?"
    ),
    "criteria": {
        "cheap": (
            "A small, fast, low-cost model. Right for a localized bug in one short "
            "function whose expected behavior the issue states clearly: an "
            "off-by-one, a wrong operator, comparison or constant, a missing edge "
            "case, a swapped variable."
        ),
        "strong": (
            "A frontier reasoning model costing about ten times more. Needed when "
            "the fix spans several files or functions, requires implementing new "
            "behavior, involves subtle algorithmic logic (parsing, date or number "
            "handling, search, recursion, combinatorics), or the specification is "
            "ambiguous."
        ),
    },
}


@dataclass
class RouteDecision:
    """Which model tier to use for a task, and why."""

    tier: str  # "cheap" | "strong"
    model: str
    router: str  # none | heuristic | jev
    source: str  # none | heuristic | jev | heuristic_fallback | low_confidence
    choice: str = ""  # the router's raw pick before the confidence rule
    confidence: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    input_tokens: int = 0
    cost_usd: float = 0.0
    reason: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Router(Protocol):
    name: str

    def route(self, issue: str, repo_dir: Path) -> RouteDecision: ...


# --------------------------------------------------------------- features
def repo_features(issue: str, repo_dir: Path) -> dict[str, Any]:
    """Cheap, explainable signals about how hard a task looks."""
    sources = [
        p
        for p in sorted(Path(repo_dir).rglob("*.py"))
        if "tests" not in p.relative_to(repo_dir).parts
        and not p.name.startswith("test_")
        and p.name != "conftest.py"
    ]
    lines = 0
    functions = 0
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines += sum(1 for ln in text.splitlines() if ln.strip())
        functions += text.count("\ndef ") + text.startswith("def ")
    low = issue.lower()
    return {
        "source_files": [str(p.relative_to(repo_dir)) for p in sources],
        "n_source_files": len(sources),
        "source_lines": lines,
        "functions": functions,
        "issue_words": len(issue.split()),
        "mentions_multiple": any(
            w in low for w in ("two problems", "span", "both", "multiple", "several")
        ),
        "feature_request": any(w in low for w in ("feature", "implement", "add a", "new function")),
    }


def _source_excerpt(repo_dir: Path, files: list[str], limit: int = 6000) -> str:
    parts = []
    for rel in files:
        text = (Path(repo_dir) / rel).read_text(encoding="utf-8", errors="replace")
        parts.append(f"# file: {rel}\n{text}")
    joined = "\n\n".join(parts)
    return joined[:limit]


# ---------------------------------------------------------------- routers
class NoRouter:
    name = "none"

    def __init__(self, model: str = STRONG_MODEL):
        self.model = model

    def route(self, issue: str, repo_dir: Path) -> RouteDecision:
        return RouteDecision(
            tier="fixed", model=self.model, router="none", source="none", reason="routing disabled"
        )


class HeuristicRouter:
    """Offline rule-based router; also the fallback when Jev is unavailable."""

    name = "heuristic"

    def __init__(
        self,
        cheap_model: str = CHEAP_MODEL,
        strong_model: str = STRONG_MODEL,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        self.cheap_model = cheap_model
        self.strong_model = strong_model
        self.confidence_threshold = confidence_threshold

    def score(self, f: dict[str, Any]) -> float:
        s = 0.0
        s += 2.0 if f["n_source_files"] >= 2 else 0.0
        s += 1.0 if f["source_lines"] > 30 else 0.0
        s += 1.0 if f["functions"] >= 3 else 0.0
        s += 1.5 if f["mentions_multiple"] else 0.0
        s += 1.0 if f["feature_request"] else 0.0
        s += 0.5 if f["issue_words"] > 120 else 0.0
        return s

    def route(
        self, issue: str, repo_dir: Path, source: str = "heuristic", error: str = ""
    ) -> RouteDecision:
        start = time.perf_counter()
        f = repo_features(issue, repo_dir)
        s = self.score(f)
        p_strong = 1.0 / (1.0 + math.exp(-(s - 1.5) * 1.5))
        probs = {"cheap": round(1 - p_strong, 4), "strong": round(p_strong, 4)}
        choice = max(probs, key=lambda k: probs[k])
        confidence = round(abs(p_strong - 0.5) * 2, 4)
        return _apply_threshold(
            choice,
            probs,
            confidence,
            self.confidence_threshold,
            self.cheap_model,
            self.strong_model,
            router="heuristic",
            source=source,
            latency_ms=(time.perf_counter() - start) * 1000,
            reason=(
                f"score={s:.1f} (files={f['n_source_files']}, "
                f"lines={f['source_lines']}, functions={f['functions']})"
            ),
            error=error,
        )


class JevClient(Protocol):
    def system_one(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpJevClient:
    """Minimal HTTP client for POST /v1/systemone with retry on 429/5xx."""

    def __init__(
        self,
        api_key: str | None = None,
        url: str = TYPESAFE_URL,
        timeout_s: float = 20.0,
        max_attempts: int = 4,
    ):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set")
        self.url = url
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts

    def system_one(self, payload: dict[str, Any]) -> dict[str, Any]:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = httpx.post(self.url, json=payload, headers=headers, timeout=self.timeout_s)
            except httpx.TransportError:
                if attempt == self.max_attempts:
                    raise
                time.sleep(min(8.0, 0.5 * 2**attempt))
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_attempts:
                wait = resp.headers.get("retry-after")
                time.sleep(float(wait) if wait and wait.isdigit() else min(8.0, 0.5 * 2**attempt))
                continue
            if resp.status_code >= 400:
                # Never echo request headers; the body has no credentials.
                raise RuntimeError(f"TypeSafe API {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        raise RuntimeError("TypeSafe API: retries exhausted")  # pragma: no cover


class FakeJevClient:
    """Deterministic offline stand-in for Jev (mock runs and tests).

    Returns a response in the real API shape, with probabilities derived from
    the heuristic score so that mock-mode routing is stable and explainable.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def system_one(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        state = payload["state"]
        f = state["repository"]
        s = HeuristicRouter().score(
            {
                "n_source_files": f["source_file_count"],
                "source_lines": f["source_lines"],
                "functions": f["functions"],
                "mentions_multiple": f["mentions_multiple"],
                "feature_request": f["feature_request"],
                "issue_words": len(state["issue"].split()),
            }
        )
        p_strong = round(1.0 / (1.0 + math.exp(-(s - 1.5) * 2.0)), 4)
        probs = {"cheap": round(1 - p_strong, 4), "strong": p_strong}
        choice = max(probs, key=lambda k: probs[k])
        return {
            "model": "jev-fake",
            "answers": {
                QUESTION_ID: {
                    "type": "choice",
                    "choice": choice,
                    "confidence": round(abs(p_strong - 0.5) * 2, 4),
                    "probabilities": probs,
                }
            },
            "usage": {"input_tokens": len(str(state)) // 4, "output_tokens": 1},
        }


class JevRouter:
    name = "jev"

    def __init__(
        self,
        client: JevClient | None = None,
        cheap_model: str = CHEAP_MODEL,
        strong_model: str = STRONG_MODEL,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        jev_model: str = JEV_MODEL,
    ):
        self.cheap_model = cheap_model
        self.strong_model = strong_model
        self.confidence_threshold = confidence_threshold
        self.jev_model = jev_model
        self.fallback = HeuristicRouter(cheap_model, strong_model, confidence_threshold)
        self.client: JevClient | None
        self.init_error = ""
        if client is not None:
            self.client = client
        else:
            try:
                self.client = HttpJevClient()
            except RuntimeError as exc:
                self.client, self.init_error = None, str(exc)

    def build_payload(self, issue: str, repo_dir: Path) -> dict[str, Any]:
        f = repo_features(issue, repo_dir)
        return {
            "model": self.jev_model,
            "state": {
                "issue": issue,
                "repository": {
                    "source_files": f["source_files"],
                    "source_file_count": f["n_source_files"],
                    "source_lines": f["source_lines"],
                    "functions": f["functions"],
                    "mentions_multiple": f["mentions_multiple"],
                    "feature_request": f["feature_request"],
                },
                "source_code": _source_excerpt(repo_dir, f["source_files"]),
            },
            "questions": {QUESTION_ID: JEV_QUESTION},
        }

    def route(self, issue: str, repo_dir: Path) -> RouteDecision:
        if self.client is None:
            return self.fallback.route(
                issue, repo_dir, source="heuristic_fallback", error=self.init_error
            )
        payload = self.build_payload(issue, repo_dir)
        start = time.perf_counter()
        try:
            response = self.client.system_one(payload)
            answer = response["answers"][QUESTION_ID]
            probs = {k: float(v) for k, v in answer["probabilities"].items()}
            choice = str(answer["choice"])
            confidence = float(answer["confidence"])
            if choice not in ("cheap", "strong"):
                raise ValueError(f"unexpected choice {choice!r}")
        except Exception as exc:  # noqa: BLE001 - any failure: fall back offline
            return self.fallback.route(
                issue,
                repo_dir,
                source="heuristic_fallback",
                error=f"{type(exc).__name__}: {str(exc)[:200]}",
            )
        latency_ms = (time.perf_counter() - start) * 1000
        tokens = int((response.get("usage") or {}).get("input_tokens", 0))
        return _apply_threshold(
            choice,
            probs,
            confidence,
            self.confidence_threshold,
            self.cheap_model,
            self.strong_model,
            router="jev",
            source="jev",
            latency_ms=latency_ms,
            input_tokens=tokens,
            cost_usd=tokens * JEV_PRICE_PER_M_INPUT / 1e6,
            reason=f"jev model {response.get('model', '?')}",
        )


def _apply_threshold(
    choice: str,
    probs: dict[str, float],
    confidence: float,
    threshold: float,
    cheap_model: str,
    strong_model: str,
    *,
    router: str,
    source: str,
    latency_ms: float,
    reason: str,
    input_tokens: int = 0,
    cost_usd: float = 0.0,
    error: str = "",
) -> RouteDecision:
    """Use the cheap model only for a confident "cheap"; otherwise go strong."""
    tier = choice
    if confidence < threshold and choice != "strong":
        tier = "strong"
        source = "low_confidence" if source in ("jev", "heuristic") else source
        reason = f"{reason}; confidence {confidence:.2f} < {threshold:.2f} -> strong"
    return RouteDecision(
        tier=tier,
        model=cheap_model if tier == "cheap" else strong_model,
        router=router,
        source=source,
        choice=choice,
        confidence=confidence,
        probabilities=probs,
        latency_ms=round(latency_ms, 1),
        input_tokens=input_tokens,
        cost_usd=cost_usd,
        reason=reason,
        error=error,
    )


def make_router(
    name: str,
    *,
    cheap_model: str = CHEAP_MODEL,
    strong_model: str = STRONG_MODEL,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    offline: bool = False,
    default_model: str | None = None,
) -> Router:
    """Build a router. ``offline=True`` (mock runs) swaps in the fake Jev."""
    name = name.lower()
    if name == "none":
        return NoRouter(default_model or strong_model)
    if name == "heuristic":
        return HeuristicRouter(cheap_model, strong_model, confidence_threshold)
    if name == "jev":
        return JevRouter(
            FakeJevClient() if offline else None, cheap_model, strong_model, confidence_threshold
        )
    raise ValueError(f"unknown router {name!r}; use none, heuristic or jev")
