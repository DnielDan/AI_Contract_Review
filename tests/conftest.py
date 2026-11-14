"""Keeps every test offline: a developer's .env may set LLM_PROVIDER and an API key, but tests must
never call a hosted LLM or send contract text off the machine (US-15). Tests that exercise the AI
review set LLM_PROVIDER themselves and replace the network call."""
import pytest


@pytest.fixture(autouse=True)
def no_llm_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
