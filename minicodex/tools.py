"""The agent's tools: the only ways it can act on the world.

Each tool is a small, explicit function. The agent cannot run arbitrary
shell commands or reach the network; `run_tests` is the single subprocess it
may start, with a fixed command line and a timeout. This mirrors how Cisco
constrains Codex to a task sandbox with an approved toolchain.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from minicodex.guardrails import BLOCKED_DIRS, Sandbox

MAX_READ_CHARS = 20_000
MAX_TEST_OUTPUT_CHARS = 6_000
TEST_TIMEOUT_SECONDS = 60


TOOL_NAMES = ("list_files", "read_file", "write_file", "search", "run_tests", "finish")


def _function(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    """An OpenAI-format function tool in strict mode (all fields required)."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


_PATH = {"type": "string", "description": "Path relative to the repo root."}

# Native tool definitions (OpenAI / OpenRouter Chat Completions `tools`).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    _function("list_files", "List every visible file in the repository.", {}),
    _function("read_file", "Read one file.", {"path": _PATH}),
    _function(
        "write_file",
        "Overwrite (or create) a file with its complete new content.",
        {"path": _PATH, "content": {"type": "string", "description": "The full new file content."}},
    ),
    _function(
        "search",
        "Case-insensitive substring search across all files.",
        {"query": {"type": "string"}},
    ),
    _function("run_tests", "Run the pytest suite and return the result.", {}),
    _function(
        "finish",
        "End the session with a short summary of the change.",
        {"summary": {"type": "string"}},
    ),
]

# Structured-output schema for the JSON-action fallback (models that support
# `response_format` json_schema but not tools). Unused args are null.
_NULLABLE_STR = {"type": ["string", "null"]}
ACTION_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_action",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action": {"type": "string", "enum": list(TOOL_NAMES)},
                "args": {
                    "type": "object",
                    "properties": {
                        k: _NULLABLE_STR for k in ("path", "content", "query", "summary")
                    },
                    "required": ["path", "content", "query", "summary"],
                    "additionalProperties": False,
                },
            },
            "required": ["thought", "action", "args"],
            "additionalProperties": False,
        },
    },
}


@dataclass
class TestResult:
    passed: bool
    output: str
    returncode: int


class ToolBox:
    """All tools, bound to one sandbox. Every call goes through guardrails."""

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def list_files(self) -> list[str]:
        """Relative paths of all visible files in the working copy."""
        results = []
        for path in sorted(self.sandbox.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.sandbox.root)
            if any(part in BLOCKED_DIRS for part in rel.parts):
                continue
            if self.sandbox.is_allowed(str(rel)):
                results.append(str(rel))
        return results

    def read_file(self, path: str) -> str:
        """Read a file (truncated if huge). Guardrails may refuse."""
        resolved = self.sandbox.resolve(path)
        text = resolved.read_text(encoding="utf-8")
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + "\n... [truncated]"
        return text

    def write_file(self, path: str, content: str) -> str:
        """Overwrite (or create) a file inside the sandbox."""
        resolved = self.sandbox.resolve_for_write(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"

    def search(self, query: str) -> list[str]:
        """Case-insensitive substring search across all visible files."""
        hits = []
        needle = query.lower()
        for rel in self.list_files():
            try:
                text = self.read_file(rel)
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if needle in line.lower():
                    hits.append(f"{rel}:{lineno}: {line.strip()}")
        return hits[:50]

    def run_tests(self) -> TestResult:
        """Run pytest in the working copy. The agent's only subprocess."""
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=self.sandbox.root,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            env=_restricted_env(),
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        if len(output) > MAX_TEST_OUTPUT_CHARS:
            output = output[:MAX_TEST_OUTPUT_CHARS] + "\n... [truncated]"
        return TestResult(passed=proc.returncode == 0, output=output, returncode=proc.returncode)


def _restricted_env() -> dict[str, str]:
    """A minimal environment for the test subprocess: no API keys, no proxy."""
    keep = {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "PYTHONHASHSEED",
        "TMPDIR",
        "SYSTEMROOT",
        "VIRTUAL_ENV",
    }
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["NO_PROXY"] = "*"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
