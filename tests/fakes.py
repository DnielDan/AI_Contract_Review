"""A stand-in for the AI review, so scans can run end to end in tests without calling a provider.
Used by conftest.py (the fake_ai fixture) and by e2e_server.py (the browser test's server)."""

FAKE_PROVIDER = "gemini"
FAKE_KEY_ENV = "GEMINI_API_KEY"
FAKE_KEY = "test-key-not-a-real-key"
FAKE_MODEL = "test-model"
MIN_QUOTE_LENGTH = 20


# Replaces llm_review.review_contract: flags the contract's first paragraph that is long enough to be
# located, against the first Common Problem of the first matrix sheet that has one
def fake_review_contract(contract_text, tnc_dictionary, before_retry=None):
    category = next(name for name, sheet in tnc_dictionary.items() if sheet.get("Common Problems"))
    quote = next((line.strip() for line in contract_text.split("\n") if len(line.strip()) >= MIN_QUOTE_LENGTH), None)
    if quote is None:
        return []
    return [{
        "quote": quote,
        "category": category,
        "matched_problem": str(tnc_dictionary[category]["Common Problems"][0]),
        "justification": "Stand-in AI justification.",
        "suggested_change": "Stand-in AI wording.",
        "confidence": "high",
    }]


# The settings that make the AI review look set up: a provider, a fake key, and a fixed model name
def fake_settings():
    return {"LLM_PROVIDER": FAKE_PROVIDER, FAKE_KEY_ENV: FAKE_KEY, "LLM_MODEL": FAKE_MODEL}
