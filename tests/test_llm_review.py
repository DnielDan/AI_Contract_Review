"""AI review (US-12): provider selection, matrix-backed output, and failures reported without a matcher
fallback. No network calls."""
import pytest

import llm_providers
import llm_review
import main
from flag_problem_language import load_tnc_matrix, write_flagged_text

TNC = load_tnc_matrix(main.TNC_MATRIX_PATH)
# A real matrix row, so the tests check that guidance is looked up from the matrix
CATEGORY = next(name for name, sheet in TNC.items() if sheet["Common Problems"] and sheet["Why"][0])
PROBLEM = TNC[CATEGORY]["Common Problems"][0]
FLAGGED = "The Sponsor shall own all intellectual property arising from the research performed under this Agreement."
CONTRACT = f"This Agreement begins on January 1. {FLAGGED} Payment is due within thirty days."


def fake_reply(quote=FLAGGED, matched_problem=PROBLEM):
    return {"issues": [{
        "quote": quote, "category": CATEGORY, "matched_problem": matched_problem,
        "justification": "AI says this is a problem.", "suggested_change": "AI replacement wording.",
        "confidence": "high",
    }]}


# Runs the app's AI review (main.ai_flags) on CONTRACT with `reply` as the model's answer, writes the
# flagged text as the scan does, and returns the number of flags and that text
def run_llm_flagging(tmp_path, monkeypatch, reply):
    monkeypatch.setattr(llm_review, "generate_structured", lambda prompt, schema, name: reply)
    flags = main.ai_flags(CONTRACT)
    flagged_txt = tmp_path / "flagged.txt"
    write_flagged_text(CONTRACT, flags, str(flagged_txt))
    return len(flags), flagged_txt.read_text(encoding="utf-8")


def test_flagged_passage_gets_matrix_guidance_and_ai_suggestion(tmp_path, monkeypatch):
    count, text = run_llm_flagging(tmp_path, monkeypatch, fake_reply())
    assert count == 1
    assert text.count("[POTENTIAL PROBLEMATIC LANGUAGE DETECTED]") == 1
    assert f"Problem Category: {CATEGORY}" in text
    assert f"Why: {TNC[CATEGORY]['Why'][0]}" in text  # from the matrix, not the model
    assert "AI suggested change: AI replacement wording." in text
    assert "Payment is due within thirty days." in text  # unflagged text is kept


def test_quote_not_in_contract_is_listed_at_the_end(tmp_path, monkeypatch):
    count, text = run_llm_flagging(tmp_path, monkeypatch, fake_reply(quote="Text that is nowhere in the contract at all."))
    assert count == 1
    assert "ADDITIONAL FLAGGED LANGUAGE" in text


def test_problem_not_in_matrix_is_marked(tmp_path, monkeypatch):
    _, text = run_llm_flagging(tmp_path, monkeypatch, fake_reply(matched_problem="Something the model invented"))
    assert "(not found in the matrix)" in text


def test_short_quote_does_not_flag_every_sentence_containing_it(tmp_path, monkeypatch):
    count, _ = run_llm_flagging(tmp_path, monkeypatch, fake_reply(quote="the Sponsor"))
    assert count == 1  # listed at the end, not matched inside the sentence


def test_schema_limits_categories_to_matrix_sheets():
    schema = llm_review._issue_schema(TNC.keys())
    assert schema["properties"]["issues"]["items"]["properties"]["category"]["enum"] == sorted(TNC)


def test_unset_provider_means_no_llm(monkeypatch):
    assert llm_providers.provider_name() is None
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert llm_providers.provider_name() is None


@pytest.mark.parametrize("provider, key", [("openrouter", "OPENROUTER_API_KEY"),
                                           ("anthropic", "ANTHROPIC_API_KEY"),
                                           ("gemini", "GEMINI_API_KEY")])
