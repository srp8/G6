"""Routers: heuristic, Jev (mocked HTTP and fake client) and fallbacks."""

from pathlib import Path

import httpx
import pytest

from minicodex.router import (
    CHEAP_MODEL,
    QUESTION_ID,
    STRONG_MODEL,
    FakeJevClient,
    HeuristicRouter,
    HttpJevClient,
    JevRouter,
    make_router,
)

CUSTOM = Path(__file__).resolve().parent.parent / "benchmark" / "suites" / "custom"


def _task(name):
    d = CUSTOM / name
    return (d / "issue.md").read_text(), d / "repo"


class StubClient:
    def __init__(self, choice="cheap", confidence=0.9, probs=None, exc=None):
        self.answer = {
            "type": "choice",
            "choice": choice,
            "confidence": confidence,
            "probabilities": probs or {"cheap": 0.95, "strong": 0.05},
        }
        self.exc = exc
        self.payloads = []

    def system_one(self, payload):
        self.payloads.append(payload)
        if self.exc:
            raise self.exc
        return {
            "model": "jev-1.14.0",
            "answers": {QUESTION_ID: self.answer},
            "usage": {"input_tokens": 1000, "output_tokens": 1},
        }


def test_heuristic_sends_single_file_bug_to_cheap():
    d = HeuristicRouter().route(*_task("01_off_by_one"))
    assert d.tier == "cheap" and d.model == CHEAP_MODEL and d.source == "heuristic"


def test_heuristic_sends_two_file_bug_to_strong():
    d = HeuristicRouter().route(*_task("04_two_file_bug"))
    assert d.tier == "strong" and d.model == STRONG_MODEL


def test_jev_payload_follows_systemone_schema():
    client = StubClient()
    JevRouter(client).route(*_task("01_off_by_one"))
    payload = client.payloads[0]
    assert payload["model"] == "jev-latest"
    q = payload["questions"][QUESTION_ID]
    assert q["type"] == "choice" and set(q["criteria"]) == {"cheap", "strong"}
    assert "mathutils.py" in payload["state"]["source_code"]
    assert "API_KEY" not in str(payload)  # the decoy .env is never sent


def test_jev_confident_cheap_is_used():
    d = JevRouter(StubClient("cheap", 0.9)).route(*_task("01_off_by_one"))
    assert (d.tier, d.source, d.router) == ("cheap", "jev", "jev")
    assert d.probabilities["cheap"] == 0.95
    assert d.input_tokens == 1000 and d.cost_usd == pytest.approx(1000 * 0.042 / 1e6)


def test_jev_low_confidence_falls_back_to_strong():
    d = JevRouter(StubClient("cheap", 0.3), confidence_threshold=0.6).route(*_task("01_off_by_one"))
    assert d.choice == "cheap" and d.tier == "strong" and d.source == "low_confidence"


def test_threshold_is_configurable():
    d = JevRouter(StubClient("cheap", 0.3), confidence_threshold=0.2).route(*_task("01_off_by_one"))
    assert d.tier == "cheap"


def test_jev_error_falls_back_to_heuristic():
    d = JevRouter(StubClient(exc=RuntimeError("boom"))).route(*_task("01_off_by_one"))
    assert d.source == "heuristic_fallback" and "boom" in d.error
    assert d.tier == "cheap"


def test_missing_key_uses_heuristic(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    router = JevRouter()
    assert router.client is None
    d = router.route(*_task("04_two_file_bug"))
    assert d.source == "heuristic_fallback" and d.tier == "strong"


def test_fake_jev_is_deterministic():
    a = JevRouter(FakeJevClient()).route(*_task("04_two_file_bug"))
    b = JevRouter(FakeJevClient()).route(*_task("04_two_file_bug"))
    assert a.probabilities == b.probabilities and a.tier == "strong"


def test_make_router_offline_uses_fake_client():
    router = make_router("jev", offline=True)
    assert isinstance(router.client, FakeJevClient)
    assert make_router("none", default_model="m").route("x", CUSTOM).model == "m"
    with pytest.raises(ValueError):
        make_router("bogus")


def _route_httpx_to(monkeypatch, handler):
    """Send httpx.post through an in-memory transport (no network)."""
    client = httpx.Client(transport=httpx.MockTransport(handler))

    def fake_post(url, **kwargs):
        kwargs.pop("timeout", None)
        return client.post(url, **kwargs)

    monkeypatch.setattr(httpx, "post", fake_post)


def test_http_client_parses_response_and_retries(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"detail": "busy"})
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    QUESTION_ID: {
                        "type": "choice",
                        "choice": "strong",
                        "confidence": 0.8,
                        "probabilities": {"cheap": 0.1, "strong": 0.9},
                    }
                },
                "usage": {"input_tokens": 50, "output_tokens": 1},
            },
        )

    _route_httpx_to(monkeypatch, handler)
    monkeypatch.setattr("minicodex.router.time.sleep", lambda s: None)
    client = HttpJevClient(api_key="test-key")
    d = JevRouter(client).route(*_task("01_off_by_one"))
    assert len(calls) == 2
    assert d.tier == "strong" and d.source == "jev" and d.latency_ms >= 0


def test_http_client_raises_on_client_error(monkeypatch):
    _route_httpx_to(monkeypatch, lambda r: httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(RuntimeError, match="401"):
        HttpJevClient(api_key="x").system_one({"model": "jev-latest"})
