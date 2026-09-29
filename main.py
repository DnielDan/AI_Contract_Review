from nicegui import ui, run, app
import os
from contract_to_txt import convert_to_txt, txt_to_docx
from flag_FAR_clauses import annotate_contract
from flag_problem_language import _flag_problem_language
from nltk import data as nltk
import pdf_to_txt

# Resolve paths from this file's folder so the app runs on any OS and from any working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPLEMENTARY_DIR = os.path.join(BASE_DIR, "supplementary_files")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Append the custom path to the NLTK data path
nltk.path.append(os.path.join(SUPPLEMENTARY_DIR, "nltk_data"))

FAR_CLAUSE_MATRIX_PATH = os.path.join(SUPPLEMENTARY_DIR, "2023-03-20_FAR Matrix.xls")
TNC_MATRIX_PATH = os.path.join(SUPPLEMENTARY_DIR, "Contract Ts&Cs Matrix.xlsm")

# Launch mode, set with environment variables (see README):
#   AICR_NATIVE=1  open in a desktop window (needs pywebview) instead of the browser
#   AICR_HOST      address to listen on; defaults to 127.0.0.1 so uploads are not exposed on the network
#   AICR_PORT      port to listen on; defaults to 8080
NATIVE = os.environ.get("AICR_NATIVE", "0").lower() in {"1", "true", "yes"}
HOST = os.environ.get("AICR_HOST", "127.0.0.1")
PORT = int(os.environ.get("AICR_PORT", "8080"))

##############################################################################################################################

@ui.page("/subscanner")
def subcontract_scanner():
    ui.add_head_html("<link rel='stylesheet' href='/static/style.css'/>")
    ui.html('<title>AI Contract Review</title>')
    ui.colors(primary='#E87722', secondary='#e86100')
    with ui.header(elevated=True).style('width: 100%; display: flex; justify-content: center;'):
        with ui.element():
            ui.label('Subcontractor Agreement Scanner').style('font-size: 22px; text-align: center')
            with ui.element().style('width: 100%; display: flex; justify-content: center;'):
                ui.label('Office of Sponsored Programs').style('font-size: 18px;')
    ui.upload(multiple=True, label="Upload Subcontractor Agreements", auto_upload=True, on_upload=handle_sub_upload).props(add="accept='.pdf'")

def handle_sub_upload(e):
    name = e.name
    binary = e.content.read()
    upload_filepath = write_binary_to_temp_file(name, binary)
    found = pdf_to_txt.scan_for_findings(upload_filepath)
    if found:
        ui.notify(name + " was flagged", type='negative')
    else:
        ui.notify(name + " was not flagged", type='positive')




##############################################################################################################################

@ui.page("/contractscanner")
def contract_scanner():
    ui.add_head_html("<link rel='stylesheet' href='/static/style.css'/>")
    ui.html('<title>AI Contract Review</title>')
    ui.colors(primary='#0b2341', secondary='#e86100')
    with ui.header(elevated=True).style('width: 100%; display: flex; justify-content: center;'):
        with ui.element():
            ui.label('AI Contract Scanner').style('font-size: 22px; text-align: center')
            with ui.element().style('width: 100%; display: flex; justify-content: center;'):
                ui.label('Office of Sponsored Programs').style('font-size: 18px;')
    ui.upload(multiple=True, label="Upload Contracts", auto_upload=True, on_upload=handle_contract_upload).props(add="accept='.docx,.doc,.pdf'")


async def handle_contract_upload(e):
    name = e.name
    binary = e.content.read()
    upload_filepath = write_binary_to_temp_file(name, binary)
    downloads_path = os.path.join(os.environ['USERPROFILE'], 'Downloads')
    output_filepath = os.path.join(downloads_path, f"{getFilenameStringNoExtension(name)}_scanned.docx")
    ui.notify("Scanning file...")
    await run.cpu_bound(scan_file, upload_filepath, output_filepath)
    os.remove(upload_filepath)
    ui.notify("Downloading scan")
    ui.download(output_filepath)

def scan_file(filepath, output_filepath):
    # clean docx and annotate it
    convert_to_txt(filepath)
    _flag_problem_language(TNC_MATRIX_PATH)
    back_to_docx = 'flagged_contract_to_txt.txt'
    file_to_highlight = 'flagged_contract_to_docx.docx'
    txt_to_docx(back_to_docx, file_to_highlight)

    annotate_contract(FAR_CLAUSE_MATRIX_PATH, file_to_highlight, output_filepath)

def getFilenameStringNoExtension(filename):
    temp_list = filename.split(".")
    if (len(temp_list) == 1):
        return temp_list[0]
    else:
        temp_list.pop()
        return '.'.join(temp_list)

def write_binary_to_temp_file(name, binary):
    filepath = os.path.join(TEMP_DIR, name)
    with open(file=filepath, mode="wb") as file:
        file.write(binary)
    return filepath

##########################################################################################

@ui.page("/")
def index():
    ui.add_head_html("<link rel='stylesheet' href='/static/style.css'/>")
    ui.label("Choose the feature you would like to access:").style("font-size: 30px;")
    with ui.element().style("""
                            display: flex;
                            width: 100vw;
                            justify-content: center;
                            height: calc(100vh - 50px);
                            align-items: center;
                            position: absolute;
                            top: 50px;
                            left: 0;"""):
        ui.link("AI Contract Scanner", contract_scanner).classes("page-button").style("background: #0b2341; margin-right: 50px;")
        ui.link("Subcontractor Agreement Scanner", subcontract_scanner).classes("page-button").style("background: #E87722;")

if __name__ in {"__main__", "__mp_main__"}:
    app.add_static_files("/static", STATIC_DIR)
    app.add_static_files("/temp", TEMP_DIR)
    if NATIVE:
        ui.run(native=True, reload=False, port=PORT)
    else:
        ui.run(reload=False, host=HOST, port=PORT)