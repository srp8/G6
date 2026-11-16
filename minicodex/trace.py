"""JSONL trace logging so a human can review every action the agent took.

This mirrors the audit/human-review requirement in Cisco's Codex deployment:
nothing the agent does is invisible. Every LLM call, tool call, test run, and
decision is appended to a trace file as one JSON object per line.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TraceLogger:
    """Appends timestamped events to a JSONL file (and keeps them in memory)."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: list[dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def log(self, event: str, **fields: Any) -> dict[str, Any]:
        record = {"ts": round(time.time(), 3), "event": event, **fields}
        self.events.append(record)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record
