"""Tests for problem-language flagging against the Ts&Cs Matrix."""
import openpyxl

import main
from flag_problem_language import _flag_problem_language, extract_sheet_data, sk_cosine_sim

BANNER = "[POTENTIAL PROBLEMATIC LANGUAGE DETECTED]"
UNRELATED = "The quick brown fox jumps over the lazy dog."


def _known_problem_sentence():
    workbook = openpyxl.load_workbook(main.TNC_MATRIX_PATH)
    problems = extract_sheet_data(workbook["Intellectual Property"])["Common Problems"]
    return next(str(problem) for problem in problems if "split the costs of patent preparation" in str(problem))


def test_cosine_similarity_scores():
    sentence = "The sponsor shall own all intellectual property."
    assert sk_cosine_sim(sentence, sentence)[0][1] > 0.99
    assert sk_cosine_sim(sentence, UNRELATED)[0][1] < 0.01


def test_matrix_problem_language_is_flagged_and_unrelated_text_is_not(tmp_path, monkeypatch):
    problem = _known_problem_sentence()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "contract_to_txt.txt").write_text(f"{UNRELATED} {problem}", encoding="utf-8")

    _flag_problem_language(main.TNC_MATRIX_PATH)

    lines = (tmp_path / "flagged_contract_to_txt.txt").read_text(encoding="utf-8").split("\n")
    problem_line = next(i for i, line in enumerate(lines) if line.startswith(problem[:40]))
    unrelated_line = lines.index(UNRELATED)
    assert BANNER in lines[problem_line - 1]
    assert unrelated_line == 0 or BANNER not in lines[unrelated_line - 1]
    assert any(line.strip().startswith("Confidence:") for line in lines[problem_line:])
