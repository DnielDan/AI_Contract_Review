# AI provider and model recommendation (US-12)

This recommendation is for OSP and Auburn IT. It compares the AI models the team tested on the labeled
sample contracts and says which one to set up once Auburn's agreement with an AI provider is signed.

## Recommendation
**Use Google Gemini (Flash) if Auburn's agreement is with Google.** On the sample contracts it had the
fewest false alarms of any model tested while catching as many problems as the others, and the student
team could test it at no cost. If the agreement is with Anthropic instead, Claude works with the same
code, but it needs prompt tuning first (see "If the agreement is with Anthropic").

Whichever model is used, the tool is a **first pass**: the best model caught about half of the labeled
problems, so the reviewer still reads the whole contract.

## How the models were tested
- **Test set:** the `dev` split of `evaluation/labels.csv`, which has 5 sample contracts with 61
  problem sentences labeled by the team against the Ts&Cs Matrix (22 problem clauses).
- **Measure:** `python -m evaluation.evaluate --scanner llm --split dev`. "Caught" is a labeled problem the
  model flagged. A "false alarm" is a flagged sentence labeled acceptable. Precision is caught ÷ (caught +
  false alarms).
- **When:** November 12–17, 2026, with the prompt in the code at the time (V0). The prompt has since been
  fenced against prompt injection (DATA_HANDLING.md); that change adds no instructions about what to flag.
- **Keys:** free tiers (Gemini, OpenRouter) and a personal Anthropic key, on sample contracts only.
- Full run logs and per-contract scores are kept by the team outside the repository
  (`Cycle3-Fall2026/llm-eval-results/RESULTS.md`).

## Results (dev split, 61 labeled problems)
| Model (standard prompt) | Caught | False alarms | Precision | Cost of the 5 contracts |
|---|---|---|---|---|
| **Gemini `gemini-flash-latest`** | 30 | **24** | **56%** | free tier |
| Nemotron 3.5 Super (OpenRouter, free) | 32 | 28 | 53% | free tier |
| Claude Sonnet 5.5 | 23 | 45 | 34% | $0.48 |
| Claude Haiku 5.5 | 18 | 44 | 29% | $0.04 |
| TF-IDF matcher (the tool before the AI review) | 18 | 62 | 22% | – |

**How to read these numbers**
- **Precision is a lower bound.** The labels are not exhaustive, so some "false alarms" may be real issues.
- **One run per model is only a rough ranking.** The same model and prompt flagged different passages on
  repeated calls (one Claude Haiku prompt scored 36 and then 23).
- **Asking for more recall costs precision on every model.** Prompts telling the model that a missed
  problem is worse than an extra flag caught up to 36 problems, but with 92–104 false alarms.
- **Nemotron is not an option for OSP.** It is reached through OpenRouter, which forwards contracts to
  third-party hosts; it was tested only as a free comparison.
- **`gemini-3.8-flash`** (a fixed version) was also tested, but the free tier's rate limits stopped the
  run after 3 of the 5 contracts, so its score is not comparable.
- The `holdout` split (2 contracts kept out of all tuning) has not been run yet.

## Why Gemini
1. **Fewest false alarms for the same recall.** Gemini and Claude caught a similar number of problems,
   but Claude flagged 2–4 times as many acceptable passages. Every false alarm is a passage the reviewer
   has to read and dismiss.
2. **No tuning needed for the results above.** Gemini's score is with the tool's standard prompt.
3. **It works with the tool's settings as delivered:** `LLM_PROVIDER=gemini`, the key in
   `GEMINI_API_KEY`, and the model in `LLM_MODEL`.

## If the agreement is with Anthropic
Claude works with the same code (`LLM_PROVIDER=anthropic`). Before relying on it:
- **Tune the prompt for Claude** on the `dev` split (US-17). The prompt that works for Gemini gave Claude
  many more false alarms, and Sonnet was not clearly better than Haiku.
- **Set `LLM_EFFORT=low` for Haiku.** At its default effort, Haiku spent its output on thinking and was
  cut off on the longest contract (proposed_revisions) at 16,000 output tokens. The tool now fails such a
  reply with "cut off before it finished" instead of resending it.
- **Cost is small:** a full `dev` run (5 contracts) cost $0.03–0.06 with Haiku and about $0.50 with Sonnet.

## Before real contracts are used
1. Score the chosen model on `dev` again with the approved key, more than once, and record the results.
2. Run the injection check (`python -m evaluation.injection_check`) and record the result in
   DATA_HANDLING.md. It has not yet returned results from a live model: the free tier was rate-limited.
3. Run the `holdout` split once, as the final check.
4. **Use a paid or agreement-covered key, not a free tier.** During testing the free Gemini tier often
   refused requests (429 Too Many Requests, 503 Service Unavailable), and each refusal fails that scan. Free
   tiers can also let the provider keep inputs (DATA_HANDLING.md).
5. Set the model to a fixed version, not an alias like `gemini-flash-latest`, which Google can point at
   a newer model without notice. Any change of model means rescoring.
