"""Regression tests for US-14 (a, b): PDF and legacy .doc text extraction, and documents with no
readable text (a scanned PDF) reported as unreadable rather than as clean."""
import os
import shutil

import pytest
from docx import Document
from pypdf import PdfReader, PdfWriter

import pdf_to_txt
from contract_to_txt import (NO_DOCUMENT_TEXT, NO_PDF_TEXT, UnsupportedFileError, convert_to_txt, extract_doc_text,
                             extract_pdf_text, require_text)

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "supplementary_files", "samples_test_set")
MULTI_PAGE_PDF = os.path.join(SAMPLES, "0430-23 O'Brien - fully executed.pdf")
SUBCONTRACT_PDF = os.path.join(SAMPLES, "24-00373 Subcontract Auburn University_FE (1).pdf")
LEGACY_DOC = os.path.join(SAMPLES, "Godwin - redline 12.5.23.doc")
SCANNED_PDF = os.path.join(SAMPLES, "0264-23 Godwin - fully executed.pdf")  # page images, no text layer


def test_pdf_extraction_includes_last_page():
    # The old loop used range(page_count - 1) and silently dropped the last page
    last_page_text = PdfReader(MULTI_PAGE_PDF).pages[-1].extract_text().strip()
    assert last_page_text
    assert last_page_text[:60] in extract_pdf_text(MULTI_PAGE_PDF)


def test_one_page_pdf_produces_text(tmp_path):
    # With the old loop, a one-page PDF produced no text at all
    writer = PdfWriter()
    writer.add_page(PdfReader(MULTI_PAGE_PDF).pages[0])
    one_page_pdf = tmp_path / "one_page.pdf"
    with open(one_page_pdf, "wb") as file:
        writer.write(file)
    assert extract_pdf_text(str(one_page_pdf)).strip()


def test_pdf_control_characters_are_removed():
    # These PDFs contain control characters (O'Brien on its last page, Lawson on page 2)
    # that made the Word output step crash
    for name in ["0430-23 O'Brien - fully executed.pdf", "1611-23 Lawson - fully executed.pdf"]:
        text = extract_pdf_text(os.path.join(SAMPLES, name))
        assert not any(ord(char) < 32 and char not in "\n\t" for char in text)


def test_full_scan_of_pdf_with_control_characters(tmp_path, monkeypatch, fake_ai):
    import main
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "scanned.docx"
    main.scan_contract_with_results(MULTI_PAGE_PDF, str(output))
    assert output.stat().st_size > 0


def test_pdf_file_is_closed_after_extraction(tmp_path):
    # An open handle would keep Windows from deleting the upload afterward
    copy = tmp_path / "upload.pdf"
    shutil.copy(MULTI_PAGE_PDF, copy)
    extract_pdf_text(str(copy))
    os.remove(copy)
    assert not copy.exists()


def test_subcontractor_scan_leaves_no_txt_copy(tmp_path):
    upload = tmp_path / "subcontract.pdf"
    shutil.copy(SUBCONTRACT_PDF, upload)
    assert pdf_to_txt.scan_for_findings(str(upload)) is False
    assert list(tmp_path.glob("*.txt")) == []


def test_doc_extraction_reads_body_text():
    text = extract_doc_text(LEGACY_DOC)
    assert "“OCURRENCE OF WESTERN CHICKEN TURTLE”" in text
    assert "Auburn University" in text
    assert "�" not in text
    assert not any(ord(char) < 32 and char not in "\n\t" for char in text)


def test_convert_to_txt_accepts_doc_with_any_extension_case(tmp_path, monkeypatch):
    upload = tmp_path / "CONTRACT.DOC"
    shutil.copy(LEGACY_DOC, upload)
    monkeypatch.chdir(tmp_path)
    assert convert_to_txt(str(upload)) is None
    with open(tmp_path / "contract_to_txt.txt", encoding="utf-8") as file:
        assert "WESTERN CHICKEN TURTLE" in file.read()


def test_scanned_pdf_is_reported_as_unreadable_and_nothing_is_written(tmp_path):
    output = tmp_path / "contract.txt"
    with pytest.raises(UnsupportedFileError, match="scanned image") as raised:
        convert_to_txt(SCANNED_PDF, str(output))
    assert str(raised.value) == NO_PDF_TEXT
    assert not output.exists()


def test_word_document_without_text_is_reported(tmp_path):
    empty = tmp_path / "empty.docx"
    document = Document()
    document.add_paragraph("   ")
    document.add_paragraph("12")
    document.save(empty)
    with pytest.raises(UnsupportedFileError, match=NO_DOCUMENT_TEXT):
        convert_to_txt(str(empty), str(tmp_path / "contract.txt"))


def test_every_sample_contract_with_text_passes_the_check(tmp_path):
    samples = [name for name in os.listdir(SAMPLES) if os.path.splitext(name)[1].lower() in (".pdf", ".docx", ".doc")]
    for name in samples:
        if os.path.join(SAMPLES, name) == SCANNED_PDF:
            continue
        convert_to_txt(os.path.join(SAMPLES, name), str(tmp_path / "contract.txt"))  # raises if it found no text


def test_text_check_needs_real_words_not_page_numbers():
    with pytest.raises(UnsupportedFileError):
        require_text("1\n2\n3\n- 4 -\nPage 5 of 7", ".pdf")
    assert require_text("The Sponsor shall own all intellectual property. " * 3, ".pdf")


def test_subcontractor_check_of_a_scanned_pdf_is_an_error_not_unflagged(tmp_path):
    upload = tmp_path / "audit.pdf"
    shutil.copy(SCANNED_PDF, upload)
    with pytest.raises(UnsupportedFileError, match="scanned image"):
        pdf_to_txt.scan_for_findings(str(upload))
    assert list(tmp_path.glob("*.txt")) == []
