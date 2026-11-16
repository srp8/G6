"""Guardrails: the governance layer of the agent.

Mirrors the controls Cisco applies to its Codex deployment, scaled down:

- Sandbox:        the agent only ever touches a working *copy* of the task
                  repo. Every path is resolved and checked to stay inside it.
- Secret hygiene: files that look like secrets (.env, keys, credentials) are
                  blocked from both reads and writes.
- No shell:       the agent has no shell tool. The only process it can start
                  is the pytest runner, with a fixed command line and timeout
                  (see tools.run_tests).
- Protected tests: the agent may read the tests but not rewrite them, so it
                  cannot "pass" by weakening the checks (writes to tests/,
                  test_*.py and conftest.py are blocked).
- Human review:   a unified-diff summary of everything that changed is
                  produced at the end of a run (see diff_summary).
"""

from __future__ import annotations

import difflib
import fnmatch
from pathlib import Path

# File names/patterns the agent must never read or write.
SECRET_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*credentials*",
    "*secret*",
    "*.keystore",
    ".netrc",
]

# Files the agent may read but never modify (the grading harness).
PROTECTED_WRITE_PATTERNS = ["tests/*", "test_*.py", "*_test.py", "conftest.py"]

# Directories the agent may not enter.
BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}


class GuardrailViolation(Exception):
    """Raised when the agent attempts a blocked action."""


class Sandbox:
    """Confines all file operations to a single working directory."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Sandbox root is not a directory: {self.root}")

    def resolve(self, relative_path: str) -> Path:
        """Resolve a path and enforce every guardrail. Raises on violation."""
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise GuardrailViolation(f"Path escapes the sandbox: {relative_path!r}")
        rel = candidate.relative_to(self.root)
        for part in rel.parts:
            if part in BLOCKED_DIRS:
                raise GuardrailViolation(f"Blocked directory: {relative_path!r}")
        name = candidate.name.lower()
        for pattern in SECRET_PATTERNS:
            if fnmatch.fnmatch(name, pattern):
                raise GuardrailViolation(f"Blocked secret-like file: {relative_path!r}")
        return candidate

    def resolve_for_write(self, relative_path: str) -> Path:
        """Like resolve(), but also refuses the protected test harness."""
        candidate = self.resolve(relative_path)
        rel = candidate.relative_to(self.root).as_posix()
        for pattern in PROTECTED_WRITE_PATTERNS:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(candidate.name, pattern):
                raise GuardrailViolation(f"Tests are read-only for the agent: {relative_path!r}")
        return candidate

    def is_allowed(self, relative_path: str) -> bool:
        try:
            self.resolve(relative_path)
            return True
        except GuardrailViolation:
            return False


def snapshot(root: str | Path) -> dict[str, str]:
    """Capture the text content of every non-blocked file under *root*."""
    root = Path(root).resolve()
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in BLOCKED_DIRS for part in rel.parts):
            continue
        try:
            files[str(rel)] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return files


def diff_summary(before: dict[str, str], after: dict[str, str]) -> str:
    """Unified diff of two snapshots, for the human-review step."""
    chunks: list[str] = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name, "").splitlines(keepends=True)
        new = after.get(name, "").splitlines(keepends=True)
        if old == new:
            continue
        label = name if name in before else f"{name} (new file)"
        diff = difflib.unified_diff(
            old, new, fromfile=f"a/{name}", tofile=f"b/{label}", lineterm=""
        )
        chunks.append("".join(line if line.endswith("\n") else line + "\n" for line in diff))
    if not chunks:
        return "No files were changed."
    return "\n".join(chunks)


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
