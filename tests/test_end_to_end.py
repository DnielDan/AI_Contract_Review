"""End-to-end scan of a sample contract, plus the filename helper ported from the old unit_tests.py."""
import os

from docx import Document

import main

SAMPLE_DOCX = os.path.join(os.path.dirname(__file__), "..", "supplementary_files", "samples_test_set",
                           "382_PAm-WilliamsFundingAgreementDraft.docx")


def test_full_scan_of_docx_produces_annotated_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "scanned.docx"
    flagged_count = main.scan_file(SAMPLE_DOCX, str(output))

    text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
    assert "FAR Acceptance Status Color Code" in text
    assert text.count("Problem Category:") >= flagged_count > 0


def test_scan_with_results_reports_each_step_and_matches_the_annotated_copy(tmp_path, monkeypatch):
    # The TF-IDF matcher is replaced with one fixed flag, so the test only takes the time of the other steps
    flag = ("RESEARCH AGREEMENT 382", {"Problem Category": "Test category"})
    monkeypatch.setattr(main, "flag_problem_language_data", lambda text: ([flag], None))
    stages, output = [], tmp_path / "scanned.docx"
    results = main.scan_contract_with_results(SAMPLE_DOCX, str(output),
                                              lambda stage, ai_notice=None: stages.append(stage))

    assert stages == ["extract", "review", "annotate"]
    (language_flag,) = results["flags"]
    assert results["paragraphs"][language_flag["paragraph"]] == "RESEARCH AGREEMENT 382"
    assert "Problem Category: Test category" in "\n".join(p.text for p in Document(output).paragraphs)


def test_filename_without_extension():
    assert main.getFilenameStringNoExtension("testing.pdf") == "testing"
    assert main.getFilenameStringNoExtension("dots.dots.docx") == "dots.dots"
    assert main.getFilenameStringNoExtension("spaces in name.pdf") == "spaces in name"
    assert main.getFilenameStringNoExtension("no_extension") == "no_extension"
