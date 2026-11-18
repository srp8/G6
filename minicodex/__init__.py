"""G6 Unit: a small, reproducible AI coding agent.

Built as the Applied Project Component of a UGA MIST 7400E group report on
Cisco's enterprise deployment of OpenAI Codex. The package implements a
scaled-down version of the Codex workflow: plan -> edit files -> run tests ->
read failures -> iterate, with guardrails and a reviewable action trace.
"""

__version__ = "0.1.0"

from minicodex.agent import Agent, AgentResult

__all__ = ["Agent", "AgentResult", "__version__"]
