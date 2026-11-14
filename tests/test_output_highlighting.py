"""The scanned document keeps paragraphs, marks flagged language, and shows everything the tool adds."""
from docx import Document
from docx.enum.text import WD_COLOR_INDEX

import main
from contract_to_txt import txt_to_docx
from flag_FAR_clauses import ADDED_TEXT_HIGHLIGHT, AI_TEXT_COLOR, annotate_contract
from flag_problem_language import write_flagged_text

PROBLEM = "The Sponsor shall own all intellectual property arising from the research."
FLAGGED_PARAGRAPH = f"Ownership is described below. {PROBLEM}"
FAR_PARAGRAPH = "The Contractor shall comply with FAR 52.203-16 and again FAR 52.203-16."  # REMOVE
PLAIN = "Payment is due within thirty days."
CONTRACT = "\n".join(["This Agreement begins on January 1.", FLAGGED_PARAGRAPH, FAR_PARAGRAPH, PLAIN])
DETAILS = {
    "Problem Category": "Intellectual Property",
    "Why": "Auburn must own what it creates",
    "AI justification": "The clause gives the sponsor all IP.",
    "AI suggested change": "Each party owns the IP it creates.",
}


def scanned(tmp_path, flags=((PROBLEM, DETAILS),), review_label=None):
    flagged_txt, flagged_docx, output = tmp_path / "flagged.txt", tmp_path / "flagged.docx", tmp_path / "out.docx"
    write_flagged_text(CONTRACT, list(flags), str(flagged_txt))
    txt_to_docx(str(flagged_txt), str(flagged_docx))
    annotate_contract(main.FAR_CLAUSE_MATRIX_PATH, str(flagged_docx), str(output), review_label)
    return Document(output).paragraphs


def run_for(paragraphs, text):
    return next(run for paragraph in paragraphs for run in paragraph.runs if run.text.strip() == text)


def test_paragraphs_stay_whole_and_the_flagged_one_is_yellow(tmp_path):
    paragraphs = scanned(tmp_path)
    texts = [paragraph.text.strip() for paragraph in paragraphs]
    assert FLAGGED_PARAGRAPH in texts  # the two-sentence paragraph is not split into sentences
    assert run_for(paragraphs, FLAGGED_PARAGRAPH).font.highlight_color == WD_COLOR_INDEX.YELLOW
    assert run_for(paragraphs, PLAIN).font.highlight_color is None


def test_everything_the_tool_adds_is_gray(tmp_path):
    paragraphs = scanned(tmp_path)
    for text in (f"Flagged sentence: {PROBLEM}", "Problem Category: Intellectual Property",
                 "Why: Auburn must own what it creates", "[POTENTIAL PROBLEMATIC LANGUAGE DETECTED]",
                 "[END POTENTIAL PROBLEMATIC LANGUAGE]"):
        assert run_for(paragraphs, text).font.highlight_color == ADDED_TEXT_HIGHLIGHT, text
    assert not run_for(paragraphs, "Why: Auburn must own what it creates").italic


def test_ai_lines_are_gray_and_italic_blue(tmp_path):
    paragraphs = scanned(tmp_path)
    for text in ("AI justification: The clause gives the sponsor all IP.",
                 "AI suggested change: Each party owns the IP it creates."):
        run = run_for(paragraphs, text)
        assert run.font.highlight_color == ADDED_TEXT_HIGHLIGHT and run.italic
        assert run.font.color.rgb == AI_TEXT_COLOR


def test_far_clause_gets_one_gray_note_from_the_matrix(tmp_path):
    paragraphs = scanned(tmp_path)
    assert run_for(paragraphs, FAR_PARAGRAPH).font.highlight_color == WD_COLOR_INDEX.RED
    notes = [paragraph for paragraph in paragraphs if paragraph.text.startswith("FAR 52.203-16")]
    assert len(notes) == 1  # noted on first mention only
    assert ": Remove." in notes[0].text
    assert notes[0].runs[0].font.highlight_color == ADDED_TEXT_HIGHLIGHT
    texts = [paragraph.text for paragraph in paragraphs]
    assert texts.index(notes[0].text) == texts.index(FAR_PARAGRAPH) + 1


def test_unplaced_flags_are_listed_at_the_end_in_gray(tmp_path):
    paragraphs = scanned(tmp_path, flags=[("Text that is nowhere in this contract at all.", DETAILS)])
    header = run_for(paragraphs, "ADDITIONAL FLAGGED LANGUAGE (passage not located in the extracted text)")
    assert header.font.highlight_color == ADDED_TEXT_HIGHLIGHT


def test_legend_explains_the_colors(tmp_path):
    paragraphs = scanned(tmp_path)
    assert run_for(paragraphs, "Yellow = Potential problem language (Ts&Cs Matrix)").font.highlight_color \
        == WD_COLOR_INDEX.YELLOW
    gray = "Gray = added by the tool from the FAR and Ts&Cs Matrices (and the AI review); not in the original contract"
    assert run_for(paragraphs, gray).font.highlight_color == ADDED_TEXT_HIGHLIGHT
    assert run_for(paragraphs, "Italic blue = written by the AI review, not taken from the matrix").italic


def test_review_label_is_shown_at_the_top(tmp_path):
    paragraphs = scanned(tmp_path, review_label="AI review (openrouter, some-model)")
    assert paragraphs[0].text == "Problem language reviewed by: AI review (openrouter, some-model)"


def test_review_label_says_which_review_ran(monkeypatch):
    assert main.review_label(None) == "Basic matcher (TF-IDF similarity)"
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    assert main.review_label(None) == "AI review (openrouter, some-model)"
    assert "because the AI review was unavailable" in main.review_label("AI review unavailable ...")


def test_full_scan_without_llm_is_labeled_as_matcher(tmp_path):
    sample = main.os.path.join(main.SUPPLEMENTARY_DIR, "samples_test_set", "382_PAm-WilliamsFundingAgreementDraft.docx")
    output = tmp_path / "scanned.docx"
    main.scan_contract(sample, str(output))
    first = Document(output).paragraphs[0].text
    assert first == "Problem language reviewed by: Basic matcher (TF-IDF similarity)"
