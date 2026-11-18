"""Reads the Ts&Cs Matrix and writes the contract text with each flagged passage marked.

The TF-IDF matcher that used to live here is now evaluation/tfidf_matcher.py (accuracy baseline only).
"""
import openpyxl
import re
from nltk.tokenize import sent_tokenize

def extract_sheet_data(sheet):

    data = {
        "Auburn's Preferred Language": [],
        'Common Problems' : [],
        'Why': [],
        '1st response to Sponsor' : []
    }
    # Quick fix for ensuring both cell title forms are adressed, 
    # could/should probably be improved in future
    auburn_title = ["Auburn's Preferred Language", 'Auburn Preferred Language']

    current_key = None
    for row in sheet.iter_rows(values_only = True):
        if not row[1]: continue #skip empty rows in second columnn

        if row[1] in auburn_title: 
            current_key =  "Auburn's Preferred Language"
            continue

        if row[1] in data.keys():
            current_key = row[1]
            continue

        if current_key == 'Common Problems':
            data['Common Problems'].append(row[1])
            data['Why'].append(row[2] if len(row) > 2 and row[2] else None)
            data['1st response to Sponsor'].append(row[3] if len(row) > 3 and row[3] else None)
        elif current_key == "Auburn's Preferred Language":
            data[current_key].append(row[1])

    return data

# This function exists solely for testing purposes
# used to generate a readable representation of the parsed T&Cs matrix
def pretty_print_nested_values(dictionary):
    output = []
    for page_title, inner_dict in dictionary.items():
        output.append(page_title)
        for cell_title, values in inner_dict.items():
            output.append("\t" + cell_title + ":")
            for value in values:
                str_value = str(value) if value is not None else "None"
                output.append("\t\t" + str_value)
        output.append('')  # Add a blank line for separation
    return "\n".join(output)

# Loads every topic sheet of the Ts&Cs Matrix into {sheet name: sheet data}
def load_tnc_matrix(tnc_path_in):
    wb = openpyxl.load_workbook(tnc_path_in)

    sheet_names = wb.sheetnames

    tnc_dictionary = {}

    for sheet_name in sheet_names:
        if sheet_name != "INDEX" and sheet_name != "template" and sheet_name != "CONTACTS":
            sheet = wb[sheet_name]
            sheet_data = extract_sheet_data(sheet)
            tnc_dictionary[sheet_name] = sheet_data

    return tnc_dictionary

# Markers around each flagged paragraph in the flagged text; flag_FAR_clauses.py styles the output from them
PROBLEM_START_MARKER = "[POTENTIAL PROBLEMATIC LANGUAGE DETECTED]"
PROBLEM_END_MARKER = "[END POTENTIAL PROBLEMATIC LANGUAGE]"
BANNER = "*******************************************************************************************"
FLAGGED_SENTENCE_LABEL = "Flagged sentence:"
UNPLACED_HEADER = "ADDITIONAL FLAGGED LANGUAGE (passage not located in the extracted text)"
# Flagged text shorter than this only counts when it is a whole sentence of the paragraph, so a short
# phrase such as "the Sponsor" cannot attach to every paragraph that contains it
MIN_PARTIAL_MATCH_LENGTH = 20


def _normalize(text):
    text = str(text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


# Returns the index of the paragraph a flagged sentence or quote belongs to, or None
def _paragraph_for(flagged_text, paragraphs, normalized_paragraphs):
    target = _normalize(flagged_text)
    if not target:
        return None
    if len(target) < MIN_PARTIAL_MATCH_LENGTH:
        for i, paragraph in enumerate(paragraphs):
            if target == normalized_paragraphs[i] or target in (_normalize(s) for s in sent_tokenize(paragraph)):
                return i
        return None
    for i, paragraph in enumerate(normalized_paragraphs):
        if target in paragraph:
            return i
    # Text that runs across lines (common in PDFs) or spans several paragraphs: use the line it starts on
    start = target[:MIN_PARTIAL_MATCH_LENGTH * 2]
    for i, paragraph in enumerate(normalized_paragraphs):
        if paragraph and (start in paragraph or (len(paragraph) >= MIN_PARTIAL_MATCH_LENGTH and paragraph in target)):
            return i
    return None


def _write_block(lines, text, flags_here, paragraph_is_flag):
    lines.append("\t\t" + BANNER)
    lines.append(PROBLEM_START_MARKER)
    lines.append(text)
    for flagged_text, details in flags_here:
        if not paragraph_is_flag:
            lines.append(f"\t\t{FLAGGED_SENTENCE_LABEL} {flagged_text}")
        for key, value in details.items():
            if isinstance(value, (list, tuple)):
                value = "; ".join(str(item) for item in value if item)
            lines.append(f"\t\t{key}: {value}")
    lines.append("\t\t" + PROBLEM_END_MARKER)
    lines.append(BANNER)


# Writes the contract paragraph by paragraph, as extracted, and marks each paragraph that contains flagged
# language, followed by a "Flagged sentence" line and the details of each flag in it. flags is a list of
# (flagged sentence or quote, details dict). Flags that cannot be located are listed at the end.
# Shared by the TF-IDF matcher and the LLM review (llm_review.py), so both produce the same layout.
def write_flagged_text(contract_text, flags, flagged_txt_path):
    paragraphs = contract_text.split("\n")
    normalized = [_normalize(paragraph) for paragraph in paragraphs]
    placed, unplaced = {}, []
    for flagged_text, details in flags:
        index = _paragraph_for(flagged_text, paragraphs, normalized)
        if index is None:
            unplaced.append((flagged_text, details))
        else:
            placed.setdefault(index, []).append((flagged_text, details))

    lines = []
    for i, paragraph in enumerate(paragraphs):
        if i in placed:
            whole = len(placed[i]) == 1 and _normalize(placed[i][0][0]) == normalized[i]
            _write_block(lines, paragraph, placed[i], whole)
        else:
            lines.append(paragraph)
    if unplaced:
        lines.append(UNPLACED_HEADER)
        for flagged_text, details in unplaced:
            _write_block(lines, flagged_text, [(flagged_text, details)], True)

    with open(flagged_txt_path, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(line + "\n")
