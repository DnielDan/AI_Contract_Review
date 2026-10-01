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
| `AICR_HOST` | `127.0.0.1` | Address to listen on. Only use `0.0.0.0` once uploads are secured, since it exposes the app to the network. |
| `AICR_PORT` | `8080` | Port to listen on. |
| `AICR_NATIVE` | `0` | Set to `1` to open in a desktop window (requires `pywebview`) instead of the browser. |

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
See `evaluation/README.md` for how the labels were made, their limits, and the current baseline.

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
- **AI Contract Scanner:** converts an uploaded `.docx`, `.doc`, or `.pdf` to text, compares each sentence with the "Common Problems" entries in the Contract Ts&Cs Matrix using TF-IDF cosine similarity, and marks matches in the output with the matrix's category, Auburn's preferred language, "Why" explanation, suggested first response to the sponsor, and a similarity score. It also highlights FAR clause numbers found in the FAR Matrix by acceptance status (green OK, turquoise conditional, red remove).
- **Subcontractor Agreement Scanner:** searches an uploaded PDF for three audit-finding phrases (for example, "Material weaknesses identified? Yes") and reports flagged or not flagged.
- The app does not currently use a large language model; all analysis is local pattern and similarity matching.

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
