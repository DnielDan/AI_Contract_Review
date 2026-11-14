import pandas as pd
import re
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import RGBColor

from flag_problem_language import BANNER, PROBLEM_END_MARKER, PROBLEM_START_MARKER, UNPLACED_HEADER

# Paragraphs containing flagged Ts&Cs language
PROBLEM_HIGHLIGHT = WD_COLOR_INDEX.YELLOW
# Everything the tool adds that is not in the original contract: matrix guidance, AI lines, FAR notes
ADDED_TEXT_HIGHLIGHT = WD_COLOR_INDEX.GRAY_25
# Lines written by the AI review rather than taken from the matrix; also shown in italic blue
AI_LINE_PREFIXES = ('AI justification:', 'AI suggested change:')
AI_TEXT_COLOR = RGBColor(0x1F, 0x4E, 0x79)
STATUS_NAMES = {'OK': 'OK', 'C': 'Conditional', 'REMOVE': 'Remove'}

# Main Program. review_label, when given, is shown at the top to say which review flagged the language.
def annotate_contract(xls_in, contract_in, save_path, review_label=None):
    # Read FAR Matrix and clean it
    xls_matrix_path = xls_in
    df_clean = read_far_matrix(xls_matrix_path)
    xls_clauses = df_clean['Clause'].tolist()
    acceptance_status = df_clean['Acceptance Status*'].tolist()
    far_notes = {row['Clause']: row for _, row in df_clean.iterrows()}

    # Read Contract Text
    contract_text = read_docx(contract_in)

    # Flag Clauses in Contract Text
    flagged_clauses = flag_clauses(contract_text, xls_clauses, acceptance_status)

    # Create New Annotated Document
    new_doc = Document()
    original_doc = Document(contract_in)

    if review_label:
        label = new_doc.add_paragraph().add_run(f'Problem language reviewed by: {review_label}')
        label.bold = True
    add_color_code(new_doc)
    in_block = passage_is_next = False
    noted_clauses = set()
    for paragraph in original_doc.paragraphs:
        new_paragraph = annotate_paragraph(paragraph, flagged_clauses, new_doc)
        text = paragraph.text.strip()
        if passage_is_next and text:
            # The paragraph with flagged language, from the original contract; FAR colors in it take precedence
            for run in new_paragraph.runs:
                if run.font.highlight_color is None:
                    run.font.highlight_color = PROBLEM_HIGHLIGHT
            passage_is_next = False
            _add_far_notes(new_doc, paragraph.text, flagged_clauses, far_notes, noted_clauses)
            continue
        if text == PROBLEM_START_MARKER:
            in_block = passage_is_next = True
        added_by_tool = in_block or text in (BANNER, UNPLACED_HEADER, PROBLEM_END_MARKER)
        if text == PROBLEM_END_MARKER:
            in_block = False
        if added_by_tool:
            _mark_added(new_paragraph, ai=text.startswith(AI_LINE_PREFIXES))
        else:
            _add_far_notes(new_doc, paragraph.text, flagged_clauses, far_notes, noted_clauses)

    # Save Annotated Document
    new_doc.save(save_path)

# Highlights text the tool added; AI-written lines are also italic blue
def _mark_added(paragraph, ai=False):
    for run in paragraph.runs:
        run.font.highlight_color = ADDED_TEXT_HIGHLIGHT
        if ai:
            run.italic = True
            run.font.color.rgb = AI_TEXT_COLOR

def _note_value(value):
    text = '' if pd.isna(value) else str(value).strip()
    return text.rstrip('.')

# After a paragraph that mentions FAR clauses, adds a note from the FAR Matrix for each clause
# the first time it appears: title, acceptance status, acceptance criteria, and request to sponsor
def _add_far_notes(new_doc, text, flagged_clauses, far_notes, noted_clauses):
    for clause, status in flagged_clauses.items():
        if clause in noted_clauses or not _clause_pattern(clause).search(text):
            continue
        noted_clauses.add(clause)
        row = far_notes.get(clause, {})
        title = _note_value(row.get('Title'))
        note = f"FAR {clause}{', ' + title if title else ''}: {STATUS_NAMES.get(status, status)}."
        criteria = _note_value(row.get('Acceptance Criteria or Additional Notes'))
        request = _note_value(row.get('Request to Sponsor'))
        if criteria:
            note += f" {criteria}."
        if request:
            note += f" Request to Sponsor: {request}."
        paragraph = new_doc.add_paragraph()
        paragraph.add_run(note)
        _mark_added(paragraph)

