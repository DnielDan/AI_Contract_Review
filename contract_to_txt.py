import os
import struct
import docx2txt
import olefile
from docx import Document
from pypdf import PdfReader

# Raised for files the scanner cannot process; the message is shown to the user as-is
class UnsupportedFileError(Exception):
    pass

# Some PDFs contain control characters that Word documents cannot store, which crashed the scan;
# drop them, keeping tabs and line breaks
_PDF_CONTROL_CHARACTERS = {code: None for code in range(32) if code not in (9, 10, 13)}
_PDF_CONTROL_CHARACTERS[13] = '\n'

# Returns the text of every page of a PDF; pages with no extractable text contribute nothing
def extract_pdf_text(pdf_path):
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        text = '\n'.join(page.extract_text() or '' for page in pdf_reader.pages)
    return text.translate(_PDF_CONTROL_CHARACTERS)

# Returns the main body text of a legacy Word 97-2003 (.doc) file.
# Reads the document's piece table directly, so no copy of Word or LibreOffice is needed.
def extract_doc_text(doc_path):
    with olefile.OleFileIO(doc_path) as ole:
        word_stream = ole.openstream('WordDocument').read()
        flags = struct.unpack_from('<H', word_stream, 0x0A)[0]
        if flags & 0x0100:
            raise UnsupportedFileError('Password-protected .doc files are not supported.')
        table_stream = ole.openstream('1Table' if flags & 0x0200 else '0Table').read()

    # Locate the character count and piece table (Clx) through the File Information Block
    csw = struct.unpack_from('<H', word_stream, 32)[0]
    long_values_start = 34 + csw * 2 + 2
    text_length = struct.unpack_from('<i', word_stream, long_values_start + 3 * 4)[0]
    cslw = struct.unpack_from('<H', word_stream, 34 + csw * 2)[0]
    offsets_start = long_values_start + cslw * 4 + 2
    clx_offset, clx_length = struct.unpack_from('<II', word_stream, offsets_start + 33 * 8)
    clx = table_stream[clx_offset:clx_offset + clx_length]

    # Skip any formatting entries to reach the piece table
    i = 0
    while clx[i] == 0x01:
        i += 3 + struct.unpack_from('<H', clx, i + 1)[0]
    if clx[i] != 0x02:
        raise UnsupportedFileError('This .doc file could not be read. Try saving it as .docx in Word and uploading that.')
    piece_table_length = struct.unpack_from('<I', clx, i + 1)[0]
    piece_table = clx[i + 5:i + 5 + piece_table_length]
    piece_count = (piece_table_length - 4) // 12
    positions = struct.unpack_from(f'<{piece_count + 1}I', piece_table, 0)

    pieces = []
    for k in range(piece_count):
        start, end = positions[k], min(positions[k + 1], text_length)
        if start >= text_length:
            break
        file_offset = struct.unpack_from('<I', piece_table, (piece_count + 1) * 4 + k * 8 + 2)[0]
        char_count = end - start
        if file_offset & 0x40000000:
            # Compressed piece: one byte per character
            offset = (file_offset & ~0x40000000) // 2
            pieces.append(word_stream[offset:offset + char_count].decode('cp1252', errors='replace'))
        else:
            pieces.append(word_stream[file_offset:file_offset + 2 * char_count].decode('utf-16-le', errors='replace'))
    return _clean_word_text(''.join(pieces))

# Converts Word's special characters to plain text: keeps field results, drops field codes,
# and turns paragraph, line, page, and table-cell marks into line breaks
def _clean_word_text(text):
    output = []
    in_field_code = []
    for char in text:
        if char == '\x13':
            in_field_code.append(True)
        elif char == '\x14':
            if in_field_code:
                in_field_code[-1] = False
        elif char == '\x15':
            if in_field_code:
                in_field_code.pop()
        elif in_field_code and in_field_code[-1]:
            continue
        elif char in '\r\x0b\x0c\x07':
            output.append('\n')
        elif char == '\x1e':
            output.append('-')
        elif char == '\t' or char >= ' ':
            output.append(char)
    return ''.join(output)

# Removes blank lines and surrounding whitespace, then writes the text for the rest of the pipeline
def _write_clean_text(raw_text, txt_path):
    lines = [line.strip() for line in raw_text.strip().split('\n')]
    cleaned_text = '\n'.join(line for line in lines if line)

    with open(txt_path, 'w', encoding="utf-8") as file:
        file.write(cleaned_text)

# Function to process and clean the content of a DOCX file
def _clean_docx(docx_path, txt_path):
    _write_clean_text(docx2txt.process(docx_path), txt_path)

# Function to process and clean the content of a legacy DOC file
def _clean_doc(doc_path, txt_path):
    _write_clean_text(extract_doc_text(doc_path), txt_path)

# Function to process and clean the content of a PDF file
def _clean_pdf(pdf_path, txt_path):
    with open(txt_path, 'w', encoding="utf-8") as file:
        file.write(extract_pdf_text(pdf_path))

# Function to convert a txt file to docx file
def txt_to_docx(txt_filepath, cleaned_docx_filepath):
    # Initialize a Document
    doc = Document()

    # Open and read the txt file
    with open(txt_filepath, 'r', encoding = "utf8") as txt_file:
        # Loop over each line in the txt file
        for line in txt_file:
            # Add a paragraph for each line in txt to docx
            doc.add_paragraph(line.strip())

    # Save the Document
    doc.save(cleaned_docx_filepath)

# Writes the contract's text to txt_path; the app passes a path inside the upload's own working directory
def convert_to_txt(contract_in, txt_path='contract_to_txt.txt'):
    extension = os.path.splitext(contract_in)[1].lower()
    if extension == '.pdf':
        _clean_pdf(contract_in, txt_path)
    elif extension == '.docx':
        _clean_docx(contract_in, txt_path)
    elif extension == '.doc':
        _clean_doc(contract_in, txt_path)
    else:
        # Raising (rather than returning an error string) stops the scan here; otherwise the next
        # step would read text left over from an earlier scan
        raise UnsupportedFileError(f"'{extension or 'no extension'}' files are not supported. Upload a .docx, .doc, or .pdf file.")
