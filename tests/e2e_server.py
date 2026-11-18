"""Runs the app for the browser test (test_e2e_workbench.py) with the stand-in AI review from fakes.py,
so the test scans a sample contract without calling an AI provider or needing a key.

    python tests/e2e_server.py      (AICR_HOST and AICR_PORT as for main.py)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import anthropic  # noqa: E402
import openai  # noqa: E402
import uvicorn  # noqa: E402

import main  # noqa: E402
from fakes import fake_review_contract, fake_settings  # noqa: E402


def blocked(*args, **kwargs):
    raise RuntimeError("The browser test server never calls a real AI provider")


if __name__ == "__main__":
    os.environ.update(fake_settings())  # after main loaded .env, so the fake settings win
    main.review_contract = fake_review_contract
    openai.OpenAI = anthropic.Anthropic = blocked
    uvicorn.run(main.app, host=main.HOST, port=main.PORT)
