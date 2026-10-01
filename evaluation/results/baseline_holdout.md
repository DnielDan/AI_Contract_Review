# Evaluation: `baseline` on the `holdout` split

| Document | Problems | Caught | Missed | False alarms | Precision | Recall | Clause recall | Seconds |
|---|---|---|---|---|---|---|---|---|
| hale | 4 | 3 | 1 | 12 | 20% | 75% | 2/2 | 8.5 |
| mou | 6 | 0 | 6 | 17 | 0% | 0% | 0/3 | 10.7 |
| **Overall** | 10 | 3 | 7 | 29 | 9% | 30% | 2/5 | 19.1 |

- Matrix-related problems caught: 3/10 (30%)
- Sentences flagged in total: 32 of 336

Labels come from OSP's own markup of these contracts (see evaluation/README.md). "ok" means OSP
left a sentence unchanged, not that OSP confirmed it, so precision is a lower bound.
