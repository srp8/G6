"""OpenAI/OpenRouter backend with a fake SDK client (no network)."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from minicodex.backends import openai_backend
from minicodex.backends.base import ToolsUnsupportedError
from minicodex.backends.openai_backend import OpenAIBackend


def _usage(cost=None):
    extra = {} if cost is None else {"cost": cost}
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=7),
        model_extra=extra,
        cost=cost,
    )


def _response(tool=True, cost=0.0123):
    calls = (
        [
            SimpleNamespace(
                id="c1", function=SimpleNamespace(name="read_file", arguments='{"path": "a.py"}')
            )
        ]
        if tool
        else None
    )
    msg = SimpleNamespace(
        content=None if tool else '{"action": "finish"}',
        tool_calls=calls,
        model_extra={"reasoning_details": [{"type": "reasoning.summary"}]},
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=_usage(cost),
        model_extra={},
    )


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.kwargs = []

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _status_error(cls, code, headers=None):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(code, request=req, headers=headers or {})
    return cls(f"error {code}", response=resp, body=None)


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setitem(
        openai_backend._CAPS_CACHE,
        "openai/gpt-6.1-sol",
        {"tools", "structured_outputs", "reasoning"},
    )
    monkeypatch.setattr(openai_backend.time, "sleep", lambda s: None)

    def make(outcomes):
        b = OpenAIBackend(model="openai/gpt-6.1-sol", reasoning_effort="low")
        b.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(outcomes)))
        return b

    return make


def test_tool_call_request_and_parsing(backend):
    b = backend([_response()])
    out = b.complete([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    sent = b.client.chat.completions.kwargs[0]
    assert sent["tool_choice"] == "required" and sent["parallel_tool_calls"] is False
    assert sent["extra_body"] == {"reasoning": {"effort": "low"}}
    assert "temperature" not in sent  # model does not list temperature
    assert out.tool_calls[0].name == "read_file" and out.tool_calls[0].arguments == {"path": "a.py"}
    assert out.message["tool_calls"][0]["id"] == "c1"
    assert out.message["reasoning_details"]  # preserved for the next turn
    assert out.usage.cost_usd == pytest.approx(0.0123) and out.usage.cost_source == "reported"
    assert out.usage.reasoning_tokens == 7


def test_cost_falls_back_to_price_table(backend):
    b = backend([_response(cost=None)])
    out = b.complete([{"role": "user", "content": "hi"}])
    assert out.usage.cost_source == "estimated"
    assert out.usage.cost_usd == pytest.approx((100 * 2.0 + 20 * 10.0) / 1e6)


def test_retries_429_and_5xx_then_succeeds(backend):
    b = backend(
        [
            _status_error(openai.RateLimitError, 429, {"retry-after": "1"}),
            _status_error(openai.InternalServerError, 502),
            _response(),
        ]
    )
    out = b.complete([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert out.usage.api_retries == 2


def test_gives_up_after_max_attempts(backend):
    b = backend([_status_error(openai.InternalServerError, 503)] * 6)
    with pytest.raises(openai.InternalServerError):
        b.complete([{"role": "user", "content": "hi"}])


def test_auth_errors_are_not_retried(backend):
    b = backend([_status_error(openai.AuthenticationError, 401), _response()])
    with pytest.raises(openai.AuthenticationError):
        b.complete([{"role": "user", "content": "hi"}])
    assert len(b.client.chat.completions.kwargs) == 1


def test_tool_rejection_raises_tools_unsupported(backend):
    err = _status_error(openai.BadRequestError, 400)
    err.message = "tools are not supported for this model"
    b = backend(
        [openai.BadRequestError("tools are not supported", response=err.response, body=None)]
    )
    with pytest.raises(ToolsUnsupportedError):
        b.complete([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])


def test_backoff_honors_retry_after():
    err = _status_error(openai.RateLimitError, 429, {"retry-after": "3"})
    assert openai_backend._backoff_delay(1, err) == 3.0
    assert 0.5 <= openai_backend._backoff_delay(1, RuntimeError()) <= 1.0


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIBackend()
