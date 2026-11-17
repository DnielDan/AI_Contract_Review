"""Keeps every test offline: a developer's .env may set LLM_PROVIDER and an API key, but tests must
never call a hosted LLM or send contract text off the machine (US-15). Tests that exercise the AI
review set LLM_PROVIDER themselves and replace the network call.

Also holds the API fixtures shared by the test files. They import main inside the fixture, so the
browser test (test_e2e_workbench.py) can run with an interpreter that only has Playwright."""
import time

import pytest

FINISHED_STAGES = ("done", "failed", "cancelled")


@pytest.fixture(autouse=True)
def no_llm_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


@pytest.fixture
def client(monkeypatch, tmp_path):
    """The API, with a fresh list of scans whose working directories go in tmp_path."""
    from fastapi.testclient import TestClient

    import main
    monkeypatch.setattr(main, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_scans", {})
    return TestClient(main.app)


@pytest.fixture(scope="session")
def wait_for_scan():
    """Returns a function that polls a scan through an API client until it has finished, and returns its status."""
    def wait(client, scan_id, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = client.get(f"/api/scans/{scan_id}").json()
            if status["stage"] in FINISHED_STAGES:
                return status
            time.sleep(0.05)
        raise AssertionError(f"scan {scan_id} did not finish within {timeout} seconds")
    return wait


@pytest.fixture
def fake_scan(monkeypatch):
    """Returns a function that replaces the scan pipeline with a quick one, which writes `docx` as the
    annotated copy and reports `flagged` flags. The returned list collects (upload path, output path)."""
    import main

    def install(flagged=0, ai_notice=None, docx=b"annotated contract"):
        calls = []

        def scan(path, output, on_stage):
            calls.append((path, output))
            with open(output, "wb") as file:
                file.write(docx)
            return {"paragraphs": [], "flags": [{}] * flagged, "far": [], "review_label": "",
                    "review_method": "matcher", "ai_notice": ai_notice}
        monkeypatch.setattr(main, "scan_contract_with_results", scan)
        return calls
    return install
