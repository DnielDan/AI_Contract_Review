"""Builds the labeled test set (US-9a) from OSP's own markup in the sample contracts.

OSP reviewers mark up incoming contracts by striking through sponsor language they reject,
typing Auburn's replacement language in red (sometimes as tracked insertions), and adding
comments that explain why. This script reconstructs each contract's original sponsor text
(struck and deleted text kept; red and inserted text removed), splits it into sentences the
same way the scanner does, and labels a sentence as a problem when OSP struck, deleted,
commented on, or inserted language into it. All other sentences are labeled "ok", meaning
OSP left them unchanged (not that OSP confirmed them).

Run from the repository root:  python -m evaluation.build_test_set [--force]
It writes evaluation/data/<doc_id>.txt and evaluation/labels.csv. labels.csv is then
reviewed by hand, so the script will not overwrite it unless --force is given.
"""
import csv
import os
import sys
import zipfile

from lxml import etree
from nltk import data as nltk_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "supplementary_files", "samples_test_set")
EVAL_DIR = os.path.join(ROOT, "evaluation")
DATA_DIR = os.path.join(EVAL_DIR, "data")
LABELS_PATH = os.path.join(EVAL_DIR, "labels.csv")

nltk_data.path.append(os.path.join(ROOT, "supplementary_files", "nltk_data"))

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
AUBURN_RED = "FF0000"

# Contracts with OSP markup. Two are held out for the Cycle 3 validation pass, so that
# tuning in Cycle 2 never sees them.
DOCUMENTS = {
    "adhikari": ("0078-23 Adhikari - agreement.docx", "dev"),
    "lawson": ("1611-23 Lawson - agreement.docx", "dev"),
    "williams_funding": ("382_PAm-WilliamsFundingAgreementDraft.docx", "dev"),
    "cmi2": ("CMI2_Auburn_Project_Emergence_Subk_240320_Auburn Review.docx", "dev"),
    "proposed_revisions": ("Proposed Contract Revisions - Auburn V1.docx", "dev"),
    "hale": ("1102-23 Hale - agreement.docx", "holdout"),
    "mou": ("Auburn University Memorandum of Understanding (AU edits).docx", "holdout"),
}

# Draft issue type for each OSP-marked sentence: the Ts&Cs Matrix sheet that covers the topic,
# or "other" for administrative corrections the matrix does not address (wrong ID numbers,
# funding amounts, payment logistics, reporting deadlines). Drafted by the team for review.
_SHEET_RANGES = {
    "adhikari": [((57, 60), "Dispute Resolution"), ((61, 63), "Limitation of Liability"),
                 ((64, 66), "Govering Law"), ((154, 154), "other")],
    "lawson": [((15, 17), "other"), ((159, 163), "Dispute Resolution"),
               ((164, 166), "Limitation of Liability"), ((171, 174), "Govering Law")],
    "williams_funding": [((44, 46), "Warranties"), ((55, 55), "Govering Law")],
    "cmi2": [((30, 30), "other"), ((76, 76), "Limitation of Liability"), ((88, 88), "Records Retention"),
             ((96, 96), "Intellectual Property")],
    "proposed_revisions": [((13, 15), "other"), ((34, 47), "Insurance"), ((48, 51), "Limitation of Liability"),
                           ((55, 56), "Assignment"), ((80, 82), "Use of Name"), ((91, 91), "Warranties"),
                           ((288, 288), "Govering Law")],
    "hale": [((97, 98), "Limitation of Liability"), ((102, 103), "Govering Law")],
    "mou": [((124, 126), "Limitation of Liability"), ((127, 127), "Insurance"), ((175, 176), "Govering Law")],
}


def draft_issue_type(doc_id, sentence_index):
    for (first, last), sheet in _SHEET_RANGES.get(doc_id, []):
        if first <= sentence_index <= last:
            return sheet if sheet == "other" else f"matrix: {sheet}"
    return "unassigned"


FIELDS = ["doc_id", "split", "sentence_index", "label", "evidence", "osp_note", "issue_type", "reviewed", "sentence"]


def _is_auburn_addition(run, inside_insertion):
    color = run.find(f"{W}rPr/{W}color")
    return inside_insertion or (color is not None and color.get(f"{W}val", "").upper() == AUBURN_RED)


def _is_struck(run):
    strike = run.find(f"{W}rPr/{W}strike")
    return strike is not None and strike.get(f"{W}val", "true") not in ("0", "false")


