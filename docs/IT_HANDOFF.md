# Turning on the AI review: guide for Auburn IT (US-23)

The contract scanner is delivered **with the AI review turned off and no API key**. OSP will use it only
once Auburn's agreement with an AI provider (Google or Anthropic) is signed. This guide is for the IT staff
who then set it up. It takes about an hour, most of it the checks in step 5.

Until the key is added, the app starts and shows a yellow "AI review is not set up" banner, and turns
down every upload. Nothing is sent anywhere.

## 1. Before you start
- [ ] Auburn's agreement with the provider is signed, and you have confirmed its data-protection terms
      (retention, use for training, where data is processed). See [DATA_HANDLING.md](DATA_HANDLING.md).
- [ ] You have an API key from **Auburn's account** with that provider, covered by the agreement. Do not
      use a free or personal key: free tiers can keep inputs, and they refuse requests when busy, which
      fails the scan.
- [ ] You know which computer will run the app and who will reach it (step 6).

## 2. Install
On the computer that will run the app, follow **Setup** and **Running the app** in the
[README](../README.md): Python 3.11, Node.js 22, `pip install -r requirements.txt`, and build the
workbench (`npm ci`, `npm run build` in `frontend/`).

## 3. Add the key and choose the model
1. In the repository folder, copy `.env.example` to `.env`. Git ignores `.env`; never commit it or send
   the key by email or chat.
2. Fill in three lines. For Google Gemini:
   ```
   LLM_PROVIDER=gemini
   LLM_MODEL=<the fixed Gemini Flash version you choose>
   GEMINI_API_KEY=<the key>
   ```
   For Anthropic: `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=<the key>`, and `LLM_MODEL` set to the
   Claude model (add `LLM_EFFORT=low` for Haiku; see [MODEL_RECOMMENDATION.md](MODEL_RECOMMENDATION.md)).
3. **Always set `LLM_MODEL` to a fixed version**, not an alias such as `gemini-flash-latest`, which the
   provider can switch to a newer model without notice. The student team's recommendation and test
   results are in [MODEL_RECOMMENDATION.md](MODEL_RECOMMENDATION.md).
4. Leave the other settings empty unless a scan fails with a message that names one (step 7).
5. Restart the app after any change to `.env`.

The `openrouter` provider is for development only and must not be used with OSP contracts: it forwards
text to third-party hosts.

## 4. Start the app and check that the AI is ready
```
python main.py
```
- The terminal should **not** show the warning "AI review is not set up".
- Open http://127.0.0.1:8080. There should be no yellow banner.
- `http://127.0.0.1:8080/api/config` should show `"ai_ready": true` with your provider and model.

## 5. Check the model before real contracts are used
Use only the sample contracts for these checks. Run them from the repository folder with the virtual
environment active. Each sends the sample contracts to the provider; together they take about 30 minutes.

1. **Test scan:** upload a sample contract from `supplementary_files/samples_test_set/` in the workbench,
   for example `0078-23 Adhikari - agreement.docx`. (Some of the PDFs there are scanned images with no
   text, which the app turns down by design.)
   The middle step should read "AI review", the flag cards should include "AI justification", and the
   download button should save an annotated `.docx`.
2. **Accuracy on the labeled contracts** (5 requests). Run it twice, since results vary between runs:
   ```
   python -m evaluation.evaluate --scanner llm --split dev --no-save
   ```
   Compare "caught" and "false alarms" with the table in MODEL_RECOMMENDATION.md. Much lower catches or
   many more false alarms mean the model behaves differently from the one the team tested.
3. **Prompt-injection check** (7 requests):
   ```
   python -m evaluation.injection_check
   ```
   The control case and all six injection cases should pass. The report is saved in
   `evaluation/results/injection_<provider>.md`; record the result in DATA_HANDLING.md.
4. **Final check on contracts kept out of all tuning** (2 requests), once:
   ```
   python -m evaluation.evaluate --scanner llm --split holdout --no-save
   ```
5. Give the results to OSP. OSP and IT approve the setup before real contracts are scanned (the
   checklist at the end of DATA_HANDLING.md).

## 6. Where it runs and who can reach it
- By default the app listens on `127.0.0.1`, so only someone on that computer can use it.
- **The app has no sign-in yet.** Do not set `AICR_HOST=0.0.0.0` (reachable from the network) unless the
  computer is on a network only OSP staff can reach, or the app sits behind Auburn sign-in (for example a
  reverse proxy with single sign-on). Choosing and setting that up is IT's decision.
- `AICR_PORT` changes the port (default 8080).
- Running it as a service that starts with the computer is up to IT; the command is `python main.py` in
  the repository folder, using the virtual environment's Python.

## 7. Running it day to day
- **Errors:** a scan that fails tells the reviewer why. The table "If uploads are turned down or a scan
  fails" in the README lists each message and its fix. The terminal (or service log) has the details;
  it never contains contract text or the API key.
- **Treat the log as OSP-internal:** it records file names of failed uploads, which can identify a
  contract.
- **Scans are kept in memory only,** for 2 hours (`AICR_SCAN_RETENTION_MINUTES`), and are lost on restart.
  Uploaded files are deleted as soon as each scan ends.
- **One contract is scanned at a time;** other uploads wait in a queue.
- **Rotating the key:** create a new key in the provider's console, replace it in `.env`, restart, and
  delete the old key. If a key is ever exposed, delete it at once.

## 8. When something changes
Repeat step 5 (at least the test scan, the `dev` run and the injection check) whenever:
- the model or provider changes, including a provider retiring the model version in `LLM_MODEL`;
- the prompt in `llm_review.py` changes;
- OSP updates the Ts&Cs Matrix (`AICR_TNC_MATRIX`), since the model is given its Common Problems.

Updated matrices go in through `AICR_FAR_MATRIX` and `AICR_TNC_MATRIX` in `.env` (paths relative to the
repository folder). The app checks both when it starts and stops with a clear message if one is missing
or lacks the expected columns.
