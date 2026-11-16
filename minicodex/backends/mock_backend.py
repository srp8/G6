"""Deterministic offline backend: a tiny rule-based "LLM".

It speaks the exact same JSON action protocol as the real backend, so the
agent loop, trace, guardrails, benchmark, and notebook all exercise the same
code paths with NO API key. Instead of a neural network it carries a small
playbook of bug patterns (an "expert system"): when the tests fail, it looks
for a known buggy pattern in the files it has read and rewrites that file.

It fixes at most one file per edit, then re-runs the tests -- so multi-file
bugs genuinely take multiple iterations, just like a real agent run.

Two profiles make the router and cascade demonstrable offline:

- "strong" (default): keeps applying playbook fixes until the tests pass.
- "cheap": applies a single fix and gives up if the tests still fail, so a
  multi-file bug needs escalation to the strong profile.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from minicodex.backends.base import LLMResponse, Message, Usage


@dataclass
class ReplaceRule:
    """If a file contains `find`, replace it with `replace`."""

    find: str
    replace: str
    note: str


@dataclass
class AppendRule:
    """If the issue mentions `trigger` and `target` lacks `marker`, append code."""

    trigger: str
    target: str
    marker: str
    code: str
    note: str


RULES: list[ReplaceRule | AppendRule] = [
    ReplaceRule(
        find="for i in range(1, n):",
        replace="for i in range(1, n + 1):",
        note="off-by-one: range(1, n) skips n",
    ),
    ReplaceRule(
        find="return age > 18",
        replace="return age >= 18",
        note="wrong comparison: 18-year-olds are adults",
    ),
    ReplaceRule(
        find="    return sum(numbers) / len(numbers)",
        replace=("    if not numbers:\n        return 0.0\n    return sum(numbers) / len(numbers)"),
        note="missing edge case: empty list divides by zero",
    ),
    ReplaceRule(
        find="FREE_SHIPPING_THRESHOLD = 25.0",
        replace="FREE_SHIPPING_THRESHOLD = 50.0",
        note="wrong constant: free shipping starts at $50, not $25",
    ),
    ReplaceRule(
        find="        total -= item.price * item.quantity",
        replace="        total += item.price * item.quantity",
        note="sign bug: items must add to the subtotal",
    ),
    ReplaceRule(
        find='words = text.split(",")',
        replace="words = text.split()",
        note="wrong delimiter: words are separated by whitespace",
    ),
    ReplaceRule(
        find="        counts[word] = 1",
        replace="        counts[word] = counts.get(word, 0) + 1",
        note="dict bug: assignment overwrites the running count",
    ),
    AppendRule(
        trigger="slugify",
        target="text_utils.py",
        marker="def slugify",
        code=(
            "\n\ndef slugify(text: str) -> str:\n"
            '    """Lowercase, trim, and join words with single hyphens."""\n'
            '    cleaned = [c.lower() if c.isalnum() else " " for c in text]\n'
            '    return "-".join("".join(cleaned).split())\n'
        ),
        note="feature request: add slugify()",
    ),
]


class MockBackend:
    """Stateful scripted policy: plan -> read files -> test -> patch -> retest."""

    name = "mock"
    supports_native_tools = False
    supports_structured_outputs = False

    def __init__(self, profile: str = "strong"):
        if profile not in ("strong", "cheap"):
            raise ValueError(f"unknown mock profile {profile!r}")
        self.profile = profile
        self.model = f"mock-{profile}"
        self.max_fixes = 1 if profile == "cheap" else 10**6
        self.fixes_applied = 0
        self.files: dict[str, str] = {}
        self.pending_reads: list[str] = []
        self.issue: str = ""
        self.awaiting: str | None = None  # tool name we expect an observation for
        self.gave_up = False

    # ------------------------------------------------------------------ API
    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self.issue:
            self.issue = next((m["content"] for m in messages if m["role"] == "user"), "")
        observation = messages[-1]["content"] if messages[-1]["role"] == "user" else ""
        action = self._next_action(observation)
        text = json.dumps(action, indent=2)
        usage = Usage(
            input_tokens=sum(len(m.get("content") or "") for m in messages) // 4,
            output_tokens=len(text) // 4,
            cost_usd=0.0,
            calls=1,
        )
        return LLMResponse(text=text, usage=usage)

    # --------------------------------------------------------------- policy
    def _next_action(self, observation: str) -> dict[str, Any]:
        if self.awaiting == "list_files":
            listed = _parse_list(observation)
            self.pending_reads = [p for p in listed if p.endswith(".py")]
        elif self.awaiting == "read_file":
            path = self.pending_reads.pop(0)
            self.files[path] = _parse_file_content(observation)
        elif self.awaiting == "run_tests":
            if "TESTS PASSED" in observation:
                self.awaiting = None
                return {
                    "thought": "All tests pass; the fix is complete.",
                    "action": "finish",
                    "args": {"summary": "Tests pass after the applied fix."},
                }
            fix = self._find_fix() if self.fixes_applied < self.max_fixes else None
            if fix is not None:
                self.fixes_applied += 1
                path, new_content, note = fix
                self.files[path] = new_content
                self.awaiting = "write_file"
                return {
                    "thought": f"Tests fail. Applying known fix: {note}",
                    "action": "write_file",
                    "args": {"path": path, "content": new_content},
                }
            self.gave_up = True
            self.awaiting = None
            return {
                "thought": "Tests still fail and no known pattern matches.",
                "action": "finish",
                "args": {"summary": "Unable to fix: no playbook rule matched."},
            }

        if self.awaiting is None and not self.files and not self.pending_reads:
            self.awaiting = "list_files"
            return {
                "thought": (
                    "Plan: (1) list the files, (2) read the source, "
                    "(3) run the tests to see failures, (4) patch the bug, "
                    "(5) re-run tests until green."
                ),
                "action": "list_files",
                "args": {},
            }
        if self.pending_reads:
            self.awaiting = "read_file"
            return {
                "thought": f"Reading {self.pending_reads[0]} to understand the code.",
                "action": "read_file",
                "args": {"path": self.pending_reads[0]},
            }
        self.awaiting = "run_tests"
        return {
            "thought": "Running the test suite to check the current state.",
            "action": "run_tests",
            "args": {},
        }

    def _find_fix(self) -> tuple[str, str, str] | None:
        for rule in RULES:
            if isinstance(rule, ReplaceRule):
                for path in sorted(self.files):
                    if path.startswith("tests"):
                        continue
                    if rule.find in self.files[path]:
                        return (
                            path,
                            self.files[path].replace(rule.find, rule.replace),
                            rule.note,
                        )
            else:  # AppendRule
                if rule.trigger.lower() not in self.issue.lower():
                    continue
                for path in sorted(self.files):
                    if path.startswith("tests"):
                        continue
                    is_target = path == rule.target or path.endswith("/" + rule.target)
                    if is_target and rule.marker not in self.files[path]:
                        return (path, self.files[path] + rule.code, rule.note)
        return None


def _parse_list(observation: str) -> list[str]:
    lines = observation.splitlines()
    return [line.strip("- ").strip() for line in lines[1:] if line.strip().startswith("-")]


def _parse_file_content(observation: str) -> str:
    # Observations are "OBSERVATION (read_file):\n<content>"
    _, _, body = observation.partition("\n")
    return body
