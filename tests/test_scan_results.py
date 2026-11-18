"""US-19: a scan's flags as the data the workbench shows (scan_results.build_results)."""
import numpy as np
import pytest

from scan_results import build_results

FLAGGED = "The Sponsor shall own all intellectual property arising from the research."
CONTRACT = "\n".join([
    "RESEARCH AGREEMENT",
    "",
    f"This Agreement begins on January 1. {FLAGGED} Payment is due within thirty days.",
    "The Contractor shall comply with FAR 52.204-21, Basic Safeguarding.",
])
MATCHER_DETAILS = {
    "Problem Category": "Intellectual Property",
    "Common Problems": "sponsor owns all IP",
    "Preferred Language": ["Title to inventions shall vest in Auburn.", None, "Sponsor receives a license."],
    "Why": "Auburn keeps title to its inventions.",
    "1st response to Sponsor": None,
    "Confidence": np.float64(0.41234),
}
LLM_DETAILS = {
    "Problem Category": "Intellectual Property",
    "Common Problems": "sponsor owns all IP",
    "Preferred Language": ["Title to inventions shall vest in Auburn."],
    "Why": "Auburn keeps title to its inventions.",
    "1st response to Sponsor": "We propose a non-exclusive license.",
    "AI justification": "Gives the sponsor all IP.",
    "AI suggested change": "Title vests in the inventing party.",
    "Confidence": "high",
}
FAR_ROW = {"Title": "Basic Safeguarding of Covered Contractor Information Systems.",
           "Acceptance Criteria or Additional Notes": float("nan"), "Request to Sponsor": "Please remove."}


def results_for(flags, far_clauses=None, far_rows=None, ai_notice=None):
    return build_results(CONTRACT, flags, far_clauses or {}, far_rows or {}, "Basic matcher", ai_notice)


@pytest.mark.parametrize("details, expected", [
    (MATCHER_DETAILS, {
        "category": "Intellectual Property", "why": "Auburn keeps title to its inventions.",
        "preferred": "Title to inventions shall vest in Auburn.\n\nSponsor receives a license.",
        "response": None, "ai_justification": None, "ai_suggested": None, "confidence": 0.41}),
    (LLM_DETAILS, {
        "category": "Intellectual Property", "why": "Auburn keeps title to its inventions.",
        "preferred": "Title to inventions shall vest in Auburn.", "response": "We propose a non-exclusive license.",
        "ai_justification": "Gives the sponsor all IP.", "ai_suggested": "Title vests in the inventing party.",
        "confidence": "high"}),
    ({}, {
        "category": None, "why": None, "preferred": None, "response": None,
        "ai_justification": None, "ai_suggested": None, "confidence": None}),
], ids=["matcher", "llm", "missing-keys"])
def test_flag_details_map_to_the_workbench_fields(details, expected):
    flag = results_for([(FLAGGED, details)])["flags"][0]
    assert {key: flag[key] for key in expected} == expected
    assert flag["kind"] == "language" and flag["sentence"] == FLAGGED


def test_blank_lines_are_dropped_from_the_paragraphs():
    assert results_for([])["paragraphs"] == [line for line in CONTRACT.split("\n") if line]


def test_language_flags_resolve_their_paragraph_and_unplaced_flags_come_last():
    flags = results_for([("Text that appears nowhere in this contract at all.", {}), (FLAGGED, {})])["flags"]
    assert [(flag["id"], flag["paragraph"]) for flag in flags] == [("L1", 1), ("L2", None)]


def test_far_clause_gets_its_paragraph_and_matrix_note():
    far = results_for([], {"52.204-21": "C"}, {"52.204-21": FAR_ROW})["far"]
    assert far == [{
        "id": "F1", "kind": "far", "clause": "52.204-21", "status": "C",
        "title": "Basic Safeguarding of Covered Contractor Information Systems", "criteria": None,
        "request": "Please remove", "paragraph": 2,
    }]


def test_far_clause_missing_from_the_matrix_rows_has_empty_notes():
    far = results_for([], {"52.204-21": "OK"})["far"][0]
    assert (far["title"], far["criteria"], far["request"]) == (None, None, None)


@pytest.mark.parametrize("ai_notice, method", [(None, "llm"), ("AI review unavailable", "matcher")])
def test_review_method_says_which_review_produced_the_flags(monkeypatch, ai_notice, method):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    results = results_for([], ai_notice=ai_notice)
    assert (results["review_method"], results["ai_notice"]) == (method, ai_notice)


def test_review_method_is_matcher_without_an_llm():
    assert results_for([])["review_method"] == "matcher"
