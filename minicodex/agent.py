"""The agent loop: a scaled-down version of the Codex workflow Cisco runs.

plan -> inspect files -> edit -> run tests -> read failures -> iterate,
with an iteration budget, JSONL tracing, guardrails on every tool call, and a
human-review diff at the end.

Two action protocols are supported:

- "tools": native function calling (OpenAI / OpenRouter Chat Completions
  `tools`, strict schemas, one call per turn). Used when the model supports it.
- "json": the model replies with one JSON object
  ``{"thought": "...", "action": "<tool>", "args": {...}}``. Used by the mock
  backend and as the fallback for models without tool support; when the model
  supports structured outputs the reply is constrained by a JSON schema.

An *iteration* is one edit-and-verify cycle: a test run that follows at least
one file edit. A diagnostic test run before any edit is free, so
``max_iterations=1`` means "one patch attempt, no retries" (the no-retry
baseline) and the default of 6 allows five retries after failed tests.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from minicodex.backends.base import (
    Backend,
    LLMResponse,
    Message,
    ToolsUnsupportedError,
    Usage,
)
from minicodex.guardrails import (
    GuardrailViolation,
    Sandbox,
    changed_files,
    diff_summary,
    snapshot,
)
from minicodex.tools import ACTION_RESPONSE_FORMAT, TOOL_NAMES, TOOL_SCHEMAS, ToolBox
from minicodex.trace import TraceLogger

_COMMON_PROMPT = """\
You are a careful software engineering agent fixing a small Python repo.
You work in a sandboxed copy of the repo. You cannot use a shell or the
network; your only tools are:

- list_files: {} -> list of file paths
- read_file: {"path": "<relative path>"} -> file content
- write_file: {"path": "<relative path>", "content": "<full new content>"}
- search: {"query": "<substring>"} -> matching lines across files
- run_tests: {} -> pytest result (this is how you check your work)
- finish: {"summary": "<what you did>"} -> end the session

Process: inspect the relevant files, run the tests to see the failures,
apply a minimal edit, and re-run the tests. Iterate until the tests pass.
The tests are read-only and secret-like files (.env, keys) are blocked.
Every edit you make is followed by a test run; you have a limited number of
edit-and-test attempts, so make each edit count.
"""

TOOLS_PROMPT = _COMMON_PROMPT + "\nCall exactly one tool per turn.\n"

JSON_PROMPT = (
    _COMMON_PROMPT
    + """
