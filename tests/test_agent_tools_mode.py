"""Native tool-calling protocol, JSON fallback, and the failure taxonomy."""

import shutil
from pathlib import Path

from minicodex.agent import Agent
from minicodex.backends.base import LLMResponse, ToolCall, ToolsUnsupportedError, Usage

CUSTOM = Path(__file__).resolve().parent.parent / "benchmark" / "suites" / "custom"
FIXED = (
    (CUSTOM / "01_off_by_one" / "repo" / "mathutils.py")
    .read_text()
    .replace("range(1, n):", "range(1, n + 1):")
)


class ScriptedToolBackend:
    """Replays a list of (tool name, args) as native tool calls."""

    name = "scripted"
    model = "scripted-tools"
    supports_native_tools = True
    supports_structured_outputs = True

    def __init__(self, script, fail_with=None):
        self.script = list(script)
        self.fail_with = fail_with
        self.seen = []

    def complete(self, messages, tools=None, response_format=None):
        self.seen.append(
            {"messages": list(messages), "tools": tools, "response_format": response_format}
        )
        if self.fail_with:
            raise self.fail_with
        name, args = self.script.pop(0)
        call = ToolCall(id=f"call_{len(self.seen)}", name=name, arguments=args)
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {"name": name, "arguments": "{}"}}
            ],
        }
        return LLMResponse(
            text="", usage=Usage(10, 5, cost_usd=0.001, calls=1), tool_calls=[call], message=msg
        )


def _workdir(tmp_path, task="01_off_by_one"):
    work = tmp_path / "repo"
    shutil.copytree(CUSTOM / task / "repo", work)
    issue = (CUSTOM / task / "issue.md").read_text()
    return work, issue


def test_tool_calls_drive_the_loop(tmp_path):
    work, issue = _workdir(tmp_path)
    backend = ScriptedToolBackend(
        [
            ("read_file", {"path": "mathutils.py"}),
            ("run_tests", {}),
            ("write_file", {"path": "mathutils.py", "content": FIXED}),
            ("run_tests", {}),
        ]
    )
    result = Agent(backend=backend).run(work, issue)
    assert result.solved and result.action_mode == "tools"
    assert result.iterations == 1 and result.stop_reason == "tests_passed"
    assert backend.seen[0]["tools"] is not None
    # Tool results go back as role=tool messages tied to the call id.
    last = backend.seen[-1]["messages"][-1]
    assert last["role"] == "tool" and last["tool_call_id"] == "call_3"
    assert result.usage.cost_usd > 0


def test_writing_tests_is_a_guardrail_block(tmp_path):
    work, issue = _workdir(tmp_path)
    backend = ScriptedToolBackend(
        [
            ("write_file", {"path": "tests/test_mathutils.py", "content": "def test_x(): pass"}),
            ("finish", {"summary": "done"}),
        ]
    )
    result = Agent(backend=backend).run(work, issue)
    assert not result.solved
    assert result.guardrail_blocks == 1 and result.failure_reason == "guardrail_block"
    assert "def test_x" not in (work / "tests" / "test_mathutils.py").read_text()


def test_invalid_actions_stop_the_run(tmp_path):
    work, issue = _workdir(tmp_path)
    backend = ScriptedToolBackend([("rm_rf", {})] * 5)
    result = Agent(backend=backend, max_consecutive_invalid=3).run(work, issue)
    assert result.failure_reason == "invalid_action" and result.invalid_actions == 3


def test_api_error_is_classified(tmp_path):
    work, issue = _workdir(tmp_path)
    backend = ScriptedToolBackend([], fail_with=TimeoutError("upstream timeout"))
    result = Agent(backend=backend).run(work, issue)
    assert result.failure_reason == "api_error" and "timeout" in result.error


def test_unsupported_tools_fall_back_to_json_actions(tmp_path):
    work, issue = _workdir(tmp_path)

    class NoTools(ScriptedToolBackend):
        def complete(self, messages, tools=None, response_format=None):
            if tools:
                raise ToolsUnsupportedError("tools not supported")
            self.seen.append({"messages": list(messages), "response_format": response_format})
            return LLMResponse(
                text='{"thought": "t", "action": "finish", "args": {}}', usage=Usage(calls=1)
            )

    backend = NoTools([])
    result = Agent(backend=backend).run(work, issue)
    assert result.action_mode == "json"
    assert backend.seen[0]["response_format"]["type"] == "json_schema"
    assert result.failure_reason == "wrong_fix"


def test_no_retry_budget_stops_after_one_failed_edit(tmp_path):
    work, issue = _workdir(tmp_path)
    backend = ScriptedToolBackend(
        [
            ("run_tests", {}),
            (
                "write_file",
                {"path": "mathutils.py", "content": "def sum_first_n(n):\n    return 0\n"},
            ),
            ("run_tests", {}),
            ("write_file", {"path": "mathutils.py", "content": FIXED}),
        ]
    )
    result = Agent(backend=backend, max_iterations=1).run(work, issue)
    assert not result.solved and result.iterations == 1
    assert result.failure_reason == "budget_exhausted"
