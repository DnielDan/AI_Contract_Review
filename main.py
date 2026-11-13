from nicegui import ui, run, app
import glob
import logging
import os
import re
import shutil
import tempfile
from contract_to_txt import UnsupportedFileError, convert_to_txt, txt_to_docx
from flag_FAR_clauses import annotate_contract
from flag_problem_language import DEFAULT_SIMILARITY_THRESHOLD, _flag_problem_language, load_tnc_matrix
from flag_FAR_clauses import read_far_matrix
from llm_providers import LLMConfigError, provider_name
from llm_review import llm_flag_problem_language
from dotenv import load_dotenv
from nltk import data as nltk
import pdf_to_txt

# Resolve paths from this file's folder so the app runs on any OS and from any working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPLEMENTARY_DIR = os.path.join(BASE_DIR, "supplementary_files")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
WORK_DIR_PREFIX = "scan_"  # each upload is processed in its own temp/scan_<random> directory

# Append the custom path to the NLTK data path
nltk.path.append(os.path.join(SUPPLEMENTARY_DIR, "nltk_data"))

# Settings and API keys are read from a .env file in the repository folder (see .env.example),
# or from environment variables, which take precedence
load_dotenv(os.path.join(BASE_DIR, ".env"))

# A problem with the settings in .env, reported at startup instead of during a scan
class ConfigError(RuntimeError):
    pass

# Returns a path from .env, resolved from the repository folder, or the bundled default
def _configured_path(variable, default):
    value = os.environ.get(variable, "").strip()
    return os.path.join(BASE_DIR, value) if value else default

def _configured_threshold():
    value = os.environ.get("AICR_SIMILARITY_THRESHOLD", "").strip()
    if not value:
        return DEFAULT_SIMILARITY_THRESHOLD
    try:
        threshold = float(value)
    except ValueError:
        raise ConfigError(f"AICR_SIMILARITY_THRESHOLD must be a number between 0 and 1, not '{value}'") from None
    if not 0 < threshold < 1:
        raise ConfigError(f"AICR_SIMILARITY_THRESHOLD must be between 0 and 1, not {threshold}")
    return threshold

# Matrices and matcher threshold (US-7); the bundled matrices are the defaults
FAR_CLAUSE_MATRIX_PATH = _configured_path("AICR_FAR_MATRIX", os.path.join(SUPPLEMENTARY_DIR, "2023-03-20_FAR Matrix.xls"))
TNC_MATRIX_PATH = _configured_path("AICR_TNC_MATRIX", os.path.join(SUPPLEMENTARY_DIR, "Contract Ts&Cs Matrix.xlsm"))
SIMILARITY_THRESHOLD = _configured_threshold()

# Checks that both matrices exist and have the columns the scanner reads, so a wrong path or a
# revised layout is reported when the app starts rather than as a failed scan
def check_matrices(far_path=None, tnc_path=None):
    far_path = far_path or FAR_CLAUSE_MATRIX_PATH
    tnc_path = tnc_path or TNC_MATRIX_PATH
    for label, path in (("FAR Matrix (AICR_FAR_MATRIX)", far_path), ("Ts&Cs Matrix (AICR_TNC_MATRIX)", tnc_path)):
        if not os.path.isfile(path):
            raise ConfigError(f"The {label} was not found at {path}")
    try:
        far = read_far_matrix(far_path)
    except KeyError as error:
        raise ConfigError(f"The FAR Matrix at {far_path} is missing the expected column {error}") from None
    if far.empty:
        raise ConfigError(f"The FAR Matrix at {far_path} has no clause rows with an acceptance status")
    tnc = load_tnc_matrix(tnc_path)
    if not any(sheet.get("Common Problems") for sheet in tnc.values()):
        raise ConfigError(f"The Ts&Cs Matrix at {tnc_path} has no sheets with a 'Common Problems' section")

# Launch mode, set with environment variables (see README):
#   AICR_NATIVE=1  open in a desktop window (needs pywebview) instead of the browser
#   AICR_HOST      address to listen on; defaults to 127.0.0.1 so uploads are not exposed on the network
#   AICR_PORT      port to listen on; defaults to 8080
NATIVE = os.environ.get("AICR_NATIVE", "0").lower() in {"1", "true", "yes"}
HOST = os.environ.get("AICR_HOST", "127.0.0.1")
PORT = int(os.environ.get("AICR_PORT", "8080"))

logger = logging.getLogger("aicr")

# Shown when a file fails for a reason we did not anticipate; the details go to the log
GENERIC_FAILURE = "The file may be damaged, password-protected, or in an unexpected format. Details were logged."

