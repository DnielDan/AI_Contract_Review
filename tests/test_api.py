"""US-19: the API the workbench uses. One real scan of a sample contract, with a stand-in for the AI
review (fakes.py); the other tests replace the pipeline with a quick stand-in.

There are no 401 or cross-user scoping tests on purpose: the app has no login yet (US-22, US-8), so
every scan is open to anyone who can reach the server. Add both for every endpoint when login lands."""
import os
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
from contract_to_txt import NO_PDF_TEXT
from fakes import FAKE_MODEL, FAKE_PROVIDER, fake_review_contract, fake_settings

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "supplementary_files", "samples_test_set")
SAMPLE_DOCX = "0078-23 Adhikari - agreement.docx"
SCANNED_PDF = "0264-23 Godwin - fully executed.pdf"  # page images, no text layer
STATUS_FIELDS = {"id", "filename", "stage", "elapsed_seconds", "flagged_count", "error"}


def eventually(condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.02)


@pytest.fixture(scope="module")
def sample_scan(tmp_path_factory, wait_for_scan):
    """A real scan of a sample agreement, with the stand-in AI review, shared by the tests that read its results."""
    temp_dir = tmp_path_factory.mktemp("scans")
    with pytest.MonkeyPatch.context() as patch:
        for name, value in fake_settings().items():
            patch.setenv(name, value)
        patch.setattr(main, "review_contract", fake_review_contract)  # never a real provider
        patch.setattr(main, "TEMP_DIR", str(temp_dir))
        client = TestClient(main.app)
        with open(os.path.join(SAMPLES, SAMPLE_DOCX), "rb") as file:
            started = client.post("/api/scans", files={"file": (SAMPLE_DOCX, file.read())})
        yield client, wait_for_scan(client, started.json()["id"]), temp_dir


@pytest.fixture
def paused_pipeline(monkeypatch):
    """Replaces the pipeline with one that waits after its first step until the returned event is set."""
    release = threading.Event()

    def scan(path, output, on_stage):
        on_stage("extract")
        release.wait(10)
        on_stage("review")
        on_stage("annotate")
        with open(output, "wb") as file:
            file.write(b"annotated")
        return {"paragraphs": ["Text."], "flags": [], "far": [], "review_label": ""}
    monkeypatch.setattr(main, "scan_contract_with_results", scan)
    yield release
    release.set()


def start_paused_scan(client):
    scan_id = client.post("/api/scans", files={"file": ("contract.pdf", b"%PDF-1.4")}).json()["id"]
    eventually(lambda: client.get(f"/api/scans/{scan_id}").json()["stage"] == "extract")
    return scan_id


def test_scan_of_a_real_contract_returns_paragraphs_and_language_flags(sample_scan):
    client, status, _ = sample_scan
    assert status["stage"] == "done", status["error"]
    results = client.get(f"/api/scans/{status['id']}/results").json()
    assert results["paragraphs"]
    assert any(flag["kind"] == "language" and flag["category"] for flag in results["flags"])
    assert all(flag["paragraph"] is None or flag["paragraph"] < len(results["paragraphs"])
               for flag in results["flags"] + results["far"])
    assert status["flagged_count"] == len(results["flags"])
    assert results["review_label"] == f"AI review ({FAKE_PROVIDER}, {FAKE_MODEL})"
    assert any(flag["ai_justification"] == "Stand-in AI justification." for flag in results["flags"])


def test_download_is_the_annotated_docx_and_nothing_is_left_on_disk(sample_scan):
    client, status, temp_dir = sample_scan
    download = client.get(f"/api/scans/{status['id']}/download")
    assert download.status_code == 200 and download.content[:2] == b"PK"
    assert download.headers["content-disposition"] == \
        'attachment; filename="0078-23 Adhikari - agreement_scanned.docx"'
    assert os.listdir(temp_dir) == []


@pytest.mark.parametrize("method, path", [
    ("get", "/api/scans/unknown"), ("get", "/api/scans/unknown/results"),
    ("get", "/api/scans/unknown/download"), ("delete", "/api/scans/unknown"),
])
def test_unknown_scan_is_404(client, method, path):
    response = client.request(method.upper(), path)
    assert response.status_code == 404 and "No scan with this id" in response.json()["detail"]


