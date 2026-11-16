"""OpenAI (and OpenAI-compatible, e.g. OpenRouter) backend.

Environment variables (never commit keys -- use a local .env or your shell):

- OPENAI_API_KEY    required to use this backend.
- OPENAI_BASE_URL   optional; point at any OpenAI-compatible provider.
                    For OpenRouter: https://openrouter.ai/api/v1
- MINICODEX_MODEL   default model id (e.g. ``openai/gpt-6.1-sol`` on OpenRouter).
- MINICODEX_REASONING_EFFORT   optional reasoning effort for reasoning models
                    (low | medium | high ...); sent as OpenRouter's
                    ``reasoning.effort`` or OpenAI's ``reasoning_effort``.
- MINICODEX_INPUT_COST_PER_M / MINICODEX_OUTPUT_COST_PER_M
                    USD per million tokens, used only when the provider does
                    not report the cost itself (OpenRouter always does).

Design notes (see docs/REFERENCES.md):

- Native tool calling with strict schemas and ``parallel_tool_calls=false``
  when the model supports tools; otherwise the agent falls back to JSON
  actions, constrained by ``response_format`` json_schema when supported.
- Model capabilities come from OpenRouter's ``GET /api/v1/models``
  (``supported_parameters``); other providers are assumed to support tools.
- Transient failures (429, 5xx, timeouts, connection errors) are retried with
  exponential backoff and jitter, honoring ``Retry-After`` when present.
- Cost is taken from the ``usage.cost`` field OpenRouter returns on every
  response; the price table below is only a fallback estimate.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from typing import Any

from minicodex.backends.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolsUnsupportedError,
    Usage,
)

DEFAULT_MODEL = "openai/gpt-6.1-sol"

# USD per million tokens (input, output); fallback estimate only.
PRICES_PER_M: dict[str, tuple[float, float]] = {
    "openai/gpt-6.1-sol": (2.00, 10.00),
    "openai/gpt-5.6-luna": (0.20, 1.20),
}

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 6
BASE_DELAY_S = 1.0
MAX_DELAY_S = 30.0

_CAPS_LOCK = threading.Lock()
_CAPS_CACHE: dict[str, set[str] | None] = {}


class TransientAPIError(RuntimeError):
    """A provider error that is worth retrying (e.g. an error body with 200)."""


class OpenAIBackend:
    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        timeout_s: float = 180.0,
    ):
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it (never commit it) or "
                "use the mock backend: --backend mock"
            )
        from openai import OpenAI  # imported lazily so mock runs need no SDK

        # max_retries=0: retries are handled (and counted) by _with_retries.
        self.client = OpenAI(max_retries=0, timeout=timeout_s)
        self.model = model or os.environ.get("MINICODEX_MODEL", DEFAULT_MODEL)
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.is_openrouter = "openrouter.ai" in self.base_url.lower()
        self.reasoning_effort = (
            reasoning_effort or os.environ.get("MINICODEX_REASONING_EFFORT") or None
        )
        self.max_attempts = max_attempts
        caps = self._capabilities()
        self.supports_native_tools = caps is None or "tools" in caps
        self.supports_structured_outputs = caps is None or (
            "structured_outputs" in caps or "response_format" in caps
        )
        self.supports_temperature = caps is None or "temperature" in caps
        default_in, default_out = PRICES_PER_M.get(self.model, (0.0, 0.0))
        self.input_cost_per_m = float(os.environ.get("MINICODEX_INPUT_COST_PER_M", default_in))
        self.output_cost_per_m = float(os.environ.get("MINICODEX_OUTPUT_COST_PER_M", default_out))

    # ------------------------------------------------------------ capability
    def _capabilities(self) -> set[str] | None:
        """OpenRouter's supported_parameters for this model (None = unknown)."""
        if not self.is_openrouter:
            return None
        with _CAPS_LOCK:
            if self.model in _CAPS_CACHE:
                return _CAPS_CACHE[self.model]
            caps: set[str] | None = None
            try:
                import httpx

                resp = httpx.get(self.base_url.rstrip("/") + "/models", timeout=30)
                resp.raise_for_status()
                for item in resp.json().get("data", []):
                    if item.get("id") == self.model:
                        caps = set(item.get("supported_parameters") or [])
                        break
                else:
                    raise ValueError(
                        f"model {self.model!r} is not listed at {self.base_url}/models"
                    )
            except ValueError:
                raise
            except Exception:  # noqa: BLE001 - offline / transient: assume defaults
                caps = None
            _CAPS_CACHE[self.model] = caps
            return caps

    # ------------------------------------------------------------- complete
    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        extra_body: dict[str, Any] = {}
        if self.supports_temperature:
            kwargs["temperature"] = 0
        if tools:
            kwargs.update(tools=tools, tool_choice="required", parallel_tool_calls=False)
        elif response_format:
            kwargs["response_format"] = response_format
        if self.reasoning_effort:
            if self.is_openrouter:
                extra_body["reasoning"] = {"effort": self.reasoning_effort}
            else:
                kwargs["reasoning_effort"] = self.reasoning_effort
        if extra_body:
            kwargs["extra_body"] = extra_body

        response, retries = self._with_retries(kwargs, bool(tools or response_format))
        choice = response.choices[0]
        msg = choice.message
        text = msg.content or ""
        calls: list[ToolCall] = []
        for call in msg.tool_calls or []:
            raw = call.function.arguments or "{}"
            try:
                parsed = json.loads(raw)
                args = parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                args = None
            calls.append(
                ToolCall(id=call.id, name=call.function.name, arguments=args, raw_arguments=raw)
            )

        history: Message = {"role": "assistant", "content": text or None}
        if msg.tool_calls:
            history["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in msg.tool_calls
            ]
        extra = getattr(msg, "model_extra", None) or {}
        if extra.get("reasoning_details"):
            # OpenRouter: pass reasoning blocks back unmodified across tool turns.
            history["reasoning_details"] = extra["reasoning_details"]

        usage = self._usage(response.usage)
        usage.api_retries = retries
        return LLMResponse(
            text=text,
            usage=usage,
            tool_calls=calls,
            message=history,
            finish_reason=choice.finish_reason,
        )

    def _with_retries(self, kwargs: dict[str, Any], structured: bool) -> tuple[Any, int]:
        import openai

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.client.chat.completions.create(**kwargs)
                if not getattr(response, "choices", None):
                    # OpenRouter can return an error object with HTTP 200.
                    err = (getattr(response, "model_extra", None) or {}).get("error")
                    raise TransientAPIError(f"empty choices from provider: {err}")
                return response, attempt - 1
            except openai.BadRequestError as exc:
                text = str(exc).lower()
                if structured and any(
                    w in text for w in ("tool", "function", "response_format", "json_schema")
                ):
                    raise ToolsUnsupportedError(str(exc)) from exc
                raise
            except (
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
                openai.RateLimitError,
                TransientAPIError,
                openai.APIStatusError,
            ) as exc:
                status = getattr(exc, "status_code", None)
                retryable = status is None or status in RETRYABLE_STATUS
                if not retryable or attempt >= self.max_attempts:
                    raise
                time.sleep(_backoff_delay(attempt, exc))

    def _usage(self, raw: Any) -> Usage:
        usage = Usage(
            input_tokens=getattr(raw, "prompt_tokens", 0) or 0,
            output_tokens=getattr(raw, "completion_tokens", 0) or 0,
            calls=1,
        )
        details = getattr(raw, "completion_tokens_details", None)
        usage.reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0
        reported = getattr(raw, "cost", None)
        if reported is None:
            reported = (getattr(raw, "model_extra", None) or {}).get("cost")
        if reported is not None:
            try:
                usage.cost_usd = float(reported)
                usage.cost_source = "reported"
                return usage
            except (TypeError, ValueError):
                pass
        usage.cost_usd = (
            usage.input_tokens * self.input_cost_per_m
            + usage.output_tokens * self.output_cost_per_m
        ) / 1e6
        usage.cost_source = "estimated"
        return usage


def _backoff_delay(attempt: int, exc: Exception) -> float:
    """Exponential backoff with full jitter; honors a Retry-After header."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    if retry_after:
        try:
            return min(float(retry_after), MAX_DELAY_S * 2)
        except ValueError:
            pass
    cap = min(MAX_DELAY_S, BASE_DELAY_S * 2 ** (attempt - 1))
    return random.uniform(cap / 2, cap)
