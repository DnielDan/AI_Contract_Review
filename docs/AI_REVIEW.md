# AI review: how it works, how to change it, and where it stands

This guide is for developers working on the AI contract review (US-7, US-12). To set up an API key
and turn the AI review on, follow "Adding an API key" in the main [README](../README.md).

## How it works
The app scans contracts only with an AI provider. OSP decided (sponsor meeting, 11/18/2026) that the
tool will be used only once Auburn's agreement with an AI provider is signed, so the old TF-IDF matcher
is no longer a fallback; it is kept unchanged in `evaluation/tfidf_matcher.py` as the accuracy baseline.

**Before a scan:** while `LLM_PROVIDER` or its key is missing (`llm_providers.configuration_problem`),
`GET /api/config` reports `ai_ready: false` with the reason, the workbench shows a yellow "AI review is
not set up" banner, and `POST /api/scans` turns every upload down with a 503 before reading it. The
server still starts and logs a warning, so reviewers see why instead of a dead page.

When a contract is scanned (`main.scan_contract_with_results`, which also returns the flags as data for
the browser):

1. The upload is converted to plain text (`contract_to_txt.py`).
2. `main.ai_flags` calls `llm_review.review_contract`, which sends the contract text and the Ts&Cs
   Matrix's "Common Problems" to the model. The model returns each problem passage with the matrix
   sheet (category) and the Common Problem it matches, a short explanation, a suggested replacement,
   and a confidence. If the call fails (rate limit, outage, unreadable reply), the scan **fails** with
   "Could not review <file>. The AI service (<provider>) did not return a usable result", and the cause
   is logged (`main.AIReviewError`, `main.failure_message`).
3. For each AI flag, the "Why", "1st response to Sponsor" and Auburn's preferred language are looked
   up from the matrix row the model named, so that guidance always comes from the matrix. The model's
   own explanation and suggested change are shown separately and labeled "AI". A named row that is
   not in the matrix is marked "(not found in the matrix)", and a passage that cannot be located in
   the text is listed at the end of the document instead of being dropped.
4. FAR clauses are never sent to the model; they are highlighted by the exact-match lookup in
   `flag_FAR_clauses.py`.
5. The flagged text becomes the annotated `_scanned.docx` (`flag_FAR_clauses.annotate_contract`). A line at
   the top names the AI provider and model that flagged the language. The contract keeps its paragraphs;
   a paragraph with flagged language is highlighted yellow and followed by a "Flagged sentence" line and
   the matrix guidance (`flag_problem_language.write_flagged_text`). Everything
   the tool adds is highlighted gray: the Ts&Cs guidance, the AI's lines (also italic blue), and a note
   from the FAR Matrix (title, status, acceptance criteria, request to sponsor) after the first mention
   of each FAR clause. FAR clause numbers keep their status colors. The color legend explains all of this.

### Limits on AI calls
- **Timeout:** each request waits at most `LLM_TIMEOUT_SECONDS` (default 300) for the provider; for
  Claude, whose reply is streamed, that is the longest pause allowed. A timeout fails the scan with
  "did not answer in time" (`llm_providers.LLMTimeoutError`).
