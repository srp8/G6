"""Pluggable LLM backends.

- "openai": the real backend, mirroring Cisco's use of OpenAI models. Works
  with any OpenAI-compatible API; set OPENAI_BASE_URL=https://openrouter.ai/api/v1
  to use OpenRouter model ids such as ``openai/gpt-6.1-sol``.
- "mock": a deterministic, offline, rule-based backend so the entire
  pipeline (agent loop, router, benchmark, notebook, tests) runs with NO key.
"""

from __future__ import annotations

import os

from minicodex.backends.base import Backend, LLMResponse, ToolCall, Usage
from minicodex.backends.mock_backend import MockBackend


def get_backend(
    name: str | None = None, model: str | None = None, reasoning_effort: str | None = None
) -> Backend:
    """Create a backend by name, falling back to $MINICODEX_BACKEND or mock.

    For the mock backend, ``model`` selects the profile: any id containing
    "cheap" or "luna" (or ``mock-cheap``) gives the weaker cheap profile.
    """
    name = (name or os.environ.get("MINICODEX_BACKEND") or "mock").lower()
    if name == "mock":
        cheap = bool(model) and any(k in model.lower() for k in ("cheap", "luna"))
        return MockBackend(profile="cheap" if cheap else "strong")
    if name == "openai":
        from minicodex.backends.openai_backend import OpenAIBackend

        return OpenAIBackend(model=model, reasoning_effort=reasoning_effort)
    raise ValueError(f"Unknown backend {name!r}. Use 'mock' or 'openai'.")


__all__ = ["Backend", "LLMResponse", "ToolCall", "Usage", "MockBackend", "get_backend"]
