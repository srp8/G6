# Benchmark summary

Written by `minicodex-report` from `results/runs/*/results.csv`. pass@1 is the share of task attempts solved by a single agent run (no best-of-k), graded against the pristine tests; with --repeat 3 each task counts three times. The interval is a Wilson 95% CI. Cost is OpenRouter's reported billed cost (plus the Jev router's per-token price where used).

## Results by run and suite

| run | suite | solved | pass@1 | 95% CI | mean iters | mean time (s) | mean tokens | total cost | cost / solved |
|---|---|---|---|---|---|---|---|---|---|
| jev_cascade_full | custom | 24/24 | 100.0% | 86.2%–100.0% | 1.04 | 9.4 | 4,980 | $0.0745 | $0.0031 |
| jev_cascade_full | humanevalfix | 90/90 | 100.0% | 95.9%–100.0% | 1.00 | 11.1 | 6,597 | $0.1762 | $0.0020 |
| jev_cascade_full | all | 114/114 | 100.0% | 96.7%–100.0% | 1.01 | 10.8 | 6,257 | $0.2507 | $0.0022 |
| luna_full | custom | 24/24 | 100.0% | 86.2%–100.0% | 1.12 | 9.8 | 5,011 | $0.0290 | $0.0012 |
| luna_full | humanevalfix | 90/90 | 100.0% | 95.9%–100.0% | 1.03 | 11.4 | 6,984 | $0.1362 | $0.0015 |
| luna_full | all | 114/114 | 100.0% | 96.7%–100.0% | 1.05 | 11.0 | 6,569 | $0.1651 | $0.0014 |
| luna_noretry | custom | 21/24 | 87.5% | 69.0%–95.7% | 1.00 | 8.9 | 4,606 | $0.0278 | $0.0013 |
| luna_noretry | humanevalfix | 90/90 | 100.0% | 95.9%–100.0% | 1.00 | 10.9 | 6,603 | $0.1311 | $0.0015 |
| luna_noretry | all | 111/114 | 97.4% | 92.5%–99.1% | 1.00 | 10.5 | 6,183 | $0.1589 | $0.0014 |
| mock_all | custom | 7/8 | 87.5% | 52.9%–97.8% | 1.00 | 0.4 | 5,123 | $0.0000 | $0.0000 |
| mock_all | humanevalfix | 0/30 | 0.0% | 0.0%–11.4% | 0.00 | 0.2 | 4,480 | $0.0000 | n/a |
| mock_all | all | 7/38 | 18.4% | 9.2%–33.4% | 0.21 | 0.2 | 4,616 | $0.0000 | $0.0000 |
| sol_full | custom | 24/24 | 100.0% | 86.2%–100.0% | 1.12 | 9.9 | 4,936 | $0.2396 | $0.0100 |
| sol_full | humanevalfix | 90/90 | 100.0% | 95.9%–100.0% | 1.00 | 11.6 | 6,737 | $1.1257 | $0.0125 |
| sol_full | all | 114/114 | 100.0% | 96.7%–100.0% | 1.03 | 11.2 | 6,358 | $1.3654 | $0.0120 |
| sol_noretry | custom | 21/24 | 87.5% | 69.0%–95.7% | 1.00 | 10.0 | 4,478 | $0.2278 | $0.0108 |
| sol_noretry | humanevalfix | 90/90 | 100.0% | 95.9%–100.0% | 1.00 | 11.9 | 6,823 | $1.0888 | $0.0121 |
| sol_noretry | all | 111/114 | 97.4% | 92.5%–99.1% | 1.00 | 11.5 | 6,330 | $1.3166 | $0.0119 |

## Failure taxonomy (unsolved attempts)

| run | wrong_fix | budget_exhausted | invalid_action | guardrail_block | api_error |
|---|---|---|---|---|---|
| jev_cascade_full | 0 | 0 | 0 | 0 | 0 |
| luna_full | 0 | 0 | 0 | 0 | 0 |
| luna_noretry | 0 | 3 | 0 | 0 | 0 |
| mock_all | 31 | 0 | 0 | 0 | 0 |
| sol_full | 0 | 0 | 0 | 0 | 0 |
| sol_noretry | 0 | 3 | 0 | 0 | 0 |

## Retry loop vs no-retry baseline

| suite | no-retry run | full-loop run | no-retry pass@1 | full pass@1 | gain (pp) | rescued by retry | cost no-retry | cost full |
|---|---|---|---|---|---|---|---|---|
| custom | luna_noretry | luna_full | 87.5% | 100.0% | +12.5 | 1 | $0.0278 | $0.0290 |
| humanevalfix | luna_noretry | luna_full | 100.0% | 100.0% | +0.0 | 0 | $0.1311 | $0.1362 |
| all | luna_noretry | luna_full | 97.4% | 100.0% | +2.6 | 1 | $0.1589 | $0.1651 |
| custom | sol_noretry | sol_full | 87.5% | 100.0% | +12.5 | 1 | $0.2278 | $0.2396 |
| humanevalfix | sol_noretry | sol_full | 100.0% | 100.0% | +0.0 | 0 | $1.0888 | $1.1257 |
| all | sol_noretry | sol_full | 97.4% | 100.0% | +2.6 | 1 | $1.3166 | $1.3654 |

## Router decisions

| run | tasks | cheap-first | strong | sources | escalated | cheap solved w/o escalation | mean confidence | mean / p95 latency | router cost |
|---|---|---|---|---|---|---|---|---|---|
| jev_cascade_full | 114 | 107 | 7 | {"jev": 113, "low_confidence": 1} | 0 | 107 | 0.92 | 140 / 185 ms | $0.003935 |

## Reliability (repeat runs)

| run | repeats | pass@1 per repeat | stdev | same outcome every repeat |
|---|---|---|---|---|
| jev_cascade_full | 3 | 100.0%, 100.0%, 100.0% | 0.0 pp | 100.0% |
| luna_full | 3 | 100.0%, 100.0%, 100.0% | 0.0 pp | 100.0% |
| luna_noretry | 3 | 97.4%, 97.4%, 97.4% | 0.0 pp | 100.0% |
| sol_full | 3 | 100.0%, 100.0%, 100.0% | 0.0 pp | 100.0% |
| sol_noretry | 3 | 97.4%, 97.4%, 97.4% | 0.0 pp | 100.0% |

Total cost across all runs: **$3.2567**