Respond with EXACTLY ONE JSON object, no markdown fences, of the form:
{"thought": "<brief reasoning>", "action": "<tool name>", "args": {...}}
"""
)

# Back-compat name used by earlier docs/tests.
SYSTEM_PROMPT = JSON_PROMPT

FAILURE_REASONS = (
    "wrong_fix",
    "budget_exhausted",
    "invalid_action",
    "guardrail_block",
    "api_error",
)


@dataclass
class AgentResult:
    solved: bool
    iterations: int
    wall_time_s: float
    usage: Usage
    files_changed: list[str]
    diff: str
    final_test_output: str
    gave_up: bool = False
    trace_path: str | None = None
    steps: int = 0
    stop_reason: str = ""
    failure_reason: str = ""
    invalid_actions: int = 0
    guardrail_blocks: int = 0
    test_runs: int = 0
    action_mode: str = "json"
    error: str = ""


@dataclass
class Agent:
    backend: Backend
    max_iterations: int = 6
    trace_path: str | Path | None = None
    action_mode: str = "auto"  # auto | tools | json
    max_steps: int | None = None  # default: 10 + 6 * max_iterations
    max_consecutive_invalid: int = 3
    trace: TraceLogger | None = None
    _trace: TraceLogger = field(init=False, repr=False)

    # ------------------------------------------------------------------ run
    def run(self, workdir: str | Path, issue: str) -> AgentResult:
        """Run the edit-test-fix loop on a working copy at *workdir*."""
        start = time.monotonic()
        sandbox = Sandbox(workdir)
        tools = ToolBox(sandbox)
        self._trace = self.trace or TraceLogger(self.trace_path)
        mode = self._initial_mode()
        max_steps = self.max_steps or 10 + 6 * self.max_iterations
        self._trace.log(
            "start",
            workdir=str(sandbox.root),
            issue=issue,
            backend=self.backend.name,
            model=getattr(self.backend, "model", ""),
            max_iterations=self.max_iterations,
            action_mode=mode,
        )

        before = snapshot(sandbox.root)
        usage = Usage()
        messages: list[Message] = [
            {"role": "system", "content": TOOLS_PROMPT if mode == "tools" else JSON_PROMPT},
            {"role": "user", "content": f"ISSUE TO FIX:\n{issue}"},
        ]

        st = _LoopState()
        while True:
            if st.steps >= max_steps:
                st.stop_reason = "step_cap"
                self._trace.log("step_cap_hit", steps=st.steps)
                break
            try:
                response = self._complete(messages, mode)
            except ToolsUnsupportedError as exc:
                self._trace.log("fallback_to_json_actions", reason=str(exc)[:300])
                mode = "json"
                messages = _to_json_history(messages)
                continue
            except Exception as exc:  # noqa: BLE001 - any provider failure ends the run
                st.error = f"{type(exc).__name__}: {str(exc)[:300]}"
                st.stop_reason = "api_error"
                self._trace.log("api_error", error=st.error)
                break

            usage.add(response.usage)
            st.steps += 1
            self._trace.log(
                "llm_call",
                step=st.steps,
                model=getattr(self.backend, "model", ""),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                reasoning_tokens=response.usage.reasoning_tokens,
                cost_usd=round(response.usage.cost_usd, 6),
                api_retries=response.usage.api_retries,
                response=response.text[:4000],
                tool_calls=[
                    {"name": c.name, "args": _safe_args(c.arguments or {})}
                    for c in response.tool_calls
                ],
            )

            action, call_id, extra_ids = self._extract(response, mode, messages)
            if action is not None and action.get("action") not in TOOL_NAMES:
                action = None  # unknown tool: same handling as unparseable output
            if action is None:
                st.invalid += 1
                st.consecutive_invalid += 1
                self._trace.log("invalid_action", step=st.steps)
                self._reply(
                    messages,
                    call_id,
                    extra_ids,
                    "OBSERVATION (error):\nThat was not a valid action. "
                    "Call exactly one of the tools with valid arguments.",
                )
                if st.consecutive_invalid >= self.max_consecutive_invalid:
                    st.stop_reason = "invalid_action"
                    break
                continue
            st.consecutive_invalid = 0

            name = str(action.get("action", ""))
            args = {k: v for k, v in (action.get("args") or {}).items() if v is not None}
            self._trace.log(
                "action",
                step=st.steps,
                thought=action.get("thought", ""),
                tool=name,
                args=_safe_args(args),
            )

            if name == "finish":
                self._reply(messages, call_id, extra_ids, "OBSERVATION (finish): ok")
                st.stop_reason = "finished"
                break
            observation, test_passed, blocked = _execute(tools, name, args)
            self._trace.log("observation", step=st.steps, tool=name, result=observation[:2000])
            self._reply(messages, call_id, extra_ids, observation)
            if blocked:
                st.guardrail_blocks += 1
                st.blocked_writes += name == "write_file"
                self._trace.log("guardrail_block", step=st.steps, tool=name, args=_safe_args(args))
            elif name == "write_file" and observation.startswith("OBSERVATION (write_file)"):
                st.edits_since_test += 1
                st.total_edits += 1

            if name == "run_tests":
                st.test_runs += 1
                if st.edits_since_test:
                    st.iterations += 1
                    st.edits_since_test = 0
                st.last_test_passed = test_passed
                st.final_test_output = observation
                self._trace.log("test_run", iteration=st.iterations, passed=test_passed)
                if test_passed:
                    st.stop_reason = "tests_passed"
                    break
                if st.iterations >= self.max_iterations:
                    st.stop_reason = "budget_exhausted"
                    self._trace.log("budget_exhausted", iterations=st.iterations)
                    break

        # Final verification: trust only a pytest run made after the last edit.
        if st.last_test_passed is None or st.edits_since_test:
            result = tools.run_tests()
            if st.edits_since_test:
                st.iterations += 1
            st.last_test_passed = result.passed
            st.final_test_output = result.output
            self._trace.log("final_verification", passed=result.passed)

        after = snapshot(sandbox.root)
        solved = bool(st.last_test_passed)
        agent_result = AgentResult(
            solved=solved,
            iterations=st.iterations,
            wall_time_s=round(time.monotonic() - start, 2),
            usage=usage,
            files_changed=changed_files(before, after),
            diff=diff_summary(before, after),
            final_test_output=st.final_test_output,
            gave_up=not solved and st.stop_reason != "tests_passed",
            trace_path=str(self._trace.path) if self._trace.path else None,
            steps=st.steps,
            stop_reason=st.stop_reason,
            failure_reason="" if solved else classify_failure(st),
            invalid_actions=st.invalid,
            guardrail_blocks=st.guardrail_blocks,
            test_runs=st.test_runs,
            action_mode=mode,
            error=st.error,
        )
        self._trace.log(
            "end",
            solved=solved,
            iterations=st.iterations,
            steps=st.steps,
            stop_reason=st.stop_reason,
            failure_reason=agent_result.failure_reason,
            files_changed=agent_result.files_changed,
            wall_time_s=agent_result.wall_time_s,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=round(usage.cost_usd, 6),
        )
        self._trace.log("diff_for_human_review", diff=agent_result.diff)
        return agent_result

    # -------------------------------------------------------------- helpers
    def _initial_mode(self) -> str:
        if self.action_mode == "json":
            return "json"
        native = bool(getattr(self.backend, "supports_native_tools", False))
        if self.action_mode == "tools" and not native:
            raise ValueError(f"backend {self.backend.name!r} has no native tool support")
        return "tools" if native else "json"

    def _complete(self, messages: list[Message], mode: str) -> LLMResponse:
        if mode == "tools":
            return self.backend.complete(messages, tools=TOOL_SCHEMAS)
        fmt = (
            ACTION_RESPONSE_FORMAT
            if getattr(self.backend, "supports_structured_outputs", False)
            else None
        )
        return self.backend.complete(messages, response_format=fmt)

    def _extract(
        self,
        response: LLMResponse,
        mode: str,
        messages: list[Message],
    ) -> tuple[dict[str, Any] | None, str | None, list[str]]:
        """Append the assistant turn; return (action, tool_call_id, extra ids)."""
        if mode == "tools" and response.tool_calls:
            messages.append(response.message or {"role": "assistant", "content": response.text})
            first, rest = response.tool_calls[0], response.tool_calls[1:]
            extra = [c.id for c in rest]
            if first.arguments is None:
                return None, first.id, extra
            return (
                {"action": first.name, "args": first.arguments, "thought": response.text},
                first.id,
                extra,
            )
        messages.append({"role": "assistant", "content": response.text})
        return _parse_action(response.text), None, []

    @staticmethod
    def _reply(
        messages: list[Message], call_id: str | None, extra_ids: list[str], observation: str
    ) -> None:
        if call_id is None:
            messages.append({"role": "user", "content": observation})
            return
        messages.append({"role": "tool", "tool_call_id": call_id, "content": observation})
        for other in extra_ids:  # every tool call needs an answer
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": other,
                    "content": "Not executed: call one tool per turn.",
                }
            )


@dataclass
class _LoopState:
    iterations: int = 0
    steps: int = 0
    test_runs: int = 0
    edits_since_test: int = 0
    total_edits: int = 0
    invalid: int = 0
    consecutive_invalid: int = 0
    guardrail_blocks: int = 0
    blocked_writes: int = 0
    last_test_passed: bool | None = None
    final_test_output: str = ""
    stop_reason: str = ""
    error: str = ""


def classify_failure(st: _LoopState) -> str:
    """Map an unsolved run to one failure category (see FAILURE_REASONS)."""
    if st.stop_reason == "api_error":
        return "api_error"
    if st.stop_reason == "invalid_action":
        return "invalid_action"
    if st.blocked_writes or (st.guardrail_blocks and not st.total_edits):
        return "guardrail_block"
    if st.stop_reason in ("budget_exhausted", "step_cap"):
        return "budget_exhausted"
    return "wrong_fix"


def _to_json_history(messages: list[Message]) -> list[Message]:
    """Rewrite a tool-calling history into the plain JSON-action protocol."""
    out: list[Message] = [{"role": "system", "content": JSON_PROMPT}]
    for m in messages[1:]:
        if m["role"] == "tool":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant" and m.get("tool_calls"):
            call = m["tool_calls"][0]["function"]
            out.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "thought": m.get("content") or "",
                            "action": call["name"],
                            "args": json.loads(call.get("arguments") or "{}"),
                        }
                    ),
                }
            )
        else:
            out.append({"role": m["role"], "content": m.get("content") or ""})
    return out


def _execute(
    tools: ToolBox,
    name: str,
    args: dict[str, Any],
) -> tuple[str, bool | None, bool]:
    """Run one tool. Returns (observation, test_passed or None, blocked)."""
    try:
        if name == "list_files":
            body = "\n".join(f"- {f}" for f in tools.list_files())
            return f"OBSERVATION (list_files):\n{body}", None, False
        if name == "read_file":
            content = tools.read_file(str(args["path"]))
            return f"OBSERVATION (read_file):\n{content}", None, False
        if name == "write_file":
            msg = tools.write_file(str(args["path"]), str(args["content"]))
            return f"OBSERVATION (write_file):\n{msg}", None, False
        if name == "search":
            hits = tools.search(str(args["query"]))
            body = "\n".join(hits) if hits else "(no matches)"
            return f"OBSERVATION (search):\n{body}", None, False
        if name == "run_tests":
            result = tools.run_tests()
            verdict = "TESTS PASSED" if result.passed else "TESTS FAILED"
            return (
                f"OBSERVATION (run_tests): {verdict} (exit {result.returncode})\n{result.output}",
                result.passed,
                False,
            )
        return f"OBSERVATION (error):\nUnknown tool {name!r}.", None, False  # pragma: no cover
    except GuardrailViolation as exc:
        return f"OBSERVATION (guardrail):\nBLOCKED: {exc}", None, True
    except (KeyError, FileNotFoundError, OSError, ValueError) as exc:
        return f"OBSERVATION (error):\n{type(exc).__name__}: {exc}", None, False


def _parse_action(text: str) -> dict[str, Any] | None:
    """Extract the agent's JSON action from a possibly chatty model reply.

    Tolerates prose before/after the JSON, markdown code fences (```json),
    and multiple JSON objects (the first one carrying an "action" key wins).
    """
    candidates = [m.group(1) for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)]
    candidates.append(text)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        pos = 0
        while True:
            start = candidate.find("{", pos)
            if start == -1:
                break
            try:
                obj, consumed = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                pos = start + 1
                continue
            if isinstance(obj, dict) and "action" in obj:
                return obj
            pos = start + consumed
    return None


def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    """Trim bulky values (file contents) for the trace's action record."""
    return {
        k: (v[:400] + "... [truncated]" if isinstance(v, str) and len(v) > 400 else v)
        for k, v in args.items()
    }
