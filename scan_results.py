"""The results of a scan as data for the workbench (US-19): the contract's paragraphs, each flagged
passage with its Ts&Cs Matrix guidance, and each FAR clause found with its FAR Matrix note.

The flags are the same (flagged text, details) pairs that flag_problem_language.write_flagged_text
writes into the annotated document, so the workbench and the .docx always show the same flags.
"""
import math

from flag_FAR_clauses import _clause_pattern, _note_value, flag_clauses, read_far_matrix
from flag_problem_language import _normalize, _paragraph_for


# Finds the FAR clauses in the contract text the same way annotate_contract does, and the FAR Matrix
# row of each clause. Returns ({clause: status}, {clause: row}).
def far_matches(contract_text, far_matrix_path):
    far = read_far_matrix(far_matrix_path)
    clauses = flag_clauses(contract_text, far['Clause'].tolist(), far['Acceptance Status*'].tolist())
    rows = {row['Clause']: row for _, row in far.iterrows()}
    return clauses, rows


def build_results(contract_text, flags, far_clauses, far_rows, review_label):
    paragraphs = [paragraph.strip() for paragraph in contract_text.split("\n") if paragraph.strip()]
    return {
        "paragraphs": paragraphs,
        "flags": _language_flags(flags, paragraphs),
        "far": _far_flags(far_clauses, far_rows, paragraphs),
        "review_label": review_label,
    }


# Language flags in document order; a flag that could not be located in the text comes last
def _language_flags(flags, paragraphs):
    normalized = [_normalize(paragraph) for paragraph in paragraphs]
    placed = [(_paragraph_for(text, paragraphs, normalized), text, details) for text, details in flags]
    placed.sort(key=lambda flag: (flag[0] is None, flag[0] or 0))
    return [_language_flag(f"L{number}", paragraph, text, details or {})
            for number, (paragraph, text, details) in enumerate(placed, 1)]


# Maps the details of a flag (llm_review._issue_details) to the fields the workbench shows; a missing one
# becomes None. A numeric confidence is still accepted, as the old TF-IDF matcher's similarity score was.
def _language_flag(flag_id, paragraph, text, details):
    return {
        "id": flag_id,
        "kind": "language",
        "paragraph": paragraph,
        "sentence": str(text),
        "category": _text(details.get("Problem Category")),
        "why": _text(details.get("Why")),
        "preferred": _text(details.get("Preferred Language")),
        "response": _text(details.get("1st response to Sponsor")),
        "ai_justification": _text(details.get("AI justification")),
        "ai_suggested": _text(details.get("AI suggested change")),
        "confidence": _confidence(details.get("Confidence")),
    }


# FAR clauses in the order they first appear in the contract
def _far_flags(far_clauses, far_rows, paragraphs):
    found = [(_first_paragraph_with(clause, paragraphs), clause, status) for clause, status in far_clauses.items()]
    found.sort(key=lambda clause: (clause[0] is None, clause[0] or 0))
    return [_far_flag(f"F{number}", paragraph, clause, status, far_rows.get(clause, {}))
            for number, (paragraph, clause, status) in enumerate(found, 1)]


# Reads the title, criteria and request the way _add_far_notes writes them into the .docx
def _far_flag(flag_id, paragraph, clause, status, row):
    return {
        "id": flag_id,
        "kind": "far",
        "clause": clause,
        "status": status,
        "title": _note_value(row.get('Title')) or None,
        "criteria": _note_value(row.get('Acceptance Criteria or Additional Notes')) or None,
        "request": _note_value(row.get('Request to Sponsor')) or None,
        "paragraph": paragraph,
    }


def _first_paragraph_with(clause, paragraphs):
    pattern = _clause_pattern(clause)
    return next((i for i, paragraph in enumerate(paragraphs) if pattern.search(paragraph)), None)


# Matrix cells can be empty, numbers, or (for Auburn's preferred language) a list of paragraphs
def _text(value):
    if isinstance(value, (list, tuple)):
        value = "\n\n".join(str(item).strip() for item in value if item)
    elif isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip() if value is not None else ""
    return text or None


# The matcher's confidence is a similarity score; the AI review's is "low", "medium" or "high"
def _confidence(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None if math.isnan(value) else round(float(value), 2)
    return _text(value)
