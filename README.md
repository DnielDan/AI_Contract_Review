# AI Based Contract Review

> **Continuation notice (Fall 2026):** this repository is the Fall 2026 team's working copy of the
> project, continuing the Python/NiceGUI codebase originated by the Spring 2024 teams below.
> History was carried over from the original repository,
> [Ktmking111/AI_Contract_Review_Spring2024](https://github.com/Ktmking111/AI_Contract_Review_Spring2024),
> which itself originated from
> [J-Hill22/AI-Based-Contract-Review](https://github.com/J-Hill22/AI-Based-Contract-Review/tree/Cycle3).
> A separate Fall 2025 team also worked on this project via a full rewrite (Next.js/Supabase/LLM);
> that code is not part of this repository. See the team's Cycle 0 report for current status,
> known limitations, and the active backlog.

## Setup
Requires **Python 3.11** (developed and tested on 3.11.9) and **Node.js 22** (to build the workbench). From the repository folder:

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

The reference matrices and the NLTK data the app needs are included in `supplementary_files/`, so no extra downloads are required.

## Running the app
Build the workbench (the browser interface, in `frontend/`) once, and again after changing anything in `frontend/`. Then start the server:
```
cd frontend
npm ci
npm run build
cd ..
python main.py
```

This serves the workbench at http://127.0.0.1:8080. Scanning needs an AI provider set up in `.env` (see "Settings and AI review"); until then the workbench shows a yellow "AI review is not set up" banner and turns down uploads. Drop a contract on the left to scan it; the progress card shows each step. When the scan finishes, the contract is shown with its flagged passages and FAR clauses highlighted, each flag has a card on the right with the matrix guidance, and the download button saves the annotated `<name>_scanned.docx`. An uploaded file is deleted from the server as soon as its scan ends. A finished scan's results and annotated copy are kept in memory only, for 2 hours (`AICR_SCAN_RETENTION_MINUTES`) and at most 50 finished scans; the × next to a scan in the list removes it sooner, and a server restart forgets them all. Download the annotated copy before then: once a scan has been forgotten, the download button says so and the contract has to be scanned again. The subcontractor audit check has no screen yet; it is available to programs as `POST /api/subcontract-scans`.

Launch options are set with environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `AICR_HOST` | `127.0.0.1` | Address to listen on. `0.0.0.0` lets anyone on the network use the app; the app has no login yet (planned in US-8), so keep the default outside a controlled pilot. |
| `AICR_PORT` | `8080` | Port to listen on. |
| `AICR_SCAN_RETENTION_MINUTES` | `120` | How long a finished scan's results and annotated copy stay available in memory. Also settable in `.env`. |

**Working on the workbench:** with `python main.py` running on port 8080, run `npm run dev` in `frontend/`. Vite serves the workbench on its own port, reloads it on every change, and passes `/api` calls to the Python server.

## Settings and AI review
Settings can also go in a `.env` file in the repository folder: copy `.env.example` to `.env` and fill in what you need. `.env` is ignored by git, so API keys never reach the repository.

**AI review (US-12).** The app reviews contract language only with an AI provider: OSP will use the tool once Auburn's agreement with an AI provider is signed, so there is no non-AI mode. Set `LLM_PROVIDER` and fill in that provider's key:

| `LLM_PROVIDER` | Key to fill in | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | Claude. |
| `gemini` | `GEMINI_API_KEY` | Google Gemini. |
| `openrouter` | `OPENROUTER_API_KEY` | Development on sample contracts only: OpenRouter forwards text to third-party providers. |

`LLM_MODEL` picks a model other than the provider's default. For each flagged passage the output shows the matrix's own guidance (category, "Why", Auburn's preferred language, first response to the sponsor) plus the AI's explanation and suggested change, labeled as such. FAR clauses are still highlighted by the exact lookup in the FAR Matrix. If the AI call fails (rate limit, outage, unreadable reply), the scan fails and says why; it does not fall back to the old TF-IDF matcher, which is kept only as the accuracy baseline in `evaluation/`. With `LLM_PROVIDER` empty, nothing is sent anywhere and no contract can be scanned.

For how the AI review works and how to change or evaluate it, see [docs/AI_REVIEW.md](docs/AI_REVIEW.md).

### Adding an API key (step by step)
You only need a key for the one provider you want to use.

1. **Install the requirements** (once, with the virtual environment active): `pip install -r requirements.txt`.
2. **Get a key** from the provider:
   - OpenRouter: sign in at [openrouter.ai](https://openrouter.ai), open **Keys**, and create a key (starts with `sk-or-`).
   - Claude: sign in at [console.anthropic.com](https://console.anthropic.com), open **API Keys**, and create a key (starts with `sk-ant-`). Billing must be set up on the account.
   - Gemini: sign in at [Google AI Studio](https://aistudio.google.com) and choose **Get API key**.
3. **Create your `.env` file** in the repository folder from the template:
   ```
   copy .env.example .env          # Windows
   cp .env.example .env            # macOS / Linux
   ```
4. **Fill in two lines** in `.env` and save it. For example, for OpenRouter:
   ```
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-v1-...
   ```
   Paste the key right after the `=`, with no quotes or spaces, on the line for your provider (`ANTHROPIC_API_KEY` for `anthropic`, `GEMINI_API_KEY` for `gemini`). Leave the other key lines empty.
5. **Optional: choose a model** with `LLM_MODEL=`. Leave it empty to use the provider's default. Free OpenRouter models come and go, so if the default stops working, pick another model from OpenRouter's model list (free ones end in `:free`).
6. **Check that it works:** run `python main.py`, open http://127.0.0.1:8080, and upload a sample contract. If the AI is set up, there is no yellow "not set up" banner, the scan's middle step is "AI review", and the flag cards include "AI justification" and "AI suggested change". The AI review can take a few minutes per contract on a free model.
7. **Optional: measure its accuracy** on the labeled test set without overwriting the recorded results: `python -m evaluation.evaluate --scanner llm --split dev --no-save` (one request per contract).

To switch providers later, change `LLM_PROVIDER` and fill in that provider's key; no code changes are needed. Restart the server after changing `.env`.

**If uploads are turned down or a scan fails:**

| The message says | Cause | Fix |
|---|---|---|
| `AI review is not set up ... LLM_PROVIDER is not set` | No provider in `.env` | Set `LLM_PROVIDER` and that provider's key, then restart |
| `AI review is not set up ... _API_KEY is not set in .env` | The key line for the chosen provider is empty, or `.env` was not saved | Paste the key on that line, save `.env`, and restart |
| `AI review is not set up ... Unknown LLM_PROVIDER` | `LLM_PROVIDER` is misspelled | Use `anthropic`, `gemini`, or `openrouter` |
| `Could not review ... did not return a usable result` | The key is wrong, the model no longer exists, the provider is rate-limiting you, or the service is down | Check the log in the terminal for the exact error; check the key, try another `LLM_MODEL`, or try again later |
| `Could not review ... did not answer in time` | The provider took longer than `LLM_TIMEOUT_SECONDS` (default 300) | Try again later, or raise `LLM_TIMEOUT_SECONDS` |
| `Could not review ... was cut off before it finished` | The reply reached its output limit | Raise `LLM_MAX_TOKENS`, or set `LLM_EFFORT=low` so the model spends less of the limit thinking |
| `Could not process ... No text could be read from this PDF` | The PDF is a scanned image with no text layer | Run it through OCR (text recognition), or upload the Word version |
| `AI review is not set up ... LLM_TIMEOUT_SECONDS / LLM_MAX_TOKENS / LLM_EFFORT must be ...` | One of the optional limits has an invalid value | Fix or empty that line in `.env`, then restart |

Only one contract is scanned at a time, so several uploads do not hit the provider's rate limits together; the others wait as "Queued" and can be cancelled while they wait.

**Keeping keys and contracts safe**
- Never commit `.env` (git ignores it) and never paste a key into chat, issues, or code.
- If a key is exposed, delete it on the provider's site and create a new one.
- Use only the sample contracts until OSP and Auburn IT approve a provider for real contracts: a hosted provider receives the contract text.

**Matrices (US-7).** `AICR_FAR_MATRIX` and `AICR_TNC_MATRIX` point to updated matrix files (paths relative to the repository folder; default: the bundled files). The AI review is given the Ts&Cs Matrix's Common Problems, and each flag's guidance is looked up from it. The app checks both matrices when it starts and stops with a clear message if one is missing or lacks the expected columns.

## Running the tests
```
python -m pytest
```

The tests cover text extraction, matrix parsing, the AI review's handling of replies and failures, FAR clause highlighting, the workbench API, and a full scan of a sample contract. Scans in the tests use a stand-in for the AI review (`tests/fakes.py`), and any call to a real provider fails the test, so they run offline and never send contract text to an external service, even when your `.env` holds a key. GitHub Actions builds the workbench and runs them on Linux for every pull request and every push to `main` (`.github/workflows/tests.yml`).

A browser test of the workbench (`tests/test_e2e_workbench.py`) is left out of the default run. It starts the app with the stand-in AI review (`tests/e2e_server.py`) and needs Playwright with Chromium (`pip install playwright` and `playwright install chromium`) and the built workbench:
```
python -m pytest -m e2e tests/test_e2e_workbench.py
```
If Playwright is installed in a different Python environment, run the test with that interpreter and set `AICR_E2E_PYTHON` to this project's `.venv` Python, which runs the server.

## Measuring accuracy
`evaluation/` holds a labeled test set built from OSP's own markup of the sample contracts, and a script that scores a scanner against it:
```
python -m evaluation.evaluate --scanner baseline --split dev
```
`baseline` is the inherited TF-IDF matcher (`evaluation/tfidf_matcher.py`), which the app no longer uses and which is kept unchanged so the AI review can be compared with it. Use `--scanner llm` to score the AI review with the provider set in `.env` (each run calls the provider and may be billed). See `evaluation/README.md` for how the labels were made, their limits, and the current baseline.

## Sample files
Sample documents for trying each scanner are in `supplementary_files/samples_test_set/`:

| Scanner | Try | Expected result |
|---|---|---|
| AI Contract Scanner (`.docx`) | `0078-23 Adhikari - agreement.docx` | An annotated `<name>_scanned.docx` with flagged language and highlighted FAR clauses |
| AI Contract Scanner (`.pdf`) | `0430-23 O'Brien - fully executed.pdf` | Same as above, from a PDF |
| AI Contract Scanner (legacy `.doc`) | `Godwin - redline 12.5.23.doc` | Same as above, from a Word 97-2003 file |
| Subcontractor audit check (`POST /api/subcontract-scans`) | `24-00373 Subcontract Auburn University_FE (1).pdf` | "not flagged". This file is a subcontract, not an audit report, so it contains none of the audit-finding phrases the scanner looks for; a sample audit report is still needed to test the flagged case. |

`0264-23 Godwin - fully executed.pdf` is a scanned image with no text layer. Both scanners report it as unreadable ("No text could be read from this PDF; it is probably a scanned image…") instead of as a contract with no problems, and nothing is sent to the AI. Run such a file through OCR (text recognition) first, or upload the Word version.

## What the app currently does
- **AI Contract Scanner:** converts an uploaded `.docx`, `.doc`, or `.pdf` to text, and the AI provider set in `.env` reviews it against the "Common Problems" in the Contract Ts&Cs Matrix (see "Settings and AI review"). Each flagged passage is marked in the output with the matrix's category, Auburn's preferred language, "Why" explanation, and suggested first response to the sponsor, plus the AI's own explanation, suggested change, and confidence. It also highlights FAR clause numbers found in the FAR Matrix by acceptance status (green OK, turquoise conditional, red remove). In the output, the contract keeps its paragraphs: a paragraph with flagged language is highlighted yellow, everything the tool adds (Ts&Cs guidance, FAR Matrix notes on each FAR clause, AI text) is highlighted gray, text written by the AI is also italic blue, and a line at the top names the AI provider and model. The workbench shows the same flags on the contract in the browser, with a card for each.
- **Subcontractor Agreement Scanner:** searches an uploaded PDF for three audit-finding phrases (for example, "Material weaknesses identified? Yes") and reports flagged or not flagged. It has no screen in the workbench yet (API only).
- Without `LLM_PROVIDER` set, no contract text leaves the machine and contract scans are turned down. The subcontractor check never uses the AI.

## Project history
The sections below are from the Spring 2024 teams and describe the project's original goals.

### Overview 
This is our Senior Design Project for Auburn University in Spring of 2024. We are tasked with working with Auburn's Office of Sponsored Programs (OSP) to develop a program that could take in a contract and automatically highlight all instances of problematic language/clauses that are contained within the contract. This program will allow the OSP's contract negotiators to be more efficient in how many contracts they are able to process and ultimately allow Auburn University to fulfill its mission of doubling research expenditures set by President Roberts. This tool is meant to be a home-grown and cost-effective tool that competes with commercial applications such as LegalSifter, Lexion.ai, Cobblestone, etc. This project consists of two teams, an orange team which is focusing on the core functionality of the document processing and flagging, and a blue team, which is focusing on the user interface and improving ease of use for the clients. This code originated from [Jarret's Best Effort: AI Based Contract Review](https://github.com/J-Hill22/AI-Based-Contract-Review/tree/Cycle3), the prior semesters progress towards fulfilling the client's requests.

### Project Introduction
The Office of Sponsored Programs (OSP) is responsible for the administration of research contracts and grants received by the university. OSP has a team of contract administrators who work with sponsors to negotiate and finalize research contracts. The contract negotiation process is time-consuming and requires careful review of legal and technical terms. Currently, the contract review process is manual and can be subject to numerous errors and inefficiencies.

The number of contracts requiring review and their complexity has grown significantly over the past few years with Auburn’s upward trajectory in research funding. However, the number of staff in OSP has remained stagnant. OSP’s review workload is expected to continue to increase with President Robert’s mission to double research expenditures. Pursuant to item number six of the AU Strategic Plan, Operational Excellence, OSP is interested in developing an AI tool to assist with contract review and negotiation in order to enhance the contract review process. There are multiple commercial options available (LegalSifter, Cobblestone, lexion.ai) but they are not cost-efficient. OSP believes a homegrown tool can be developed that would better address the University’s needs.

The objective of this project is to develop an AI tool that can assist OSP contract negotiators in reviewing and negotiating research contracts. The AI tool will be designed to identify and flag legal and technical issues in the contracts, suggest potential revisions and provide guidance on negotiating terms.

### Status of the Spring 2024 goals
The Spring 2024 teams planned the features below. This table records what was actually built, so that the goals are not mistaken for existing functionality.

| Spring 2024 goal | Status |
|---|---|
| Contract scanning against the FAR and Ts&Cs matrices | Implemented (see "What the app currently does") |
| Alternative language | Partial: the output shows the matrix's pre-written preferred language for each matched category; nothing is generated for the specific contract |
| Adjustment justification | Partial: the output shows the matrix's "Why" text for each matched category |
| Adaptive negotiating (learning from past negotiations) | Not implemented |
| Automated risk assessment | Not implemented |
| User interface | Implemented: a browser workbench for contract scans (FastAPI server, React frontend); the subcontractor check has no screen yet |
