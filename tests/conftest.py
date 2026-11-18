"""Keeps every test offline: a developer's .env may set LLM_PROVIDER and an API key, but tests must
never call a hosted LLM or send contract text off the machine (US-15). LLM_PROVIDER is cleared before
every test, and the functions that call a provider are replaced with ones that fail the test. Tests that
need a full scan use the fake_ai fixture, which makes the AI review look set up and answers with a
stand-in (fakes.py).

Also holds the API fixtures shared by the test files. They import main inside the fixture, so the
browser test (test_e2e_workbench.py) can run with an interpreter that only has Playwright."""
import time

import pytest

FINISHED_STAGES = ("done", "failed", "cancelled")


@pytest.fixture(autouse=True)
def no_llm_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    try:
        import llm_providers
    except ImportError:  # the browser test's interpreter may not have the project's packages
        return

    def blocked(*args, **kwargs):
        raise AssertionError("A test tried to call a hosted LLM; use the fake_ai fixture instead")
    monkeypatch.setattr(llm_providers, "_openai_compatible", blocked)
    monkeypatch.setattr(llm_providers, "_anthropic", blocked)


@pytest.fixture
def fake_ai(monkeypatch):
    """Makes the AI review look set up (provider, fake key, model) and answers with fakes.fake_review_contract."""
    import main
    from fakes import fake_review_contract, fake_settings
    for name, value in fake_settings().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(main, "review_contract", fake_review_contract)


@pytest.fixture
def client(monkeypatch, tmp_path, fake_ai):
    """The API with the AI review set up (fake_ai), a fresh list of scans, and working directories in tmp_path."""
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

    def install(flagged=0, docx=b"annotated contract"):
        calls = []

        def scan(path, output, on_stage):
            calls.append((path, output))
            with open(output, "wb") as file:
                file.write(docx)
            return {"paragraphs": [], "flags": [{}] * flagged, "far": [], "review_label": ""}
        monkeypatch.setattr(main, "scan_contract_with_results", scan)
        return calls
    return install
