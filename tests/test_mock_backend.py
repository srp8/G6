import json

from minicodex.backends import MockBackend, get_backend


def _msgs(*contents):
    """Build a conversation: system, issue, then alternating assistant/user."""
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "ISSUE TO FIX:\nfix the bug"},
    ]
    role = "assistant"
    for content in contents:
        messages.append({"role": role, "content": content})
        role = "user" if role == "assistant" else "assistant"
    return messages


def test_get_backend_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("MINICODEX_BACKEND", raising=False)
    assert get_backend().name == "mock"


def test_first_action_is_a_plan_plus_list_files():
    backend = MockBackend()
    response = backend.complete(_msgs())
    action = json.loads(response.text)
    assert action["action"] == "list_files"
    assert "plan" in action["thought"].lower()
    assert response.usage.input_tokens > 0
    assert response.usage.cost_usd == 0.0


def test_reads_files_then_runs_tests():
    backend = MockBackend()
    first = backend.complete(_msgs())
    second = backend.complete(
        _msgs(
            first.text,
            "OBSERVATION (list_files):\n- mathutils.py",
        )
    )
    action = json.loads(second.text)
    assert action == {
        "thought": "Reading mathutils.py to understand the code.",
        "action": "read_file",
        "args": {"path": "mathutils.py"},
    }
    third = backend.complete(
        _msgs(
            first.text,
            "OBSERVATION (list_files):\n- mathutils.py",
            second.text,
            "OBSERVATION (read_file):\nfor i in range(1, n):",
        )
    )
    assert json.loads(third.text)["action"] == "run_tests"


def test_applies_known_fix_when_tests_fail():
    backend = MockBackend()
    backend.issue = "fix the bug"
    backend.files = {"mathutils.py": "for i in range(1, n):\n"}
    backend.awaiting = "run_tests"
    response = backend.complete(_msgs("x", "OBSERVATION (run_tests): TESTS FAILED\n..."))
    action = json.loads(response.text)
    assert action["action"] == "write_file"
    assert "range(1, n + 1)" in action["args"]["content"]


def test_finishes_when_tests_pass():
    backend = MockBackend()
    backend.issue = "fix the bug"
    backend.awaiting = "run_tests"
    response = backend.complete(_msgs("x", "OBSERVATION (run_tests): TESTS PASSED\n..."))
    assert json.loads(response.text)["action"] == "finish"


def test_gives_up_without_matching_rule():
    backend = MockBackend()
    backend.issue = "fix the bug"
    backend.files = {"weird.py": "nothing matches here\n"}
    backend.awaiting = "run_tests"
    response = backend.complete(_msgs("x", "OBSERVATION (run_tests): TESTS FAILED\n..."))
    assert json.loads(response.text)["action"] == "finish"
    assert backend.gave_up
