# AI review: how it works, how to change it, and where it stands

This guide is for developers working on the AI contract review (US-7, US-12). To set up an API key
and turn the AI review on, follow "Adding an API key" in the main [README](../README.md).

## How it works
When a contract is scanned (`main.scan_contract`):

1. The upload is converted to plain text (`contract_to_txt.py`).
2. `main.flag_problem_language` decides how problem language is flagged:
   - **`LLM_PROVIDER` set in `.env`:** `llm_review.llm_flag_problem_language` sends the contract text
     and the Ts&Cs Matrix's "Common Problems" to the model. The model returns each problem passage
     with the matrix sheet (category) and the Common Problem it matches, a short explanation, a
     suggested replacement, and a confidence.
   - **`LLM_PROVIDER` empty:** the TF-IDF matcher (`flag_problem_language._flag_problem_language`).
   - **The AI call fails** (missing key, rate limit, outage, unreadable reply): the scan falls back to
     the TF-IDF matcher and the reviewer sees an "AI review unavailable" warning. This is the fallback
     US-12 asks for and that US-18 shows in the new interface.
3. For each AI flag, the "Why", "1st response to Sponsor" and Auburn's preferred language are looked
   up from the matrix row the model named, so that guidance always comes from the matrix. The model's
   own explanation and suggested change are shown separately and labeled "AI". A named row that is
   not in the matrix is marked "(not found in the matrix)", and a passage that cannot be located in
   the text is listed at the end of the document instead of being dropped.
4. FAR clauses are never sent to the model; they are highlighted by the exact-match lookup in
   `flag_FAR_clauses.py`.
5. The flagged text becomes the annotated `_scanned.docx`, as before.

The prompt tells the model to treat the contract text as data, not instructions, as a first guard
against prompt injection (full security checks are US-13).

### File map
| File | What it does |
|---|---|
| `llm_providers.py` | Sends a prompt to the provider named by `LLM_PROVIDER` and returns structured JSON. OpenRouter and Gemini use the OpenAI-compatible API (`_OPENAI_COMPATIBLE_PRESETS`); Claude uses the Anthropic SDK with structured outputs (`_anthropic`). |
| `llm_review.py` | Builds the prompt (`_build_prompt`) and the reply format (`_issue_schema`), reads the reply (`review_contract`), looks up matrix guidance (`_issue_details`), and writes the flagged text (`llm_flag_problem_language`). |
| `main.py` | Reads settings from `.env`, checks the matrices at startup (`check_matrices`), and chooses AI or matcher with the fallback (`flag_problem_language`). |
| `evaluation/scanners.py` | The `llm` scanner used to score the AI review on the labeled test set. |
| `.env.example` | Template for `.env`, which holds the settings and API keys and is never committed. |

## Common changes
- **Switch provider or model:** edit `LLM_PROVIDER` and `LLM_MODEL` in `.env`. No code changes.
- **Change what the model is told:** edit `_build_prompt` in `llm_review.py`. The same prompt is used
  for every provider, so rescore each model you care about afterwards (see below): wording that helps
  one model can hurt another.
- **Change what the model returns:** add the field to `_issue_schema` and show it in `_issue_details`.
- **Add a provider:** if it offers an OpenAI-compatible API, add an entry (base URL, key variable,
  default model) to `_OPENAI_COMPATIBLE_PRESETS` in `llm_providers.py` and a key line to
  `.env.example`; otherwise add a function like `_anthropic` and a branch in `generate_structured`.
- **Change the default model** of a provider: edit `default_model` in `_OPENAI_COMPATIBLE_PRESETS`, or
  `_ANTHROPIC_DEFAULT_MODEL` for Claude.

## Measuring accuracy
```
python -m evaluation.evaluate --scanner llm --split dev --no-save
```
- Uses the provider and model in `.env` and sends one request per contract (5 for `dev`).
- Score on `dev` while developing. `holdout` is reserved for the Cycle 3 validation pass; do not tune
  against it.
- Without `--no-save`, results overwrite `evaluation/results/llm_dev.md`.
- Accuracy belongs to a model, not to the code: rescore whenever the provider, model, or prompt changes,
  and run more than once, because the same model can flag different passages on different calls.
- Compare with the matcher: `python -m evaluation.evaluate --scanner baseline --split dev --no-save`.

## Tests
`python -m pytest` runs everything offline; no test calls a real AI service.
- `tests/test_llm_review.py`: provider selection and errors, matrix-backed output, unmatched quotes,
  reply formats the models have actually produced, retry, and the fallback to the matcher.
- `tests/test_config.py`: matrix paths, threshold, and the startup matrix check.
- `tests/conftest.py`: clears `LLM_PROVIDER` before every test, so a developer's `.env` key is never
  used by the test suite. Tests that need an AI reply replace the network call with a fixed one.

## Status (November 2026)
**Done**
- US-7: settings and keys in a gitignored `.env`; provider and model chosen there; matrix paths and
  the matcher threshold configurable; matrices checked at startup.
- US-12 (implementation): AI review for OpenRouter, Claude and Gemini behind one setting; matrix-backed
  guidance; FAR exact lookup kept; fallback to the matcher with a warning; `llm` evaluation scanner;
  offline tests.

**What the first live test showed (OpenRouter, free model)**
- The free NVIDIA model used earlier (`nemotron-3-super-120b-a12b:free`) was removed from OpenRouter;
  the default is now `nvidia/nemotron-3.5-super-vl:free`. Free models change without notice.
- The free model did not always follow the reply format (issues sent as text, JSON wrapped in prose,
  unreadable replies). The code now accepts these variants and retries once before falling back.
- It took 1 to 3.5 minutes per contract and flagged a different number of passages on repeated calls.
- `evaluation/results/llm_dev.md` records one scoring run as a prototype record only. It is not
  representative of the model that will be chosen.
- The Claude and Gemini paths are covered by the offline tests but have not yet been called with a
  real key.

**Open items**
- When Claude or Gemini keys arrive: one test scan, then score on `dev` (more than one run).
- Choose the provider and model (US-12). A hosted provider may be used on real contracts only after
  OSP and Auburn IT approve it under a data-protection agreement.
- US-13: security checks (data handling, keys, prompt injection) for the chosen provider.
- US-17: tune the prompt and model on the `dev` split.
- Update the Cycle 2 report: it still names Azure OpenAI as the leading option.
