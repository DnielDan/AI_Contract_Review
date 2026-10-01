# Evaluation: `baseline` on the `dev` split

| Document | Problems | Caught | Missed | False alarms | Precision | Recall | Clause recall | Seconds |
|---|---|---|---|---|---|---|---|---|
| adhikari | 11 | 3 | 8 | 6 | 33% | 27% | 3/4 | 20.8 |
| lawson | 15 | 5 | 10 | 21 | 19% | 33% | 3/4 | 21.0 |
| williams_funding | 4 | 1 | 3 | 8 | 11% | 25% | 1/2 | 3.5 |
| cmi2 | 4 | 1 | 3 | 11 | 8% | 25% | 1/4 | 6.3 |
| proposed_revisions | 27 | 8 | 19 | 16 | 33% | 30% | 3/8 | 20.7 |
| **Overall** | 61 | 18 | 43 | 62 | 22% | 30% | 11/22 | 72.3 |

- Matrix-related problems caught: 18/54 (33%)
- Sentences flagged in total: 80 of 1259

Labels come from OSP's own markup of these contracts (see evaluation/README.md). "ok" means OSP
left a sentence unchanged, not that OSP confirmed it, so precision is a lower bound.
