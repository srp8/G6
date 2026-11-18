# Requirements trace

This maps each requirement phrase from the MIST 7400E project guidelines to the
place in this repository that satisfies it. Paths are relative to the repo root.

## "Develop and evaluate an AI artifact relevant to the selected use case"

The use case is Cisco's enterprise rollout of OpenAI Codex: an agent that takes an
issue, edits code, runs the build and tests, reads the failures and iterates, under
sandboxing and human review.

| What the artifact does | Evidence |
|---|---|
| A working coding agent: plan, read, edit, run tests, read failures, iterate | `minicodex/agent.py` (loop), `minicodex/tools.py` (the six tools) |
| Built on a real model API through the provider Cisco's case centers on (OpenAI models via OpenRouter), using native tool calling | `minicodex/backends/openai_backend.py`; `action_mode=tools` in every real-run CSV |
| Enterprise controls scaled down: sandboxed working copy, no shell or network, secret files blocked, read-only tests, audit trace, human-review diff | `minicodex/guardrails.py`, `minicodex/trace.py`, `results/runs/*/traces/` |
| Cost control the way an enterprise would manage Codex spend: Jev routes each task to a cheap or a strong model, and a cascade escalates failures | `minicodex/router.py`, `minicodex/bench.py` (`--router jev --cascade`) |
| Evaluated on a real benchmark against a baseline and alternatives | `results/summary.md`, `notebooks/benchmark_report.ipynb` |
| Diagrams of the design | `docs/diagrams/architecture.png`, `docs/diagrams/agent-loop.png`, `docs/diagrams/two-file-bug-run.png` |

## "Scale the dataset down to a manageable level"

| Evidence | Detail |
|---|---|
| `DATASET.md` | Frames the scale-down: Cisco's enterprise repos and issue streams become 38 task repos, about 80 KB |
| `benchmark/suites/humanevalfix/` | 30 real bug-fix tasks sampled from HumanEvalFix (bigcode/humanevalpack, MIT) with fixed seed 7400 |
| `scripts/build_humanevalfix.py --verify` | Rebuilds the sample exactly; checks that every buggy version fails and every reference fix passes |
| `benchmark/suites/humanevalfix/manifest.json` | The exact selection, seed and source ids |
| `benchmark/suites/custom/` | 8 hand-written tasks for cases HumanEvalFix lacks (multi-file bug, feature request, secret-file decoy) |

## "Reproducible codebase (Jupyter Notebook or repository link)"

| Evidence | Detail |
|---|---|
| This repository | `pip install -e ".[notebook,dev]"`, then the README quickstart |
| Offline by default | The mock backend and the fake Jev client run every code path with no keys (`minicodex-bench` with no flags) |
| Tests and lint | `pytest` (85 tests, including mocked OpenRouter and Jev HTTP); `ruff check .`; CI in `.github/workflows/ci.yml` |
| Fixed seeds and committed outputs | Dataset seed 7400; results CSVs, run configs and traces committed under `results/runs/` |
| Notebook | `notebooks/benchmark_report.ipynb`, executed top to bottom with the committed results; figures in `results/figures/` |
| Secrets handling | `.env.example` only; keys are read from the environment and stripped from the test subprocess |

## "Video demonstration ... running prototype, model outputs, and architectural design"

See the run-of-show at the end of this file. Material for each part:

| Part | Evidence |
|---|---|
| Running prototype | `minicodex --task benchmark/suites/custom/04_two_file_bug --backend openai --router jev` (live), or offline with `--backend mock` |
| Model outputs | The CLI's printed diff and trace; `results/summary.md`; the notebook tables |
| Architectural design | `docs/diagrams/*.png`; the README architecture section |

## Model Evaluation: "performance metrics, validation methodologies, bias detection, reliability assessments"

| Phrase | Evidence |
|---|---|
| Performance metrics | pass@1 per suite with a Wilson 95% CI, mean iterations, wall time, tokens, total cost, cost per solved task (`minicodex/metrics.py`, `results/summary.md`, notebook sections 1-3 and 8) |
| Validation methodologies | Every attempt is graded on a **pristine copy of the tests**, so the agent can't pass by editing them (`grade()` in `minicodex/bench.py`). There is a no-retry baseline vs the full loop, and three configurations on the same tasks. The dataset is verified (buggy fails, reference passes). There are unit and end-to-end tests of the pipeline (`tests/`) |
| Bias detection | Results are split by suite (real benchmark vs hand-written), by bug type and by difficulty (`category` and `difficulty` columns). Router decisions are audited per suite to check whether Jev sends whole categories to one tier (notebook section 5). `DATASET.md` and the README discuss training-data contamination of public HumanEval problems as a source of optimistic bias |
| Reliability assessments | `--repeat 3` for every configuration: per-repeat pass@1, its standard deviation, and the share of tasks with the same outcome on every repeat (`reliability()` in `minicodex/metrics.py`, notebook section 7). Retries with backoff and an `api_error` failure class keep provider faults separate from model faults |

---

## Demo run-of-show (about 7 minutes)

| Time | Segment | On screen | Say |
|---|---|---|---|
| 0:00-0:40 | The case in one line | README title, then `docs/diagrams/architecture.png` | Cisco uses Codex to take an issue, edit code, run tests and iterate under guardrails. G6 Unit is that loop scaled down to a laptop. |
| 0:40-1:40 | Architecture | `architecture.png`, then `agent-loop.png` | The pieces: issue and repo in, Jev picks the model tier, the agent calls six tools, guardrails check every call, tests decide, and a trace plus a diff go to a human. |
| 1:40-3:10 | Live run | Terminal: `minicodex --task benchmark/suites/custom/04_two_file_bug --backend openai --router jev` | Point out the router line (tier, confidence), the agent fixing one file, the tests failing, then the second fix and the tests passing. End on the human-review diff. |
| 3:10-3:50 | Guardrails | `cat` the decoy `.env` in task 01; show a `guardrail_block` in a trace, or run `pytest tests/test_tools.py -q` | The agent never sees secrets, can't run a shell, and can't edit the tests that grade it. |
| 3:50-4:30 | Dataset | `DATASET.md`, `ls benchmark/suites/humanevalfix` | 30 real HumanEvalFix bugs, fixed seed, plus 8 hand-written tasks. This is enterprise data scaled down to about 80 KB. |
| 4:30-6:10 | Results | Notebook figures: `solve_rate_ci.png`, `cost_vs_solve_rate.png`, `retry_vs_noretry.png`, `router_decisions.png` | Solve rate with confidence intervals for Sol, Luna and Jev-routed. Cost per fix. What the retry loop adds over a one-shot patch. Where Jev sent tasks. |
| 6:10-6:40 | Evaluation rigor | `failure_taxonomy.png`, the reliability table, `docs/REQUIREMENTS_TRACE.md` | Pristine-test grading, failure taxonomy, three repeats per configuration, and contamination as the main caveat. |
| 6:40-7:10 | Business takeaway | `results/summary.md` | Routing keeps quality while cutting cost per fix, which is how an enterprise would control Codex spend at scale. Close with the limitations. |

**Backup if the network fails:** run the same commands with `--backend mock` (the fake Jev
router stays deterministic), and show the committed real-run figures.
