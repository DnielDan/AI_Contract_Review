"""Tests for US-3a: failures are reported to the user, distinct from "no problems found"."""
import asyncio
import io
import logging

import pytest

import main
import pdf_to_txt
from contract_to_txt import UnsupportedFileError, convert_to_txt


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self.content = io.BytesIO(data)


@pytest.fixture
def notifications(monkeypatch, tmp_path):
    """Captures ui.notify calls and keeps uploads and outputs inside tmp_path."""
    sent = []
    monkeypatch.setattr(main.ui, "notify", lambda message, **options: sent.append((message, options.get("type"))))
    monkeypatch.setattr(main.ui, "download", lambda src, filename=None: sent.append(("download", filename)))
    monkeypatch.setattr(main, "TEMP_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    async def run_inline(function, *args):
        return function(*args)
    monkeypatch.setattr(main.run, "cpu_bound", run_inline)
    return sent


def test_unsupported_file_type_raises_instead_of_reusing_the_previous_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "contract_to_txt.txt").write_text("Text left over from the previous contract.", encoding="utf-8")
    upload = tmp_path / "contract.rtf"
    upload.write_text("{\\rtf1 not supported}", encoding="utf-8")
    with pytest.raises(UnsupportedFileError, match="'.rtf' files are not supported"):
        convert_to_txt(str(upload))
    with pytest.raises(UnsupportedFileError):
        main.scan_file(str(upload), str(tmp_path / "out.docx"))
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


def test_damaged_subcontract_pdf_is_reported_not_marked_clean(notifications):
    main.handle_sub_upload(FakeUpload("audit.pdf", b"%PDF-1.4 this is not a real PDF"))
    assert len(notifications) == 1
    message, kind = notifications[0]
    assert message.startswith("Could not process audit.pdf.") and kind == "warning"
    assert "not flagged" not in message


def test_contract_scan_failure_is_reported(notifications):
    asyncio.run(main.handle_contract_upload(FakeUpload("contract.rtf", b"{\\rtf1}")))
    assert ("Scanning file...", None) in notifications
    assert any(m.startswith("Could not process contract.rtf.") and k == "warning" for m, k in notifications)
    assert not any(m == "download" for m, _ in notifications)


@pytest.mark.parametrize("flagged, expected", [(0, "no problem language found"), (3, "3 passage(s) of potential problem language flagged")])
def test_successful_scan_says_whether_anything_was_found(notifications, monkeypatch, flagged, expected):
    def fake_scan(path, output):
        with open(output, "wb") as file:
            file.write(b"annotated")
        return flagged
    monkeypatch.setattr(main, "scan_file", fake_scan)
    asyncio.run(main.handle_contract_upload(FakeUpload("contract.docx", b"stand-in")))
    assert any(expected in m for m, _ in notifications)
    assert notifications[-1][0] == "download"