# Acceptance statuses from least to most restrictive, and the highlight used for each
STATUS_SEVERITY = {'OK': 0, 'C': 1, 'REMOVE': 2}
STATUS_COLORS = {
    'OK': WD_COLOR_INDEX.BRIGHT_GREEN,   # Green for OK
    'C': WD_COLOR_INDEX.TURQUOISE,       # Turquoise for Conditional (would be blue but it's hard to read)
    'REMOVE': WD_COLOR_INDEX.RED,        # Red for Remove
}
# A FAR clause number, such as 52.204-21
_CLAUSE_NUMBER = re.compile(r'^\d{2}\.\d{3}-\d{1,4}$')

# Function to read FAR Matrix from Excel and return clean DataFrame.
# Keeps only rows whose Clause is a real clause number: the matrix also has 326 archived rows whose
# Clause is "OLD" and one "RESERVED" row, which used to match ordinary words like "hold" and "reserved".
# Statuses are normalized ("Remove", " C", "OK " were never highlighted), and a clause listed more than
# once keeps its most restrictive status, so the tool never shows a clause as more acceptable than OSP does.
def read_far_matrix(excel_path):
    df = pd.read_excel(excel_path)
    df_clean = df.dropna(subset=['Clause ', 'Acceptance Status*'])
    df_clean = df_clean[['Clause ', 'Acceptance Status*', 'Title', 'Acceptance Criteria or Additional Notes',
                         'Request to Sponsor']]
    df_clean = df_clean.rename(columns={'Clause ': 'Clause'})
    df_clean['Clause'] = df_clean['Clause'].astype(str).str.strip()
    df_clean['Acceptance Status*'] = df_clean['Acceptance Status*'].astype(str).str.strip().str.upper()
    df_clean = df_clean[df_clean['Clause'].str.match(_CLAUSE_NUMBER) & df_clean['Acceptance Status*'].isin(STATUS_SEVERITY)]
    df_clean = (df_clean.assign(severity=df_clean['Acceptance Status*'].map(STATUS_SEVERITY))
                .sort_values('severity', kind='stable')
                .drop_duplicates('Clause', keep='last')
                .drop(columns='severity')
                .sort_index())
    return df_clean

# Matches a clause number on its own, so "52.204-2" does not match inside "52.204-21"
def _clause_pattern(clause):
    return re.compile(rf'(?<![\d.]){re.escape(clause)}(?!\d)')

# Returns the more restrictive of two statuses
def _stricter(status_a, status_b):
    return max(status_a, status_b, key=lambda status: STATUS_SEVERITY.get(status, -1))

# Function to read text from a .docx file
def read_docx(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

# Function to flag clauses in contract text
def flag_clauses(contract_text, xls_clauses, acceptance_status):
    flagged_clauses = {}
    for clause, status in zip(xls_clauses, acceptance_status):
        if _clause_pattern(clause).search(contract_text):
            flagged_clauses[clause] = _stricter(flagged_clauses.get(clause, status), status)
    return flagged_clauses

def add_color_code(new_doc):
    paragraph = new_doc.add_paragraph()

    lines = ['FAR Acceptance Status Color Code', 'Green = OK', 'Turquoise = Conditional', 'Red = Remove',
             'Yellow = Potential problem language (Ts&Cs Matrix)',
             'Gray = added by the tool from the FAR and Ts&Cs Matrices (and the AI review); not in the original contract']
    colors = [WD_COLOR_INDEX.WHITE, WD_COLOR_INDEX.BRIGHT_GREEN, WD_COLOR_INDEX.TURQUOISE, WD_COLOR_INDEX.RED,
              PROBLEM_HIGHLIGHT, ADDED_TEXT_HIGHLIGHT]

    for line, color in zip(lines, colors):
        run = paragraph.add_run(line)
        if lines[0] == line: 
            run.bold = True 
            run.underline = True
        run.font.highlight_color = color
        run.add_break()
    ai_note = paragraph.add_run('Italic blue = written by the AI review, not taken from the matrix')
    ai_note.italic = True
    ai_note.font.color.rgb = AI_TEXT_COLOR
    ai_note.font.highlight_color = ADDED_TEXT_HIGHLIGHT


# Function to annotate a paragraph based on flagged clauses and their acceptance status
def annotate_paragraph(paragraph, flagged_clauses, new_doc):
    new_paragraph = new_doc.add_paragraph()
    for run in paragraph.runs:
        new_run = new_paragraph.add_run(run.text, run.style.name)
        new_run.font.highlight_color = run.font.highlight_color if run.font.highlight_color else None
        # When a run mentions several clauses, show the most restrictive status among them
        strictest = None
        for clause, status in flagged_clauses.items():
            if _clause_pattern(clause).search(run.text):
                strictest = status if strictest is None else _stricter(strictest, status)
        if strictest in STATUS_COLORS:
            new_run.font.highlight_color = STATUS_COLORS[strictest]
    return new_paragraph
