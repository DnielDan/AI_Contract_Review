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
Requires **Python 3.11** (developed and tested on 3.11.9). From the repository folder:

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

The reference matrices and the NLTK data the app needs are included in `supplementary_files/`, so no extra downloads are required.

## Running the app
```
python main.py
```

This serves the landing page, the AI Contract Scanner (`/contractscanner`), and the Subcontractor
Agreement Scanner (`/subscanner`) at http://127.0.0.1:8080. Launch options are set with environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `AICR_HOST` | `127.0.0.1` | Address to listen on. `0.0.0.0` lets anyone on the network use the app; the app has no login yet (planned in US-8), so keep the default outside a controlled pilot. |
| `AICR_PORT` | `8080` | Port to listen on. |
| `AICR_NATIVE` | `0` | Set to `1` to open in a desktop window (requires `pywebview`) instead of the browser. |

## Settings and AI review
Settings can also go in a `.env` file in the repository folder: copy `.env.example` to `.env` and fill in what you need. `.env` is ignored by git, so API keys never reach the repository.

**AI review (US-12).** Set `LLM_PROVIDER` to have an LLM review the contract's language instead of the basic matcher, then fill in that provider's key:

| `LLM_PROVIDER` | Key to fill in | Notes |
|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | What the team uses for now. Sample contracts only: OpenRouter forwards text to third-party providers. |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude. |
| `gemini` | `GEMINI_API_KEY` | Google Gemini. |

`LLM_MODEL` picks a model other than the provider's default. For each flagged passage the output shows the matrix's own guidance (category, "Why", Auburn's preferred language, first response to the sponsor) plus the AI's explanation and suggested change, labeled as such. FAR clauses are still highlighted by the exact lookup. If the AI call fails (missing key, rate limit, outage), the scan uses the basic matcher and the app says so. With `LLM_PROVIDER` empty, nothing is sent anywhere.

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
6. **Check that it works:** run `python main.py`, open the AI Contract Scanner, and upload a sample contract. If the AI ran, there is no "AI review unavailable" warning and the flagged passages in the output include "AI justification" and "AI suggested change". The AI review takes longer than the basic matcher (up to a few minutes per contract on a free model).
7. **Optional: measure its accuracy** on the labeled test set without overwriting the recorded results: `python -m evaluation.evaluate --scanner llm --split dev --no-save` (one request per contract).

To switch providers later, change `LLM_PROVIDER` and fill in that provider's key; no code changes are needed. To turn the AI off, leave `LLM_PROVIDER` empty.

**If you see "AI review unavailable, so the basic matcher was used":**

| The warning goes on to say | Cause | Fix |
|---|---|---|
| `..._API_KEY is not set in .env` | The key line for the chosen provider is empty, or `.env` was not saved | Paste the key on that line and save `.env` |
| `Unknown LLM_PROVIDER` | `LLM_PROVIDER` is misspelled | Use `openrouter`, `anthropic`, or `gemini` |
| `did not return a usable result` | The key is wrong, the model no longer exists, the provider is rate-limiting you, or the service is down | Check the log in the terminal for the exact error; check the key, try another `LLM_MODEL`, or try again later |

**Keeping keys and contracts safe**
- Never commit `.env` (git ignores it) and never paste a key into chat, issues, or code.
- If a key is exposed, delete it on the provider's site and create a new one.
- Use only the sample contracts until OSP and Auburn IT approve a provider for real contracts: a hosted provider receives the contract text.

**Matrices and matcher (US-7).** `AICR_FAR_MATRIX` and `AICR_TNC_MATRIX` point to updated matrix files (paths relative to the repository folder; default: the bundled files), and `AICR_SIMILARITY_THRESHOLD` sets the basic matcher's threshold (default `0.20`). The app checks both matrices when it starts and stops with a clear message if one is missing or lacks the expected columns.

## Running the tests
```
python -m pytest
```

The tests cover text extraction, matrix parsing, problem-language flagging, FAR clause highlighting, and a full scan of a sample contract. GitHub Actions runs them on Linux for every pull request and every push to `main` (`.github/workflows/tests.yml`); they run offline and never send contract text to an external service.

## Measuring accuracy
`evaluation/` holds a labeled test set built from OSP's own markup of the sample contracts, and a script that scores a scanner against it:
```
python -m evaluation.evaluate --scanner baseline --split dev
```
Use `--scanner llm` to score the AI review with the provider set in `.env` (each run calls the provider and may be billed). See `evaluation/README.md` for how the labels were made, their limits, and the current baseline.

## Sample files
Sample documents for trying each scanner are in `supplementary_files/samples_test_set/`:

| Scanner | Try | Expected result |
|---|---|---|
| AI Contract Scanner (`.docx`) | `0078-23 Adhikari - agreement.docx` | An annotated `<name>_scanned.docx` with flagged language and highlighted FAR clauses |
| AI Contract Scanner (`.pdf`) | `0430-23 O'Brien - fully executed.pdf` | Same as above, from a PDF |
| AI Contract Scanner (legacy `.doc`) | `Godwin - redline 12.5.23.doc` | Same as above, from a Word 97-2003 file |
| Subcontractor Agreement Scanner | `24-00373 Subcontract Auburn University_FE (1).pdf` | "not flagged". This file is a subcontract, not an audit report, so it contains none of the audit-finding phrases the scanner looks for; a sample audit report is still needed to test the flagged case. |

`0264-23 Godwin - fully executed.pdf` is a scanned image with no text layer, so it produces an output with nothing flagged.

## What the app currently does
- **AI Contract Scanner:** converts an uploaded `.docx`, `.doc`, or `.pdf` to text. With an LLM set in `.env`, the LLM reviews the text against the Ts&Cs Matrix (see "Settings and AI review"); otherwise it compares each sentence with the "Common Problems" entries in the Contract Ts&Cs Matrix using TF-IDF cosine similarity, and marks matches in the output with the matrix's category, Auburn's preferred language, "Why" explanation, suggested first response to the sponsor, and a similarity score. It also highlights FAR clause numbers found in the FAR Matrix by acceptance status (green OK, turquoise conditional, red remove).
- **Subcontractor Agreement Scanner:** searches an uploaded PDF for three audit-finding phrases (for example, "Material weaknesses identified? Yes") and reports flagged or not flagged.
- Without `LLM_PROVIDER` set, all analysis is local pattern and similarity matching and no contract text leaves the machine.

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
| User interface | Implemented: a landing page with two scanners |
