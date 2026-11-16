# Evaluation: `llm` on the `dev` split

| Document | Problems | Caught | Missed | False alarms | Precision | Recall | Clause recall | Seconds |
|---|---|---|---|---|---|---|---|---|
| adhikari | 11 | 8 | 3 | 3 | 73% | 73% | 3/4 | n/a |
| lawson | 15 | 9 | 6 | 3 | 75% | 60% | 3/4 | 61.4 |
| williams_funding | 4 | 1 | 3 | 7 | 12% | 25% | 1/2 | 113.1 |
| cmi2 | 4 | 3 | 1 | 7 | 30% | 75% | 3/4 | 149.0 |
| proposed_revisions | 27 | 14 | 13 | 17 | 45% | 52% | 4/8 | 124.7 |
| **Overall** | 61 | 35 | 26 | 37 | 49% | 57% | 14/22 | 448.2 |

- Matrix-related problems caught: 35/54 (65%)
- Sentences flagged in total: 72 of 1259

Labels come from OSP's own markup of these contracts (see evaluation/README.md). "ok" means OSP
left a sentence unchanged, not that OSP confirmed it, so precision is a lower bound.

Run on 2026-11-12 with LLM_PROVIDER=openrouter and model `nvidia/nemotron-3.5-super-vl:free`
(OpenRouter free tier), one model call per contract. Seconds are the model call time; the adhikari
call was not timed, so the overall time covers the other four contracts. This is a single run: the
same contract can get a different set of flags on another call, so repeat runs are needed before
treating these numbers as stable.
