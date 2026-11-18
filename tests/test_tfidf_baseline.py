"""The inherited TF-IDF matcher, kept in evaluation/ only as the accuracy baseline for the AI review."""
import openpyxl

import main  # noqa: F401  (sets up the bundled NLTK data path)
from evaluation.tfidf_matcher import flag_sentences, sk_cosine_sim
from flag_problem_language import extract_sheet_data, load_tnc_matrix

UNRELATED = "The quick brown fox jumps over the lazy dog."


def _known_problem_sentence():
    workbook = openpyxl.load_workbook(main.TNC_MATRIX_PATH)
    problems = extract_sheet_data(workbook["Intellectual Property"])["Common Problems"]
    return next(str(problem) for problem in problems if "split the costs of patent preparation" in str(problem))


def test_cosine_similarity_scores():
    sentence = "The sponsor shall own all intellectual property."
    assert sk_cosine_sim(sentence, sentence)[0][1] > 0.99
    assert sk_cosine_sim(sentence, UNRELATED)[0][1] < 0.01


def test_matrix_problem_language_is_flagged_and_unrelated_text_is_not():
    problem = _known_problem_sentence()
    flagged = flag_sentences(load_tnc_matrix(main.TNC_MATRIX_PATH), f"{UNRELATED}\n{problem}")
    assert problem in flagged and UNRELATED not in flagged
    assert flagged[problem]["Problem Category"] and flagged[problem]["Confidence"] > 0.2
