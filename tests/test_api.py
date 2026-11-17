"""US-19: the API the workbench uses. One real scan of a sample contract with the basic matcher (no LLM);
the other tests replace the pipeline with a quick stand-in.

There are no 401 or cross-user scoping tests on purpose: the app has no login yet (US-22, US-8), so
every scan is open to anyone who can reach the server. Add both for every endpoint when login lands."""
import os
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "supplementary_files", "samples_test_set")
SAMPLE_DOCX = "0078-23 Adhikari - agreement.docx"
STATUS_FIELDS = {"id", "filename", "stage", "review_method", "elapsed_seconds", "flagged_count", "ai_notice", "error"}


def eventually(condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.02)


@pytest.fixture(scope="module")
def sample_scan(tmp_path_factory, wait_for_scan):
    """A real scan of a sample agreement (about 30 seconds), shared by the tests that read its results."""
    temp_dir = tmp_path_factory.mktemp("scans")
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("LLM_PROVIDER", raising=False)  # so provider_name() is None: the matcher, never an LLM
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
        return {"paragraphs": ["Text."], "flags": [], "far": [], "review_label": "", "review_method": "matcher",
                "ai_notice": None}
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
    assert (status["flagged_count"], status["review_method"]) == (len(results["flags"]), "matcher")
    assert (results["review_method"], results["ai_notice"]) == ("matcher", None)


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
    assert (status["filename"], status["stage"], status["review_method"]) == ("contract.pdf", "extract", "matcher")
    assert status["elapsed_seconds"] >= 0 and status["error"] is None


def test_status_reports_fallback_before_the_scan_finishes(client, monkeypatch, wait_for_scan):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    def failing_call(*args):
        raise RuntimeError("no reply")
    monkeypatch.setattr(main, "review_contract", failing_call)
    monkeypatch.setattr(main, "flag_sentences", lambda *args: {})  # the real matcher takes about 30 seconds here
    release = threading.Event()
    annotate = main.annotate_contract

    def paused_annotate(*args):
        release.wait(10)
        annotate(*args)
    monkeypatch.setattr(main, "annotate_contract", paused_annotate)
    with open(os.path.join(SAMPLES, SAMPLE_DOCX), "rb") as file:
        scan_id = client.post("/api/scans", files={"file": (SAMPLE_DOCX, file.read())}).json()["id"]
    try:
        eventually(lambda: client.get(f"/api/scans/{scan_id}").json()["stage"] == "annotate")
        status = client.get(f"/api/scans/{scan_id}").json()
        assert status["review_method"] == "matcher"
        assert status["ai_notice"].startswith("AI review unavailable")
    finally:
        release.set()
    assert wait_for_scan(client, scan_id, timeout=30)["stage"] == "done"


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


def test_config_reports_the_matcher_without_an_llm(client):
    assert client.get("/api/config").json() == {"review_method": "matcher", "provider": None, "model": None}


def test_config_names_the_llm_when_one_is_configured(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert client.get("/api/config").json() == {"review_method": "llm", "provider": "gemini", "model": "gemini-2.5-flash"}


def test_subcontract_scan_returns_whether_findings_were_flagged(client, tmp_path):
    with open(os.path.join(SAMPLES, "0264-23 Godwin - fully executed.pdf"), "rb") as file:
        response = client.post("/api/subcontract-scans", files={"file": ("audit.pdf", file.read())})
    assert response.status_code == 200 and isinstance(response.json()["flagged"], bool)
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
