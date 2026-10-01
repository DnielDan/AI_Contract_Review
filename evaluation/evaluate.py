"""Scores a scanner against the labeled test set (US-9a).

Run from the repository root:
    python -m evaluation.evaluate --scanner baseline --split dev

The dev split is for development and tuning. The holdout split is reserved for the Cycle 3
validation pass; do not tune against it.

Reports, per document and overall:
  caught        problem sentences the scanner flagged
  missed        problem sentences it did not flag
  false alarms  "ok" sentences it flagged
  precision     caught / (caught + false alarms): how often a flag is a real problem
  recall        caught / (caught + missed): how many real problems it finds
Recall is also given for matrix-related problems only, and per clause (a clause counts as
caught if any of its sentences is flagged, since one flag is enough to draw a reviewer to it).
"""
import argparse
import csv
import os
import time
from collections import defaultdict

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH = os.path.join(EVAL_DIR, "labels.csv")
DATA_DIR = os.path.join(EVAL_DIR, "data")
RESULTS_DIR = os.path.join(EVAL_DIR, "results")

# A quoted excerpt shorter than this is too vague to credit to a sentence
MIN_EXCERPT_CHARS = 20


def normalize(text):
    return " ".join(text.split()).lower()


def load_labels(split):
    with open(LABELS_PATH, encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if split == "all" or row["split"] == split]
    for row in rows:
        row["sentence_index"] = int(row["sentence_index"])
    return rows


def match_flags(sentences, flags):
    """Returns the set of sentence positions (indexes into sentences) covered by the flags.

    A flag covers a sentence when one contains the other, so both whole-sentence flags and
    quoted excerpts that span or sit inside a sentence are credited. Short text on either side
    (such as a heading like "Arbitration.") only counts on an exact match, so it is not
    credited just because the same word appears inside some other flagged passage.
    """
    normalized_sentences = [normalize(sentence) for sentence in sentences]
    covered = set()
    for flag in flags:
        normalized_flag = normalize(flag)
        if not normalized_flag:
            continue
        for position, sentence in enumerate(normalized_sentences):
            if not sentence:
                continue
            if sentence == normalized_flag:
                covered.add(position)
            elif len(sentence) >= MIN_EXCERPT_CHARS and sentence in normalized_flag:
                covered.add(position)
            elif len(normalized_flag) >= MIN_EXCERPT_CHARS and normalized_flag in sentence:
                covered.add(position)
    return covered


def score(rows, flagged_positions):
    """rows: labeled sentences of one or more documents; flagged_positions: indexes into rows."""
    counts = defaultdict(int)
    for position, row in enumerate(rows):
        flagged = position in flagged_positions
        problem = row["label"] == "problem"
        counts["caught" if problem and flagged else "missed" if problem else "false_alarm" if flagged else "correct_ok"] += 1
        if problem and row["issue_type"].startswith("matrix"):
            counts["matrix_problems"] += 1
            counts["matrix_caught"] += flagged

    # Clauses: runs of consecutive problem sentences in the same document with the same issue type
    clauses = []
    for position, row in enumerate(rows):
        if row["label"] != "problem":
            continue
        previous = rows[position - 1] if position else None
        continues_clause = (previous is not None and previous["label"] == "problem" and previous["doc_id"] == row["doc_id"]
                            and previous["issue_type"] == row["issue_type"]
                            and previous["sentence_index"] == row["sentence_index"] - 1)
        if continues_clause:
            clauses[-1].append(position)
        else:
            clauses.append([position])
    counts["clauses"] = len(clauses)
    counts["clauses_caught"] = sum(any(p in flagged_positions for p in clause) for clause in clauses)

    def ratio(numerator, denominator):
        return numerator / denominator if denominator else float("nan")

    counts["precision"] = ratio(counts["caught"], counts["caught"] + counts["false_alarm"])
    counts["recall"] = ratio(counts["caught"], counts["caught"] + counts["missed"])
    counts["matrix_recall"] = ratio(counts["matrix_caught"], counts["matrix_problems"])
    counts["clause_recall"] = ratio(counts["clauses_caught"], counts["clauses"])
    return counts


def evaluate(scanner, split):
    rows = load_labels(split)
    by_doc = defaultdict(list)
    for row in rows:
        by_doc[row["doc_id"]].append(row)

    flagged_positions, per_doc, predictions = set(), {}, []
    offset = 0
    ordered_rows = []
    for doc_id, doc_rows in by_doc.items():
        with open(os.path.join(DATA_DIR, f"{doc_id}.txt"), encoding="utf-8") as file:
            text = file.read()
        start = time.perf_counter()
        flags = scanner(text)
        seconds = time.perf_counter() - start
        covered = match_flags([row["sentence"] for row in doc_rows], flags)
        doc_scores = score(doc_rows, covered)
        doc_scores["seconds"] = seconds
        per_doc[doc_id] = doc_scores
        flagged_positions |= {offset + position for position in covered}
        for position, row in enumerate(doc_rows):
            predictions.append({**row, "flagged": position in covered})
        ordered_rows.extend(doc_rows)
        offset += len(doc_rows)
    overall = score(ordered_rows, flagged_positions)
    overall["seconds"] = sum(doc["seconds"] for doc in per_doc.values())
    return overall, per_doc, predictions


def format_report(scanner_name, split, overall, per_doc):
    def pct(value):
        return "n/a" if value != value else f"{value:.0%}"

    lines = [
        f"# Evaluation: `{scanner_name}` on the `{split}` split",
        "",
        "| Document | Problems | Caught | Missed | False alarms | Precision | Recall | Clause recall | Seconds |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for doc_id, s in list(per_doc.items()) + [("**Overall**", overall)]:
        problems = s["caught"] + s["missed"]
        lines.append(f"| {doc_id} | {problems} | {s['caught']} | {s['missed']} | {s['false_alarm']} | "
                     f"{pct(s['precision'])} | {pct(s['recall'])} | {s['clauses_caught']}/{s['clauses']} | {s['seconds']:.1f} |")
    lines += [
        "",
        f"- Matrix-related problems caught: {overall['matrix_caught']}/{overall['matrix_problems']} ({pct(overall['matrix_recall'])})",
        f"- Sentences flagged in total: {overall['caught'] + overall['false_alarm']} of "
        f"{overall['caught'] + overall['missed'] + overall['false_alarm'] + overall['correct_ok']}",
        "",
        "Labels come from OSP's own markup of these contracts (see evaluation/README.md). \"ok\" means OSP",
        "left a sentence unchanged, not that OSP confirmed it, so precision is a lower bound.",
    ]
    return "\n".join(lines)


def main():
    from evaluation.scanners import SCANNERS

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scanner", default="baseline", choices=sorted(SCANNERS))
    parser.add_argument("--split", default="dev", choices=["dev", "holdout", "all"])
    parser.add_argument("--no-save", action="store_true", help="print the report without saving it")
    args = parser.parse_args()

    overall, per_doc, predictions = evaluate(SCANNERS[args.scanner], args.split)
    report = format_report(args.scanner, args.split, overall, per_doc)
    print(report)
    if not args.no_save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        base = os.path.join(RESULTS_DIR, f"{args.scanner}_{args.split}")
        with open(base + ".md", "w", encoding="utf-8") as file:
            file.write(report + "\n")
        with open(base + "_predictions.csv", "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(predictions[0]))
            writer.writeheader()
            writer.writerows(predictions)
        print(f"\nSaved {base}.md and {base}_predictions.csv")


if __name__ == "__main__":
    main()
