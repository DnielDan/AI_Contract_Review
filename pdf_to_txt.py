from PyPDF2 import PdfReader
import mmap

# Converts pdf to txt
def pdf_to_txt(pdf_path):
    no_ext = pdf_path[:-4]
    txt_fname = no_ext + ".txt"

    pdf_file_obj = open(pdf_path, 'rb')

    pdf_reader = PdfReader(pdf_file_obj)

    page_count = len(pdf_reader.pages)

    page_obj = pdf_reader.pages[page_count - 1]

    pdf_text = ''

    for i in range(page_count - 1):
        page_obj = pdf_reader.pages[i]
        pdf_text += (page_obj.extract_text())

    with open(txt_fname, 'w', encoding="utf-8") as file:
        file.write(pdf_text)
    
    return txt_fname


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