# Returns the message to show the user when a file could not be processed, and logs the error
def failure_message(name, error):
    if isinstance(error, UnsupportedFileError):
        logger.warning("Could not process %s: %s", name, error)
        return f"Could not process {name}. {error}"
    logger.exception("Could not process %s", name, exc_info=error)
    return f"Could not process {name}. {GENERIC_FAILURE}"

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
    work_dir = new_work_dir()
    try:
        upload_filepath = write_binary_to_temp_file(name, e.content.read(), work_dir)
        found = pdf_to_txt.scan_for_findings(upload_filepath)
    except Exception as error:
        ui.notify(failure_message(name, error), type='warning', multi_line=True, timeout=0, close_button=True)
        return
    finally:
        remove_work_dir(work_dir)
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
    work_dir = new_work_dir()
    try:
        upload_filepath = write_binary_to_temp_file(name, e.content.read(), work_dir)
        output_name = f"{getFilenameStringNoExtension(safe_filename(name))}_scanned.docx"
        output_filepath = os.path.join(work_dir, output_name)
        ui.notify("Scanning file...")
        try:
            flagged_count, ai_notice = await run.cpu_bound(scan_contract, upload_filepath, output_filepath)
        except Exception as error:
            ui.notify(failure_message(name, error), type='warning', multi_line=True, timeout=0, close_button=True)
            return
        with open(output_filepath, 'rb') as file:
            scanned_document = file.read()
    finally:
        # Nothing from this upload stays on the server, whether the scan succeeded or failed
        remove_work_dir(work_dir)
    if ai_notice:
        ui.notify(f"{name}: {ai_notice}", type='warning', multi_line=True, timeout=0, close_button=True)
    if flagged_count:
        ui.notify(f"{name}: {flagged_count} passage(s) of potential problem language flagged. Downloading scan.", type='negative')
    else:
        ui.notify(f"{name}: no problem language found. Downloading scan (FAR clauses are still highlighted).", type='positive')
    # Sent as bytes over this user's own connection, so no URL is created that someone else could open
    ui.download(scanned_document, output_name)

# Scans a contract and writes the annotated copy; returns the number of passages flagged.
def scan_file(filepath, output_filepath):
    return scan_contract(filepath, output_filepath)[0]

# Scans a contract and writes the annotated copy. Returns the number of passages flagged and a
# notice for the reviewer when the AI review was configured but could not run (otherwise None).
# Intermediate files go in the same directory as output_filepath, so concurrent scans never share files.
def scan_contract(filepath, output_filepath):
    work_dir = os.path.dirname(os.path.abspath(output_filepath))
    contract_txt = os.path.join(work_dir, 'contract_to_txt.txt')
    flagged_txt = os.path.join(work_dir, 'flagged_contract_to_txt.txt')
    file_to_highlight = os.path.join(work_dir, 'flagged_contract_to_docx.docx')

    # clean docx and annotate it
    convert_to_txt(filepath, contract_txt)
    flagged_count, ai_notice = flag_problem_language(contract_txt, flagged_txt)
    txt_to_docx(flagged_txt, file_to_highlight)

    annotate_contract(FAR_CLAUSE_MATRIX_PATH, file_to_highlight, output_filepath)
    return flagged_count, ai_notice

# Flags problem language with the LLM named in .env (US-12), or with the TF-IDF matcher when no LLM
# is configured. If the LLM call fails, the scan falls back to the matcher instead of failing.
def flag_problem_language(contract_txt, flagged_txt):
    provider = provider_name()
    if provider:
        try:
            return llm_flag_problem_language(TNC_MATRIX_PATH, contract_txt, flagged_txt), None
        except LLMConfigError as error:
            logger.warning("AI review not run: %s", error)
            reason = str(error)
        except Exception:
            logger.exception("AI review with %s failed; using the basic matcher", provider)
            reason = f"The AI service ({provider}) did not return a usable result. Details were logged."
        ai_notice = f"AI review unavailable, so the basic matcher was used. {reason}"
    else:
        ai_notice = None
    return _flag_problem_language(TNC_MATRIX_PATH, contract_txt, flagged_txt, SIMILARITY_THRESHOLD), ai_notice

def getFilenameStringNoExtension(filename):
    temp_list = filename.split(".")
    if (len(temp_list) == 1):
        return temp_list[0]
    else:
        temp_list.pop()
        return '.'.join(temp_list)

# Returns a version of an uploaded filename that is safe to write: any folder part is dropped
# (so "../../main.py" cannot escape the working directory) and unusual characters are replaced
def safe_filename(name):
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._ ()'-]", "_", base).strip(" .")
    stem, extension = os.path.splitext(base)
    return (stem[:100] + extension[:10]) or "upload"

# Creates a private working directory for one upload, inside TEMP_DIR
def new_work_dir():
    os.makedirs(TEMP_DIR, exist_ok=True)
    return tempfile.mkdtemp(prefix=WORK_DIR_PREFIX, dir=TEMP_DIR)

def remove_work_dir(work_dir):
    try:
        shutil.rmtree(work_dir)
    except OSError:
        logger.warning("Could not delete working directory %s; it will be removed on the next restart", work_dir, exc_info=True)

# Removes working directories left behind if the app stopped in the middle of a scan
def remove_stale_work_dirs():
    for work_dir in glob.glob(os.path.join(TEMP_DIR, WORK_DIR_PREFIX + "*")):
        remove_work_dir(work_dir)

def write_binary_to_temp_file(name, binary, work_dir):
    filepath = os.path.join(work_dir, safe_filename(name))
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
    # temp/ is deliberately not served: it holds uploaded contracts while they are scanned.
    # on_startup runs once in the server process only, never in the scan worker processes,
    # so it cannot delete the working directory of a scan in progress.
    app.on_startup(remove_stale_work_dirs)
    if __name__ == "__main__":
        try:
            check_matrices()
        except ConfigError as error:
            raise SystemExit(f"Configuration error: {error}")
    if NATIVE:
        ui.run(native=True, reload=False, port=PORT)
    else:
        ui.run(reload=False, host=HOST, port=PORT)