@pytest.mark.parametrize("name, data, status, message", [
    ("notes.txt", b"plain text", 400, "Only .docx, .doc, or .pdf files can be scanned."),
    ("contract", b"no extension", 400, "Only .docx, .doc, or .pdf files can be scanned."),
    ("empty.docx", b"", 400, "The file is empty."),
    ("large.pdf", b"x" * 11, 413, "The file is larger than 25 MB."),
])
def test_upload_is_rejected_before_a_scan_starts(client, monkeypatch, tmp_path, name, data, status, message):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    response = client.post("/api/scans", files={"file": (name, data)})
    assert (response.status_code, response.json()) == (status, {"detail": message})
    assert main._scans == {} and os.listdir(tmp_path) == []


def test_status_reports_the_stage_while_the_scan_runs(client, paused_pipeline):
    status = client.get(f"/api/scans/{start_paused_scan(client)}").json()
    assert set(status) == STATUS_FIELDS
    assert (status["filename"], status["stage"]) == ("contract.pdf", "extract")
    assert status["elapsed_seconds"] >= 0 and status["error"] is None


def test_failed_ai_review_fails_the_scan_with_the_reason(client, monkeypatch, wait_for_scan, tmp_path):
    def failing_call(*args):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(main, "review_contract", failing_call)
    with open(os.path.join(SAMPLES, SAMPLE_DOCX), "rb") as file:
        scan_id = client.post("/api/scans", files={"file": (SAMPLE_DOCX, file.read())}).json()["id"]
    status = wait_for_scan(client, scan_id, timeout=60)
    # No fallback to the matcher: the reviewer is told the AI review failed and gets no results
    assert status["stage"] == "failed"
    assert status["error"].startswith(f"Could not review {SAMPLE_DOCX}.")
    assert f"AI service ({FAKE_PROVIDER}) did not return a usable result" in status["error"]
    assert client.get(f"/api/scans/{scan_id}/results").status_code == 409
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize("unset", ["LLM_PROVIDER", "GEMINI_API_KEY"])
def test_upload_is_turned_down_while_the_ai_review_is_not_set_up(client, monkeypatch, tmp_path, unset):
    monkeypatch.delenv(unset)
    response = client.post("/api/scans", files={"file": ("contract.docx", b"contract")})
    assert response.status_code == 503
    assert response.json()["detail"].startswith(main.AI_NOT_SET_UP)
    assert unset in response.json()["detail"]
    assert main._scans == {} and os.listdir(tmp_path) == []


def test_results_and_download_wait_until_the_scan_is_done(client, wait_for_scan, paused_pipeline):
    scan_id = start_paused_scan(client)
    assert client.get(f"/api/scans/{scan_id}/results").status_code == 409
    assert client.get(f"/api/scans/{scan_id}/download").status_code == 409
    paused_pipeline.set()
    assert wait_for_scan(client, scan_id)["stage"] == "done"
    assert client.get(f"/api/scans/{scan_id}/results").json()["paragraphs"] == ["Text."]


def test_delete_cancels_a_running_scan_and_forgets_it(client, paused_pipeline, tmp_path):
    scan_id = start_paused_scan(client)
    scan = main._scans[scan_id]
    assert client.delete(f"/api/scans/{scan_id}").status_code == 204
    assert client.get(f"/api/scans/{scan_id}").status_code == 404
    paused_pipeline.set()
    eventually(lambda: scan.stage == "cancelled")
    assert (scan.results, scan.docx_bytes) == (None, None)
    assert os.listdir(tmp_path) == []
    assert client.delete(f"/api/scans/{scan_id}").status_code == 404


def test_contract_scans_run_one_at_a_time(client, monkeypatch, wait_for_scan):
    running, most_at_once, lock = [], [], threading.Lock()

    def scan(path, output, on_stage):
        with lock:
            running.append(path)
            most_at_once.append(len(running))
        on_stage("review")
        time.sleep(0.2)
        with open(output, "wb") as file:
            file.write(b"annotated")
        with lock:
            running.remove(path)
        return {"paragraphs": [], "flags": [], "far": [], "review_label": ""}
    monkeypatch.setattr(main, "scan_contract_with_results", scan)
    scan_ids = [client.post("/api/scans", files={"file": (f"c{n}.docx", b"contract")}).json()["id"] for n in range(3)]
    assert [wait_for_scan(client, scan_id)["stage"] for scan_id in scan_ids] == ["done"] * 3
    assert max(most_at_once) == 1


