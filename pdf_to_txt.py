from contract_to_txt import extract_pdf_text
import os

# Converts pdf to txt
def pdf_to_txt(pdf_path):
    txt_fname = os.path.splitext(pdf_path)[0] + ".txt"

    with open(txt_fname, 'w', encoding="utf-8") as file:
        file.write(extract_pdf_text(pdf_path))

    return txt_fname


# Checks a PDF for audit findings without leaving a .txt copy of it behind
def scan_for_findings(pdf_path):
    txt_file = pdf_to_txt(pdf_path)
    try:
        return flag_findings(txt_file)
    finally:
        os.remove(txt_file)


# Method that searches txt files for things in findings_list.
# Errors are no longer swallowed: an unreadable file used to be reported as "not flagged".
def flag_findings(txt_file):
    findings_list = ["Material weaknesses identified? Yes",
                     "Noncompliance material to financial statements noted? Yes",
                     "Significant deficiencies identified? Yes",
                    ]
    with open(txt_file, encoding="utf-8") as f:
        text = f.read()
    return any(finding in text for finding in findings_list)
