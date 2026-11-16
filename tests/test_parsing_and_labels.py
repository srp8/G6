"""Robust action parsing (chatty models) and per-run result labeling."""

from minicodex.agent import _parse_action
from minicodex.bench import resolve_run


def test_parse_plain_json():
    assert _parse_action('{"action": "run_tests", "args": {}}') == {
        "action": "run_tests",
        "args": {},
    }


def test_parse_with_chatty_prose_around():
    text = (
        "Sure! Let me run the tests now.\n"
        '{"thought": "check", "action": "run_tests", "args": {}}\n'
        "Let me know if you need anything else!"
    )
    assert _parse_action(text)["action"] == "run_tests"


def test_parse_markdown_fenced_json():
    text = 'Here is my action:\n```json\n{"action": "read_file", "args": {"path": "a.py"}}\n```'
    assert _parse_action(text)["args"]["path"] == "a.py"


def test_parse_fence_without_language_tag():
    text = '```\n{"action": "list_files", "args": {}}\n```'
    assert _parse_action(text)["action"] == "list_files"


def test_parse_skips_json_without_action_key():
    text = (
        '{"note": "this is not an action"} and then '
        '{"action": "finish", "args": {"summary": "done"}}'
    )
    assert _parse_action(text)["action"] == "finish"


def test_parse_json_containing_braces_in_strings():
    text = '{"action": "write_file", "args": {"path": "a.py", "content": "d = {1: 2}\\nprint(d)"}}'
    parsed = _parse_action(text)
    assert parsed["args"]["content"] == "d = {1: 2}\nprint(d)"


def test_parse_garbage_returns_none():
    assert _parse_action("I will now fix the bug.") is None
    assert _parse_action("{broken json") is None


def test_resolve_run_mock(monkeypatch):
    monkeypatch.delenv("MINICODEX_BACKEND", raising=False)
    assert resolve_run(None, None) == ("mock", "rule-playbook", "mock")


def test_resolve_run_openrouter_model_id_is_filename_safe():
    backend, model, label = resolve_run("openai", "openai/gpt-4o-mini")
    assert backend == "openai"
    assert model == "openai/gpt-4o-mini"
    assert label == "openai_openai-gpt-4o-mini"
    assert "/" not in label


def test_resolve_run_model_from_env(monkeypatch):
    monkeypatch.setenv("MINICODEX_MODEL", "meta-llama/llama-3.1-8b-instruct")
    _, model, label = resolve_run("openai", None)
    assert model == "meta-llama/llama-3.1-8b-instruct"
    assert label == "openai_meta-llama-llama-3.1-8b-instruct"
