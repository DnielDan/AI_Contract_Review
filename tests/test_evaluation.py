"""Tests for the US-9a labeled test set and the scoring in evaluation/evaluate.py."""
import csv
import os
from collections import Counter

from nltk import data as nltk_data

import main  # noqa: F401  (adds the bundled NLTK data path)
from evaluation.build_test_set import DOCUMENTS
from evaluation.evaluate import DATA_DIR, LABELS_PATH, load_labels, match_flags, normalize, score


def _labels():
    with open(LABELS_PATH, encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_labels_line_up_with_the_reconstructed_text():
    # Each document's labeled sentences must be exactly how the scanners' tokenizer splits its text
    tokenizer = nltk_data.load("tokenizers/punkt/english.pickle")
    rows = _labels()
    for doc_id in DOCUMENTS:
        with open(os.path.join(DATA_DIR, f"{doc_id}.txt"), encoding="utf-8") as file:
            sentences = [normalize(s) for s in tokenizer.tokenize(file.read())]
        labeled = [normalize(r["sentence"]) for r in rows if r["doc_id"] == doc_id]
        assert labeled == sentences, doc_id


def test_every_problem_has_an_issue_type_and_holdout_is_separate():
    rows = _labels()
    problems = [r for r in rows if r["label"] == "problem"]
    assert len(problems) >= 60
    assert all(r["issue_type"] == "other" or r["issue_type"].startswith("matrix: ") for r in problems)
    assert {r["doc_id"] for r in rows if r["split"] == "holdout"} == {"hale", "mou"}
    assert Counter(r["label"] for r in rows)["ok"] > 10 * len(problems)


def test_match_flags_credits_sentences_and_excerpts_but_not_stray_words():
    sentences = ["Arbitration.", "All disputes shall be decided through binding arbitration.", "Payment is due in 30 days."]
    assert match_flags(sentences, ["All disputes shall be decided through binding arbitration."]) == {1}
    assert match_flags(sentences, ["decided through binding arbitration"]) == {1}          # quoted excerpt
    # A passage spanning several sentences credits each full sentence; a short heading inside it
    # is only credited on an exact match
    assert match_flags(sentences, ["Arbitration. All disputes shall be decided through binding arbitration."]) == {1}
    assert match_flags(sentences, ["Arbitration."]) == {0}
    assert match_flags(sentences, ["See the arbitration. clause below for details"]) == set()  # short heading not credited
    assert match_flags(sentences, ["arbitration"]) == set()                                  # too short to credit


def test_score_counts_and_clause_recall():
    def row(index, label, issue_type=""):
        return {"doc_id": "d", "sentence_index": index, "label": label, "issue_type": issue_type}

    rows = [row(0, "problem", "matrix: Insurance"), row(1, "problem", "matrix: Insurance"),
            row(2, "ok"), row(3, "problem", "other"), row(4, "ok")]
    result = score(rows, flagged_positions={1, 4})
    assert (result["caught"], result["missed"], result["false_alarm"], result["correct_ok"]) == (1, 2, 1, 1)
    assert result["precision"] == 0.5
    assert result["matrix_caught"] == 1 and result["matrix_problems"] == 2
    assert (result["clauses_caught"], result["clauses"]) == (1, 2)


def test_load_labels_filters_by_split():
    assert {r["split"] for r in load_labels("dev")} == {"dev"}
    assert len(load_labels("all")) == len(load_labels("dev")) + len(load_labels("holdout"))