def reconstruct(docx_path):
    """Returns (original_text, marks, notes).

    marks[i] is the set of evidence types for character i of original_text; notes maps
    character positions to OSP comment text anchored there.
    """
    with zipfile.ZipFile(docx_path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        comments = {}
        if "word/comments.xml" in archive.namelist():
            for comment in etree.fromstring(archive.read("word/comments.xml")).iter(f"{W}comment"):
                comments[comment.get(f"{W}id")] = " ".join((t.text or "") for t in comment.iter(f"{W}t")).strip()

    chars, marks, char_notes = [], [], []
    open_comments = []
    pending_insertion = None  # evidence waiting to attach to the next original character

    def mark_previous(evidence, note=None):
        # Attach evidence to the original character just before an Auburn insertion
        for i in range(len(chars) - 1, -1, -1):
            if chars[i] != "\n":
                marks[i].add(evidence)
                if note:
                    char_notes[i].add(note)
                return True
        return False

    # Walk the whole body once, in document order, so that comment markers placed between
    # paragraphs and paragraphs nested in text boxes are each handled exactly once
    body = document.find(f"{W}body")
    for element in body.iter():
        if element.tag == f"{W}p" and not any(a.tag == f"{W}p" for a in element.iterancestors()):
            if chars and chars[-1] != "\n":
                chars.append("\n"); marks.append(set()); char_notes.append(set())
        elif element.tag == f"{W}commentRangeStart":
            open_comments.append(element.get(f"{W}id"))
        elif element.tag == f"{W}commentRangeEnd":
            if element.get(f"{W}id") in open_comments:
                open_comments.remove(element.get(f"{W}id"))
        elif element.tag == f"{W}r":
            inside_insertion = any(a.tag == f"{W}ins" for a in element.iterancestors())
            inside_deletion = any(a.tag == f"{W}del" for a in element.iterancestors())
            texts = [t for t in element if t.tag in (f"{W}t", f"{W}delText", f"{W}tab", f"{W}br")]
            if _is_auburn_addition(element, inside_insertion):
                # Auburn's own language: not part of the sponsor's contract, but it marks
                # the sentence it was added to (or the comment anchored on it) as a problem
                added = "".join(t.text or "" for t in texts if t.tag == f"{W}t")
                if added.strip():
                    note = "; ".join(n for n in (comments.get(c, "") for c in open_comments) if n) or None
                    if not mark_previous("inserted", note):
                        pending_insertion = ("inserted", note)
                continue
            for piece in texts:
                if piece.tag == f"{W}tab":
                    text = " "
                elif piece.tag == f"{W}br":
                    text = "\n"
                else:
                    text = piece.text or ""
                for char in text:
                    evidence, notes = set(), set()
                    if inside_deletion:
                        evidence.add("tracked_deletion")
                    if _is_struck(element) and char.strip():
                        evidence.add("struck")
                    for comment_id in open_comments:
                        evidence.add("comment")
                        if comments.get(comment_id):
                            notes.add(comments[comment_id])
                    if pending_insertion and char.strip():
                        evidence.add(pending_insertion[0])
                        if pending_insertion[1]:
                            notes.add(pending_insertion[1])
                        pending_insertion = None
                    chars.append(char); marks.append(evidence); char_notes.append(notes)
    return "".join(chars), marks, char_notes


def label_sentences(text, marks, char_notes):
    tokenizer = nltk_data.load("tokenizers/punkt/english.pickle")
    rows = []
    for index, (start, end) in enumerate(tokenizer.span_tokenize(text)):
        evidence = set().union(*marks[start:end]) if end > start else set()
        notes = set().union(*char_notes[start:end]) if end > start else set()
        rows.append({
            "sentence_index": index,
            "label": "problem" if evidence else "ok",
            "evidence": "+".join(sorted(evidence)),
            "osp_note": " || ".join(sorted(notes)),
            "sentence": " ".join(text[start:end].split()),
        })
    return rows


def main():
    force = "--force" in sys.argv
    if os.path.exists(LABELS_PATH) and not force:
        sys.exit(f"{LABELS_PATH} exists and may contain reviewed labels; rerun with --force to overwrite.")
    os.makedirs(DATA_DIR, exist_ok=True)
    all_rows = []
    for doc_id, (filename, split) in DOCUMENTS.items():
        text, marks, char_notes = reconstruct(os.path.join(SAMPLES, filename))
        with open(os.path.join(DATA_DIR, f"{doc_id}.txt"), "w", encoding="utf-8") as file:
            file.write(text)
        rows = label_sentences(text, marks, char_notes)
        for row in rows:
            issue_type = draft_issue_type(doc_id, row["sentence_index"]) if row["label"] == "problem" else ""
            row.update({"doc_id": doc_id, "split": split, "issue_type": issue_type, "reviewed": ""})
        all_rows.extend(rows)
        problems = sum(row["label"] == "problem" for row in rows)
        print(f"{doc_id:20} {split:8} {len(rows):4} sentences, {problems:3} problems")
    with open(LABELS_PATH, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Wrote {len(all_rows)} labeled sentences to {LABELS_PATH}")


if __name__ == "__main__":
    main()
