"""Scanners that the evaluation can score.

A scanner takes a contract's text and returns the passages it flags as problem language.
Passages may be whole sentences (as the TF-IDF matcher returns) or quoted excerpts (as an
LLM might return); evaluate.py matches either against the labeled sentences. To add a
scanner (for example an LLM judge from US-11a or US-11b), write a function with this
signature and register it in SCANNERS.
"""
import os

import main  # noqa: F401  (sets up the bundled NLTK data path and the matrix paths)
from flag_problem_language import flag_sentences, load_tnc_matrix

_tnc_matrix = None


def baseline_tfidf(contract_text):
    """The inherited Spring 2024 matcher: TF-IDF cosine similarity > 0.20 against the Ts&Cs Matrix."""
    global _tnc_matrix
    if _tnc_matrix is None:
        _tnc_matrix = load_tnc_matrix(main.TNC_MATRIX_PATH)
    return list(flag_sentences(_tnc_matrix, contract_text))


SCANNERS = {
    "baseline": baseline_tfidf,
}
