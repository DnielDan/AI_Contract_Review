"""Tests for US-3a: failures are reported to the user, distinct from "no problems found"."""
import logging

import pytest

import main
import pdf_to_txt
from contract_to_txt import UnsupportedFileError, convert_to_txt


def upload(client, name, data, url="/api/scans"):
    return client.post(url, files={"file": (name, data)})


def test_unsupported_file_type_raises_instead_of_reusing_the_previous_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "contract_to_txt.txt").write_text("Text left over from the previous contract.", encoding="utf-8")
    upload_path = tmp_path / "contract.rtf"
    upload_path.write_text("{\\rtf1 not supported}", encoding="utf-8")
    with pytest.raises(UnsupportedFileError, match="'.rtf' files are not supported"):
        convert_to_txt(str(upload_path))
    with pytest.raises(UnsupportedFileError):
        main.scan_contract_with_results(str(upload_path), str(tmp_path / "out.docx"))
    assert not (tmp_path / "out.docx").exists()


def test_flag_findings_reports_errors_instead_of_not_flagged(tmp_path):
    with pytest.raises(FileNotFoundError):
        pdf_to_txt.flag_findings(str(tmp_path / "missing.txt"))
    report = tmp_path / "report.txt"
    report.write_text("Auditor's results\nMaterial weaknesses identified? Yes\n", encoding="utf-8")
    assert pdf_to_txt.flag_findings(str(report)) is True
    report.write_text("Material weaknesses identified? No\n", encoding="utf-8")
    assert pdf_to_txt.flag_findings(str(report)) is False
    report.write_text("", encoding="utf-8")
    assert pdf_to_txt.flag_findings(str(report)) is False


def test_failure_message_explains_known_problems_and_logs_unexpected_ones(caplog):
    assert main.failure_message("a.rtf", UnsupportedFileError("'.rtf' files are not supported.")) == \
        "Could not process a.rtf. '.rtf' files are not supported."
    with caplog.at_level(logging.ERROR, logger="aicr"):
        message = main.failure_message("b.pdf", KeyError("xref"))
    assert message == f"Could not process b.pdf. {main.GENERIC_FAILURE}"
    assert "Could not process b.pdf" in caplog.text


def test_failed_ai_review_is_reported_as_such_and_logged(caplog):
    error = main.AIReviewError("The AI service (gemini) did not return a usable result.")
    error.__cause__ = ConnectionError("rate limited")
    with caplog.at_level(logging.ERROR, logger="aicr"):
        message = main.failure_message("c.docx", error)
    assert message == "Could not review c.docx. The AI service (gemini) did not return a usable result."
    assert "AI review of c.docx failed" in caplog.text


def test_damaged_subcontract_pdf_is_reported_not_marked_clean(client):
    response = upload(client, "audit.pdf", b"%PDF-1.4 this is not a real PDF", "/api/subcontract-scans")
    assert response.status_code == 422
    message = response.json()["detail"]
    assert message.startswith("Could not process audit.pdf.")
    assert "flagged" not in response.json() and "not flagged" not in message


def test_contract_scan_failure_is_reported(client, wait_for_scan):
    started = upload(client, "contract.docx", b"not really a Word document")
    assert started.status_code == 202 and started.json()["stage"] == "queued"
    status = wait_for_scan(client, started.json()["id"])
    assert status["stage"] == "failed"
    assert status["error"].startswith("Could not process contract.docx.")
    assert client.get(f"/api/scans/{status['id']}/download").status_code == 409


@pytest.mark.parametrize("flagged", [0, 3])
def test_successful_scan_says_whether_anything_was_found(client, wait_for_scan, fake_scan, flagged):
    fake_scan(flagged=flagged)
    status = wait_for_scan(client, upload(client, "contract.docx", b"stand-in").json()["id"])
    assert (status["stage"], status["flagged_count"], status["error"]) == ("done", flagged, None)
    assert client.get(f"/api/scans/{status['id']}/download").status_code == 200
