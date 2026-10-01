# Accuracy evaluation (US-9a)

This folder measures how accurately a scanner flags problem language, so that the inherited
matcher, the matcher fixes (US-14 c), and the LLM prototypes (US-11a, US-11b) can be compared
on the same contracts with the same scoring.

## Where the labels come from
Several sample contracts contain OSP reviewers' own markup: sponsor language struck through or
deleted with tracked changes, Auburn's replacement language in red or as tracked insertions, and
comments explaining the objection. `build_test_set.py` turns that markup into labels:

1. It rebuilds each contract's **original sponsor text**: struck and deleted text is kept, and
   Auburn's red or inserted text is removed. For the two contracts whose unedited originals are
   also in the sample set, the rebuilt text matches the original word for word (MOU: 4,456/4,456
   words) or nearly so (CMI2: 99.8%, where the only differences are form blanks OSP filled in).
2. It splits the text into sentences with the same tokenizer the scanner uses.
3. A sentence is labeled **problem** if OSP struck, deleted, commented on, or inserted language
   into it, and **ok** otherwise. The OSP comment, if any, is kept in `osp_note`.

`issue_type` records which Ts&Cs Matrix sheet covers each problem (`matrix: <sheet>`), or `other`
for administrative corrections the matrix does not address, such as a wrong ID number or funding
amount. Issue types were drafted by the team and are pending review.

## Limits to keep in mind
- **"ok" means OSP left a sentence unchanged, not that OSP confirmed it.** Some unmarked sentences
  may be issues OSP chose not to raise, so false-alarm counts, and therefore precision, are
  conservative.
- Labels are per sentence. A clause usually spans several sentences, so clause recall (a clause
  counts as caught if any of its sentences is flagged) is closer to what a reviewer experiences.
- Identical sentences can have different labels in different places (for example, "The terms of
  this provision will survive termination of this Agreement." inside a struck clause and inside an
  accepted one), so no text-only scanner can score perfectly on them.
- The Ts&Cs Matrix has no separate indemnification sheet; indemnity problems are covered by its
  "Limitation of Liability" sheet, partly as a keyword list.

## Splits
| Split | Contracts | Use |
|---|---|---|
| `dev` | Adhikari, Lawson, Williams funding agreement, CMI2, Proposed Contract Revisions | Development and tuning |
| `holdout` | Hale, MOU | **Reserved for the Cycle 3 validation pass.** Score against it only to record results, never to tune. |

## Reviewing labels
Open `labels.csv` in Excel. For each problem row, check the sentence and `issue_type`, correct
anything wrong, and put your initials in `reviewed`. At minimum, review every problem row and a
sample of ok rows. Do not rerun `build_test_set.py --force` after review: it regenerates the file
and would discard the review.

## Running an evaluation
From the repository root:
```
python -m evaluation.evaluate --scanner baseline --split dev
```
The report is printed and saved to `results/<scanner>_<split>.md`, with every sentence's label and
prediction in `results/<scanner>_<split>_predictions.csv` for error analysis.

## Adding a scanner
Write a function that takes a contract's text and returns the passages it flags (whole sentences
or quoted excerpts), and register it in `SCANNERS` in `scanners.py`. Quoted excerpts are credited
to the sentences they contain or sit inside; very short excerpts are only credited on an exact match.

## Baseline (inherited TF-IDF matcher, before the US-14 c fixes)
| Split | Problems | Caught | Missed | False alarms | Precision | Recall | Clause recall |
|---|---|---|---|---|---|---|---|
| dev | 61 | 18 | 43 | 62 | 22% | 30% | 11/22 |
| holdout | 10 | 3 | 7 | 29 | 9% | 30% | 2/5 |

The matcher misses about 70% of the problem sentences OSP marked, and roughly four in five of its
flags are on sentences OSP left unchanged. Full reports are in `results/`.
