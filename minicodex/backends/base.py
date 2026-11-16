"""Backend interface shared by the real and mock LLMs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

Message = dict[str, Any]


@dataclass
class Usage:
    """Token usage and cost for one or more LLM calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    api_retries: int = 0
    calls: int = 0
    # "reported" when every call's cost came from the provider (OpenRouter's
    # usage.cost), "estimated" when any call fell back to the price table.
    cost_source: str = "reported"

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cost_usd += other.cost_usd
        self.api_retries += other.api_retries
        self.calls += other.calls
        if other.cost_source == "estimated":
            self.cost_source = "estimated"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ToolCall:
    """One native function call requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any] | None  # None when the JSON arguments were invalid
    raw_arguments: str = ""


@dataclass
class LLMResponse:
    text: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The assistant message exactly as it should be appended to the history
    # (keeps tool_calls and provider reasoning blocks intact).
    message: Message | None = None
    finish_reason: str | None = None


class ToolsUnsupportedError(RuntimeError):
    """The provider rejected native tools / structured outputs for this model."""


class Backend(Protocol):
    """A chat-completion backend. ``messages`` use the OpenAI chat format."""

    name: str
    model: str
    supports_native_tools: bool
    supports_structured_outputs: bool

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse: ...
