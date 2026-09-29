from contract_to_txt import extract_pdf_text
import mmap
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


# Method that searches txt files for things in findings_list
def flag_findings(txt_file):
    findings_list = [b"Material weaknesses identified? Yes",
                     b"Noncompliance material to financial statements noted? Yes",
                     b"Significant deficiencies identified? Yes",
                    ]
    try:
        with open(txt_file) as f:
            for i in findings_list:
                s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                if s.find(i) != -1:
                    return True
    except:
        return False
    return False
