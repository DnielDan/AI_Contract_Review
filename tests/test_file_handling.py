"""Tests for US-2: each upload is isolated, nothing is left on the server, and filenames are safe."""
import os
from concurrent.futures import ThreadPoolExecutor

from docx import Document

import main

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "supplementary_files", "samples_test_set")


def test_safe_filename_drops_folders_and_unusual_characters():
    assert main.safe_filename("../../main.py") == "main.py"
    assert main.safe_filename("..\\..\\Windows\\evil.docx") == "evil.docx"
    assert main.safe_filename("/etc/passwd") == "passwd"
    assert main.safe_filename("0430-23 O'Brien - fully executed.pdf") == "0430-23 O'Brien - fully executed.pdf"
    assert main.safe_filename("contract<>|?*.docx") == "contract_____.docx"
    assert main.safe_filename("....") == "upload"
    assert len(main.safe_filename("a" * 500 + ".docx")) == 105


def test_upload_cannot_be_written_outside_its_working_directory(tmp_path):
    work_dir = tmp_path / "scan_test"
    work_dir.mkdir()
    path = main.write_binary_to_temp_file("../../escaped.docx", b"data", str(work_dir))
    assert os.path.dirname(path) == str(work_dir)
    assert not (tmp_path / "escaped.docx").exists()


def test_successful_scan_sends_bytes_and_leaves_nothing_on_the_server(client, wait_for_scan, fake_scan, tmp_path):
    calls = fake_scan(flagged=2)
    started = client.post("/api/scans", files={"file": ("Lawson agreement.docx", b"contract")})
    assert wait_for_scan(client, started.json()["id"])["stage"] == "done"
    download = client.get(f"/api/scans/{started.json()['id']}/download")
    assert download.content == b"annotated contract"
    assert download.headers["content-disposition"] == 'attachment; filename="Lawson agreement_scanned.docx"'
    (path, output), = calls
    assert os.path.dirname(path) == os.path.dirname(output)  # upload and output share one private directory
    assert os.listdir(tmp_path) == []


def test_failed_scan_leaves_nothing_on_the_server(client, wait_for_scan, tmp_path):
    started = client.post("/api/scans", files={"file": ("contract.docx", b"not really a Word document")})
    assert wait_for_scan(client, started.json()["id"])["stage"] == "failed"
    damaged = client.post("/api/subcontract-scans", files={"file": ("damaged.pdf", b"%PDF-1.4 not really a PDF")})
    assert damaged.status_code == 422
    assert os.listdir(tmp_path) == []


def test_stale_work_dirs_are_removed_but_other_files_are_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "TEMP_DIR", str(tmp_path))
    (tmp_path / "scan_left_over").mkdir()
    (tmp_path / "scan_left_over" / "contract.pdf").write_bytes(b"old upload")
    (tmp_path / ".gitkeep").write_text("")
    main.remove_stale_work_dirs()
    assert os.listdir(tmp_path) == [".gitkeep"]


def test_concurrent_scans_do_not_mix_up_contracts(tmp_path, fake_ai):
    # Before US-2 every scan wrote to the same contract_to_txt.txt, so overlapping scans could
    # return one contract's text inside another contract's results
    jobs = {
        "williams": ("382_PAm-WilliamsFundingAgreementDraft.docx", "Williams"),
        "cmi2": ("CMI2_Auburn_Project_Emergence_Subk_240320.docx", "CMI2"),
    }
    outputs = {}
    for key in jobs:
        (tmp_path / key).mkdir()
        outputs[key] = tmp_path / key / "scanned.docx"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(main.scan_contract_with_results, os.path.join(SAMPLES, sample), str(outputs[key]))
                   for key, (sample, _) in jobs.items()]
        for future in futures:
            future.result()
    texts = {key: "\n".join(p.text for p in Document(outputs[key]).paragraphs) for key in jobs}
    assert "CMI2" in texts["cmi2"] and "CMI2" not in texts["williams"]
    assert "Williams" in texts["williams"] and "Williams" not in texts["cmi2"]
