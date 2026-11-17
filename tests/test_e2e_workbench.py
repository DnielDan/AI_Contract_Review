"""Browser test of the workbench (US-19): a real scan of a sample contract through the built frontend
and the API, with the basic matcher. Left out of the default run because it needs Playwright with
Chromium and the built frontend:

    cd frontend && npm run build
    python -m pytest -m e2e tests/test_e2e_workbench.py

The server runs in its own process with the interpreter in AICR_E2E_PYTHON (default: the one running
the test), so the test can run with any interpreter that has Playwright while the server uses the
project's virtual environment."""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytestmark = pytest.mark.e2e

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "supplementary_files", "samples_test_set", "0078-23 Adhikari - agreement.docx")
SCAN_TIMEOUT_MS = 180_000
COLLAPSED_PANEL_MAX_WIDTH = 180


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_up(url, process, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The server stopped with exit code {process.returncode}")
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"The server did not answer at {url} within {timeout} seconds")


@pytest.fixture(scope="module")
def sync_api():
    return pytest.importorskip("playwright.sync_api")


# Requests sync_api first, so nothing is started when Playwright is missing
@pytest.fixture(scope="module")
def server(sync_api):
    if not os.path.isfile(os.path.join(ROOT, "frontend", "dist", "index.html")):
        pytest.fail("The workbench is not built: run npm ci and npm run build in frontend/")
    port = free_port()
    # An empty LLM_PROVIDER takes precedence over .env, so the scan never calls an LLM
    env = {**os.environ, "AICR_HOST": "127.0.0.1", "AICR_PORT": str(port), "LLM_PROVIDER": ""}
    process = subprocess.Popen([os.environ.get("AICR_E2E_PYTHON", sys.executable), "main.py"], cwd=ROOT, env=env)
    try:
        wait_until_up(f"http://127.0.0.1:{port}/api/config", process)
        yield f"http://127.0.0.1:{port}/"
    finally:
        process.terminate()
        process.wait(timeout=30)


def test_scan_shows_highlighted_flags_and_the_panel_collapses(sync_api, server):
    errors = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda message: message.type == "error" and errors.append(message.text))
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server)

        page.set_input_files("#file-input", SAMPLE)
        page.wait_for_selector(".flag", timeout=SCAN_TIMEOUT_MS)
        card = page.locator(".flag").first
        flag_id = card.get_attribute("data-flag-id")
        card.click()
        sync_api.expect(page.locator(f'mark.sel[data-flag-id="{flag_id}"]').first).to_be_visible()

        page.click("#chevron")
        page.wait_for_function(f"document.querySelector('.side').getBoundingClientRect().width <= {COLLAPSED_PANEL_MAX_WIDTH}")
        browser.close()
    assert not errors, f"console errors: {errors}"