def test_missing_key_gives_a_clear_error(monkeypatch, provider, key):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.delenv(key, raising=False)
    with pytest.raises(llm_providers.LLMConfigError, match=key):
        llm_providers.generate_structured("prompt", {}, "name")


def test_unknown_provider_gives_a_clear_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "copilot")
    with pytest.raises(llm_providers.LLMConfigError, match="Unknown LLM_PROVIDER"):
        llm_providers.generate_structured("prompt", {}, "name")


def test_json_wrapped_in_text_is_parsed():
    assert llm_providers._parse_json_text('Here you go:\n```json\n{"issues": []}\n```') == {"issues": []}


@pytest.mark.parametrize("settings, problem", [
    ({}, "LLM_PROVIDER is not set"),
    ({"LLM_PROVIDER": "copilot"}, "Unknown LLM_PROVIDER 'copilot'"),
    ({"LLM_PROVIDER": "anthropic"}, "ANTHROPIC_API_KEY is not set"),
    ({"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "key"}, None),
])
def test_configuration_problem_checks_the_settings_without_calling_the_provider(monkeypatch, settings, problem):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    result = llm_providers.configuration_problem()
    assert result is None if problem is None else problem in result


def test_without_a_provider_there_is_no_review_and_no_matcher(monkeypatch):
    with pytest.raises(main.AIReviewError, match="LLM_PROVIDER is not set") as raised:
        main.ai_flags(CONTRACT)
    assert str(raised.value).startswith(main.AI_NOT_SET_UP)


def test_failed_llm_call_is_reported_not_replaced_by_the_matcher(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    def failing_call(*args):
        raise ConnectionError("rate limited")
    monkeypatch.setattr(main, "review_contract", failing_call)
    with pytest.raises(main.AIReviewError, match=r"AI service \(openrouter\) did not return a usable result") as raised:
        main.ai_flags(CONTRACT)
    assert isinstance(raised.value.__cause__, ConnectionError)  # logged with the scan failure


def test_missing_key_is_reported_as_not_set_up_and_names_the_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(main.AIReviewError, match="GEMINI_API_KEY") as raised:
        main.ai_flags(CONTRACT)
    assert str(raised.value).startswith(main.AI_NOT_SET_UP)


def test_issues_returned_as_json_strings_are_accepted(tmp_path, monkeypatch):
    import json
    issue = fake_reply()["issues"][0]
    count, text = run_llm_flagging(tmp_path, monkeypatch, {"issues": [json.dumps(issue), "not json", 7]})
    assert count == 1 and "AI suggested change: AI replacement wording." in text
    count, _ = run_llm_flagging(tmp_path, monkeypatch, {"issues": json.dumps([issue])})
    assert count == 1


def test_issue_list_wrapped_in_text_is_read(tmp_path, monkeypatch):
    import json
    wrapped = "Here are the issues:\n```json\n" + json.dumps(fake_reply()["issues"]) + "\n```"
    count, _ = run_llm_flagging(tmp_path, monkeypatch, {"issues": wrapped})
    assert count == 1


def test_unreadable_reply_is_retried_then_reported(monkeypatch):
    replies = iter([{"issues": "not json at all"}, fake_reply()])
    monkeypatch.setattr(llm_review, "generate_structured", lambda *args: next(replies))
    assert len(llm_review.review_contract(CONTRACT, TNC)) == 1
    monkeypatch.setattr(llm_review, "generate_structured", lambda *args: {"issues": "still not json"})
    with pytest.raises(ValueError, match="list of issues"):
        llm_review.review_contract(CONTRACT, TNC)


def test_workbench_flags_from_the_ai_review_carry_matrix_guidance(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_review, "generate_structured", lambda *args: fake_reply())
    (quote, details), = main.ai_flags(CONTRACT)
    assert quote == FLAGGED and details["Why"] == TNC[CATEGORY]["Why"][0]  # from the matrix, not the model
    assert details["AI justification"] == "AI says this is a problem."
