# References

The documentation and papers the implementation was built against, and what
each one was used for. All links were checked in November 2026.

## Model APIs and tool calling

| Title | URL | Used for |
|---|---|---|
| OpenAI, *Function calling* guide | https://developers.openai.com/api/docs/guides/function-calling | Tool definitions in strict mode (`additionalProperties: false`, every field required), `tool_choice: "required"`, `parallel_tool_calls: false` for exactly one call per turn, returning results as `role: "tool"` messages with `tool_call_id` (`minicodex/tools.py`, `minicodex/agent.py`) |
| OpenAI, *Structured Outputs* guide | https://developers.openai.com/api/docs/guides/structured-outputs | The `response_format: {type: "json_schema", strict: true}` schema for the JSON-action fallback (`ACTION_RESPONSE_FORMAT`) |
| OpenAI Python SDK | https://github.com/openai/openai-python | Client construction, `max_retries=0` so retries are handled and counted by our own wrapper, and the SDK's exception classes (`RateLimitError`, `InternalServerError`, `APIConnectionError`, ...) |
| OpenRouter, *Tool calling* | https://openrouter.ai/docs/guides/features/tool-calling | Confirming that OpenRouter passes Chat Completions `tools`, `tool_choice` and `parallel_tool_calls` through unchanged |
| OpenRouter, *Structured outputs* | https://openrouter.ai/docs/guides/features/structured-outputs | `response_format` json_schema support across providers |
| OpenRouter, *Usage accounting* | https://openrouter.ai/docs/cookbook/administration/usage-accounting | `usage.cost` is returned on every response. The older `usage: {include: true}` flag is deprecated and no longer needed, so we dropped it. Reported cost is preferred over the price-table estimate (`cost_source` column) |
| OpenRouter, *Errors and debugging* | https://openrouter.ai/docs/api_reference/errors-and-debugging | Which statuses to retry (429, 502, 503, ...), honoring `Retry-After`, never retrying 402, and handling an error body that arrives with HTTP 200 |
| OpenRouter, *API limits* | https://openrouter.ai/docs/api_reference/limits | `GET /api/v1/key` to read credit usage before and after the benchmark runs |
| OpenRouter, *Reasoning tokens* | https://openrouter.ai/docs/guides/best-practices/reasoning-tokens | `reasoning.effort` (`--reasoning-effort`), counting `reasoning_tokens`, and passing `reasoning_details` back unmodified between tool turns |
| OpenRouter, *List models* (`GET /api/v1/models`) | https://openrouter.ai/api/v1/models | Checking model ids before the runs (`openai/gpt-6.1-sol`, `openai/gpt-5.6-luna`), their prices, and `supported_parameters` (tools, structured outputs, temperature), which the backend uses to pick an action protocol |

## Routing with Jev (TypeSafe)

| Title | URL | Used for |
|---|---|---|
| TypeSafe, *Quick start* | https://docs.typesafe.ai/introduction/quickstart | Request shape for `POST https://api.typesafe.ai/v1/systemone` (`model`, `state`, `questions`), bearer auth, and the response shape |
| TypeSafe, *Choice* primitive | https://docs.typesafe.ai/primitives/choice | The `model_tier` question: `instructions` plus `criteria` mapping each option to a description, answered with `choice`, `probabilities` and `confidence` |
| TypeSafe, *Confidence* | https://docs.typesafe.ai/confidence | How confidence differs from probability, and why to threshold it |
| TypeSafe, *Routing by confidence* and *Routing by probability* patterns | https://docs.typesafe.ai/patterns/confidence-routing, https://docs.typesafe.ai/patterns/probability-routing | The rule "use the cheap model only when Jev picks it with confidence at or above the threshold; otherwise use the strong model" (`--confidence-threshold`, default 0.6) |
| TypeSafe, *Jev with coding agents* | https://docs.typesafe.ai/introduction/coding-agents | Scoping Jev as the decision component inside our agent (routing), not as the code-writing model |
| TypeSafe, *State* | https://docs.typesafe.ai/concepts/state | Sending a structured state object (issue, file list, size signals, source excerpt) rather than one flat string |
| TypeSafe OpenAPI spec | https://api.typesafe.ai/openapi.json | Field names, `usage.input_tokens`, and error responses for the HTTP client and the offline fake |
| TypeSafe, *Models* | https://docs.typesafe.ai/models | Jev pricing (input tokens only, $0.042 per million), used for the `router_cost_usd` column |

## Agent design and the case

| Title | URL | Used for |
|---|---|---|
| Anthropic, *Building effective agents* (2024) | https://www.anthropic.com/engineering/building-effective-agents | The workflow vs agent distinction, keeping the agent a single tool-using loop with ground truth from the environment (test results) and a stopping condition |
| OpenAI, *A practical guide to building agents* | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf | Guardrails as layered defenses, clear tool definitions, and starting with a single agent before adding orchestration |
| OpenAI Codex, *Agent approvals & security* | https://developers.openai.com/codex/agent-approvals-security | The Codex controls our guardrails scale down: a sandbox limited to the workspace, network off by default, and an approval step (our human-review diff) |
| OpenAI Codex documentation | https://developers.openai.com/codex | How Codex works on tasks (plan, edit, run commands and tests, iterate), which the agent loop mirrors |

## Dataset and statistics

| Title | URL | Used for |
|---|---|---|
| Muennighoff et al. (2024), *OctoPack: Instruction tuning code large language models*, ICLR 2024 | https://arxiv.org/abs/2308.07124 | HumanEvalFix: the bug-fix task definition, bug-type labels, and its pass@1 evaluation |
| `bigcode/humanevalpack` dataset card | https://huggingface.co/datasets/bigcode/humanevalpack | Field names (`prompt`, `buggy_solution`, `test`, `entry_point`, ...) and the MIT license |
| Hugging Face Dataset Viewer API, *Rows* | https://huggingface.co/docs/dataset-viewer/rows | The `/rows` endpoint the conversion script uses, so no extra dependency is needed |
| Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *JASA*, 22(158), 209–212 | https://www.jstor.org/stable/2276774 | The Wilson score interval reported with every pass@1 (`minicodex/metrics.py`) |

## Tooling

| Title | URL | Used for |
|---|---|---|
| Python Packaging User Guide, *Writing your pyproject.toml* | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ | `pyproject.toml`, optional dependency groups and console scripts |
| Ruff documentation | https://docs.astral.sh/ruff/ | Lint rule selection and formatting |
| pytest documentation | https://docs.pytest.org/en/stable/ | Test layout, `tmp_path` and `monkeypatch` fixtures, and the `-p no:cacheprovider` flag for the sandboxed test runner |
