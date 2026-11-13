"""AI review (US-12): provider selection, matrix-backed output, and fallback to the matcher. No network calls."""
import os

import pytest

import llm_providers
import llm_review
import main
from flag_problem_language import load_tnc_matrix

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


def run_llm_flagging(tmp_path, monkeypatch, reply):
    monkeypatch.setattr(llm_review, "generate_structured", lambda prompt, schema, name: reply)
    contract_txt, flagged_txt = tmp_path / "contract.txt", tmp_path / "flagged.txt"
    contract_txt.write_text(CONTRACT, encoding="utf-8")
    count = llm_review.llm_flag_problem_language(main.TNC_MATRIX_PATH, str(contract_txt), str(flagged_txt))
    return count, flagged_txt.read_text(encoding="utf-8")


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
    assert "ADDITIONAL ISSUES FOUND BY THE AI REVIEW" in text


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


def test_scan_without_llm_uses_matcher_and_no_notice(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(main, "llm_flag_problem_language", lambda *args: called.append(args))
    contract_txt = tmp_path / "contract.txt"
    contract_txt.write_text(CONTRACT, encoding="utf-8")
    _, notice = main.flag_problem_language(str(contract_txt), str(tmp_path / "flagged.txt"))
    assert notice is None and not called


def test_failed_llm_call_falls_back_to_matcher_with_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    def failing_call(*args):
        raise ConnectionError("rate limited")
    monkeypatch.setattr(main, "llm_flag_problem_language", failing_call)
    contract_txt, flagged_txt = tmp_path / "contract.txt", tmp_path / "flagged.txt"
    contract_txt.write_text(CONTRACT, encoding="utf-8")
    _, notice = main.flag_problem_language(str(contract_txt), str(flagged_txt))
    assert "basic matcher" in notice and "openrouter" in notice
    assert os.path.exists(flagged_txt)


def test_missing_key_notice_names_the_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    contract_txt = tmp_path / "contract.txt"
    contract_txt.write_text(CONTRACT, encoding="utf-8")
    _, notice = main.flag_problem_language(str(contract_txt), str(tmp_path / "flagged.txt"))
    assert "GEMINI_API_KEY" in notice


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