- **No resending of a cut-off reply:** a reply that stops at its output limit (Claude `stop_reason`
  `max_tokens`, or `finish_reason` `length` elsewhere) fails the scan at once with "cut off before it
  finished" (`ReplyCutOffError`); sending the same request again would be cut off the same way. Raise
  `LLM_MAX_TOKENS` (default 16000 for Claude, the provider's default otherwise) or lower `LLM_EFFORT`.
- **At most two replies per contract:** a reply that cannot be read, or is not a list of issues, is
  asked for once more (`llm_review.MAX_REPLY_ATTEMPTS`); anything else fails at once. Asking for raw
  JSON when a model rejects forced tool calls does not count, since the rejection generates nothing.
  The SDKs still retry connection errors, rate limits and server errors twice with backoff
  (`SDK_MAX_RETRIES`).
- **Effort:** `LLM_EFFORT` (low, medium, high) is sent as `output_config.effort` to Claude and as
  `reasoning_effort` to OpenAI-compatible providers; empty means the model's default.
- **One contract scan at a time** (`main._scan_turn_for`): the others stay "queued", with nothing on
  disk, and can be cancelled while they wait. Cancelling is also checked before a second reply is asked
  for; a request already sent finishes or times out.
- Invalid values for these settings are reported like a missing key: uploads are turned down with the
  reason (`llm_providers.configuration_problem`).

The prompt fences the contract between markers made from a hash of the contract and tells the model,
before and after it, to treat the contract as data, not instructions. That, the matrix-backed guidance,
and the injection check (`python -m evaluation.injection_check --no-save`) are described in
[DATA_HANDLING.md](DATA_HANDLING.md), with where contract text goes, what is logged, and how keys are
kept out of logs and the repository (US-13). **Changing `_build_prompt` changes accuracy too: rescore on
`dev` and rerun the injection check afterwards.**

### File map
| File | What it does |
|---|---|
| `llm_providers.py` | Checks the settings (`configuration_problem`), sends a prompt to the provider named by `LLM_PROVIDER`, and returns structured JSON. OpenRouter and Gemini use the OpenAI-compatible API (`_OPENAI_COMPATIBLE_PRESETS`); Claude uses the Anthropic SDK with structured outputs (`_anthropic`). |
| `llm_review.py` | Builds the prompt (`_build_prompt`) and the reply format (`_issue_schema`), reads the reply (`review_contract`), and looks up matrix guidance (`_issue_details`). |
| `main.py` | Reads settings from `.env`, checks the matrices at startup (`check_matrices`), runs the AI review (`ai_flags`) and reports its failures (`AIReviewError`), turns uploads down while the AI is not set up (`ai_setup_problem`), and serves the workbench and its API. |
| `scan_results.py` | Turns a scan's flags and FAR clauses into the data the workbench shows (`build_results`). |
| `evaluation/scanners.py` | The `llm` scanner (the AI review) and the `baseline` scanner (`evaluation/tfidf_matcher.py`, the inherited matcher) scored on the labeled test set. |
| `tests/fakes.py` | The stand-in AI review used by the tests and by the browser test's server (`tests/e2e_server.py`). |
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
- `tests/test_llm_review.py`: provider selection and settings checks, matrix-backed output, unmatched
  quotes, reply formats the models have actually produced, retry, and failures reported without a
  matcher fallback.
- `tests/test_api.py`: uploads turned down while the AI is not set up, and a failed AI review failing
  the scan with its reason.
- `tests/test_llm_limits.py`: timeouts, cut-off replies, the two-reply cap, effort and output limit,
  invalid settings, using fake OpenAI and Anthropic clients.
- `tests/test_config.py`: matrix paths and the startup matrix check.
- `tests/test_tfidf_baseline.py`: the inherited matcher kept as the evaluation baseline.
- `tests/conftest.py`: clears `LLM_PROVIDER` before every test and makes any real provider call fail
  the test, so a developer's `.env` key is never used. Full scans use the `fake_ai` fixture, which
  answers with the stand-in in `tests/fakes.py`.

## Status (November 2026)
**Done**
- US-7: settings and keys in a gitignored `.env`; provider and model chosen there; matrix paths
  configurable; matrices checked at startup.
- US-12 (implementation): AI review for OpenRouter, Claude and Gemini behind one setting; matrix-backed
  guidance; FAR exact lookup kept; `llm` evaluation scanner; offline tests.
- AI-only scanning (sponsor decision, 11/18/2026): no matcher fallback; a failed AI review fails the
  scan with its reason; uploads are turned down while no provider is set up; the matcher moved to
  `evaluation/` as the baseline.
- Limits on AI calls: request timeout, no resending of a cut-off reply, at most two replies per
  contract, optional output limit and effort, one contract scan at a time (see "Limits on AI calls").

**What the first live test showed (OpenRouter, free model)**
- The free NVIDIA model used earlier (`nemotron-3-super-120b-a12b:free`) was removed from OpenRouter;
  the default is now `nvidia/nemotron-3.5-super-vl:free`. Free models change without notice.
- The free model did not always follow the reply format (issues sent as text, JSON wrapped in prose,
  unreadable replies). The code now accepts these variants and retries once before failing the scan.
- It took 1 to 3.5 minutes per contract and flagged a different number of passages on repeated calls.
- `evaluation/results/llm_dev.md` records one scoring run as a prototype record only. It is not
  representative of the model that will be chosen.
- The Claude and Gemini paths are covered by the offline tests but have not yet been called with a
  real key.

**Open items**
- US-23: hand-off guide for IT to add the approved provider's key once the agreement is signed.
- When Claude or Gemini keys arrive: one test scan, then score on `dev` (more than one run).
- Choose the provider and model (US-12). A hosted provider may be used on real contracts only after
  OSP and Auburn IT approve it under a data-protection agreement.
- US-13: run the injection check against the chosen provider and model, and record the result in
  DATA_HANDLING.md. The offline parts are done: no contract text or keys in the log, no keys in the
  repository, the contract fenced in the prompt, text never rendered as HTML.
- US-17: tune the prompt and model on the `dev` split.
- Update the Cycle 2 report: it still names Azure OpenAI as the leading option.
