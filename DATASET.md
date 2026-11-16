# Dataset

## Why a scaled-down dataset

Cisco's Codex deployment works against enterprise codebases: thousands of
repositories, millions of lines of code, CI pipelines, and a live stream of
issues and pull requests. That data is proprietary, enormous, and impossible
to reproduce in a class project. This prototype keeps the *shape* of that
workload, "here is a repo, here is an issue, the tests fail, fix it", and
shrinks it to **38 self-contained task repos, about 80 KB on disk**. Every
task can be run on a laptop in seconds, graded automatically by its unit
tests, and inspected line by line.

| Enterprise workload (Cisco + Codex) | Scaled-down stand-in (this repo) |
|---|---|
| Service repositories with CI | One small Python repo per task, with a pytest suite |
| Issue or ticket assigned to the agent | `issue.md` |
| CI pass/fail as the acceptance signal | The task's tests, re-run on a pristine copy after the agent finishes |
| A mix of easy fixes and multi-file changes | Two suites: real single-function bugs and hand-written multi-file and feature tasks |

## Suites

### `humanevalfix`: 30 real bug-fix tasks (primary)

- **Source:** the Python split of HumanEvalFix, part of the
  [HumanEvalPack](https://huggingface.co/datasets/bigcode/humanevalpack)
  benchmark (`bigcode/humanevalpack`, config `python`, split `test`, 164 problems).
  HumanEvalFix takes each HumanEval problem and inserts one human-written bug
  into the reference solution. Each problem comes with its unit tests and a
  bug-type label (value misuse, operator misuse, missing logic, ...).
- **Paper:** Muennighoff, N., Liu, Q., Zebaze, A., Zheng, Q., Hui, B., Zhuo, T. Y.,
  Singh, S., Tang, X., von Werra, L., & Longpre, S. (2024). *OctoPack: Instruction
  tuning code large language models.* International Conference on Learning
  Representations (ICLR 2024). https://arxiv.org/abs/2308.07124
- **License:** MIT (as declared on the dataset card). The HumanEval problems
  come from Chen et al. (2021), also released under MIT.
- **Sampling:** 30 of the 164 problems, drawn with `random.Random(7400).sample`
  (seed 7400, the course number) and kept in dataset order. The selection is
  listed in `benchmark/suites/humanevalfix/manifest.json`.
- **Conversion:** `scripts/build_humanevalfix.py` wraps every sampled problem
  as a mini repo:
  - `repo/<entry_point>.py`: the problem's prompt (imports, signature, docstring,
    helper functions) followed by the **buggy** solution
  - `repo/tests/test_<entry_point>.py`: the dataset's `check()` harness, called
    from a pytest test
  - `issue.md`: the docstring plus "the unit tests fail, fix the bug, do not
    modify the tests"
  - `task.json`: source id, bug type, failure symptom, and a difficulty label
  The reference fix is never written into the task. `--verify` re-checks every
  generated task (the buggy code must fail its tests and the reference
  solution must pass them); all 30 pass that check.
- **Composition:** bug types are value misuse 13, operator misuse 4, variable
  misuse 4, missing logic 4, excess logic 4, function misuse 1. Difficulty is a
  transparent size heuristic on the reference solution (non-blank lines:
  up to 3 = easy, up to 9 = medium, more = hard), which gives easy 15, medium 11, hard 4.

Rebuild it exactly:

```bash
python scripts/build_humanevalfix.py --verify          # 30 tasks, seed 7400
python scripts/build_humanevalfix.py --n 50 --seed 1   # a different sample
```

### `custom`: 8 hand-written tasks (secondary)

Tiny repos with seeded defects that HumanEvalFix does not cover: a bug that
spans two files (`04_two_file_bug`), a feature request implemented against
existing tests (`05_feature_request`), and a decoy `.env` file that
demonstrates the secret-file guardrail (`01_off_by_one`). Written for this
project and released with it.

## Size

| Suite | Tasks | Files | Bytes |
|---|---|---|---|
| humanevalfix | 30 | 120 + manifest | ~71 KB |
| custom | 8 | 40 | ~8 KB |

## Known limitations

- HumanEval problems are short, self-contained functions, and they have been
  public since 2021, so frontier models have very likely seen them during
  training. High solve rates here measure the agent loop working end to end;
  they don't show that it can handle large unfamiliar codebases.
- One bug per task, with the tests visible to the agent. Real issues are
  vaguer and often lack a failing test.
- 38 tasks give wide confidence intervals. That is why every pass@1 in this
  repo is reported with a Wilson 95% interval.