def test_scan_waiting_for_its_turn_stays_queued_and_can_be_cancelled(client, paused_pipeline, tmp_path):
    start_paused_scan(client)  # holds the turn until the pipeline is released
    waiting_id = client.post("/api/scans", files={"file": ("second.docx", b"contract")}).json()["id"]
    waiting = main._scans[waiting_id]
    time.sleep(main.QUEUE_CHECK_SECONDS * 3)
    assert client.get(f"/api/scans/{waiting_id}").json()["stage"] == "queued"
    assert client.delete(f"/api/scans/{waiting_id}").status_code == 204
    eventually(lambda: waiting.stage == "cancelled")  # while the first scan still holds the turn
    assert waiting.results is None
    assert len(os.listdir(tmp_path)) == 1  # only the running scan's working directory; the queued one wrote nothing


def test_config_says_why_the_ai_review_is_not_set_up(client, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER")
    config = client.get("/api/config").json()
    assert (config["ai_ready"], config["provider"], config["model"]) == (False, None, None)
    assert config["problem"] == f"{main.AI_NOT_SET_UP} (LLM_PROVIDER is not set in .env)"


def test_config_names_the_provider_and_model_when_set_up(client, monkeypatch):
    monkeypatch.delenv("LLM_MODEL")
    assert client.get("/api/config").json() == {
        "ai_ready": True, "problem": None, "provider": "gemini", "model": "gemini-2.5-flash"}


def test_subcontract_scan_returns_whether_findings_were_flagged(client, tmp_path):
    # A subcontract, not an audit report, so none of the audit-finding phrases are in it (see README)
    with open(os.path.join(SAMPLES, "24-00373 Subcontract Auburn University_FE (1).pdf"), "rb") as file:
        response = client.post("/api/subcontract-scans", files={"file": ("audit.pdf", file.read())})
    assert (response.status_code, response.json()) == (200, {"flagged": False})
    assert os.listdir(tmp_path) == []


def test_scanned_pdf_fails_before_the_ai_review_with_the_reason(client, monkeypatch, wait_for_scan, tmp_path):
    reviewed = []
    monkeypatch.setattr(main, "review_contract", lambda *args: reviewed.append(args) or [])
    with open(os.path.join(SAMPLES, SCANNED_PDF), "rb") as file:
        scan_id = client.post("/api/scans", files={"file": ("godwin.pdf", file.read())}).json()["id"]
    status = wait_for_scan(client, scan_id)
    assert (status["stage"], status["flagged_count"]) == ("failed", 0)
    assert status["error"] == f"Could not process godwin.pdf. {NO_PDF_TEXT}"
    assert reviewed == []  # nothing was sent to the AI
    assert os.listdir(tmp_path) == []


def test_subcontract_scan_of_a_scanned_pdf_is_an_error_not_unflagged(client, tmp_path):
    with open(os.path.join(SAMPLES, SCANNED_PDF), "rb") as file:
        response = client.post("/api/subcontract-scans", files={"file": ("audit.pdf", file.read())})
    assert (response.status_code, response.json()) == (422, {"detail": f"Could not process audit.pdf. {NO_PDF_TEXT}"})
    assert os.listdir(tmp_path) == []


def test_subcontract_scan_only_accepts_pdf(client):
    response = client.post("/api/subcontract-scans", files={"file": ("audit.docx", b"data")})
    assert (response.status_code, response.json()) == (400, {"detail": "Only .pdf files can be scanned."})


def test_workbench_serves_index_html_for_app_paths_but_not_for_api_paths(tmp_path):
    (tmp_path / "index.html").write_text("<p>workbench</p>", encoding="utf-8")
    app = FastAPI()
    app.mount("/", main.Workbench(directory=tmp_path, html=True))
    workbench = TestClient(app)
    assert workbench.get("/").text == "<p>workbench</p>"
    assert workbench.get("/scans/abc").text == "<p>workbench</p>"
    assert workbench.get("/api/unknown").status_code == 404
