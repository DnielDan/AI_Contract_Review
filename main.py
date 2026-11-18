import glob
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from contract_to_txt import UnsupportedFileError, convert_to_txt, txt_to_docx
from flag_FAR_clauses import annotate_contract
from flag_problem_language import load_tnc_matrix, write_flagged_text
from flag_FAR_clauses import read_far_matrix
from llm_providers import LLMConfigError, configuration_problem, model_name, provider_name
from llm_review import _issue_details, review_contract
from scan_results import build_results, far_matches
from dotenv import load_dotenv
from nltk import data as nltk
import pdf_to_txt

# Resolve paths from this file's folder so the app runs on any OS and from any working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPLEMENTARY_DIR = os.path.join(BASE_DIR, "supplementary_files")
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")  # the workbench, built with npm run build
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

# Matrices (US-7); the bundled matrices are the defaults
FAR_CLAUSE_MATRIX_PATH = _configured_path("AICR_FAR_MATRIX", os.path.join(SUPPLEMENTARY_DIR, "2023-03-20_FAR Matrix.xls"))
TNC_MATRIX_PATH = _configured_path("AICR_TNC_MATRIX", os.path.join(SUPPLEMENTARY_DIR, "Contract Ts&Cs Matrix.xlsm"))

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

# Where the server listens, set with environment variables (see README):
#   AICR_HOST      address to listen on; defaults to 127.0.0.1 so uploads are not exposed on the network
#   AICR_PORT      port to listen on; defaults to 8080
HOST = os.environ.get("AICR_HOST", "127.0.0.1")
PORT = int(os.environ.get("AICR_PORT", "8080"))

logger = logging.getLogger("aicr")

# Shown when a file fails for a reason we did not anticipate; the details go to the log
GENERIC_FAILURE = "The file may be damaged, password-protected, or in an unexpected format. Details were logged."

# Shown to reviewers while no approved AI provider and key are set up (see docs/AI_REVIEW.md)
AI_NOT_SET_UP = ("AI review is not set up on this server yet, so contracts cannot be scanned. "
                 "Ask IT to finish the setup in docs/AI_REVIEW.md.")

# The AI review could not produce flags; the message is shown to the reviewer as is, the cause is logged
class AIReviewError(RuntimeError):
    pass

# Returns the message to show the user when a file could not be processed, and logs the error
def failure_message(name, error):
    if isinstance(error, UnsupportedFileError):
        logger.warning("Could not process %s: %s", name, error)
        return f"Could not process {name}. {error}"
    if isinstance(error, AIReviewError):
        logger.error("AI review of %s failed", name, exc_info=error)
        return f"Could not review {name}. {error}"
    logger.exception("Could not process %s", name, exc_info=error)
    return f"Could not process {name}. {GENERIC_FAILURE}"

# Returns the reviewer-facing reason the AI review cannot run, or None when a provider and its key are set
def ai_setup_problem():
    problem = configuration_problem()
    return f"{AI_NOT_SET_UP} ({problem})" if problem else None

# Says in the scanned document which AI provider and model flagged the language
def review_label():
    return f"AI review ({provider_name()}, {model_name()})"

# Flags problem language with the AI review (US-12). Returns a list of (flagged text, details), where the
# details come from the Ts&Cs Matrix row the model named plus the model's own explanation. There is no
# fallback to the TF-IDF matcher: OSP uses the tool only with an approved AI provider, so an AI failure
# fails the scan with the reason. (The matcher is kept in evaluation/ as the accuracy baseline.)
def ai_flags(contract_text):
    tnc_dictionary = load_tnc_matrix(TNC_MATRIX_PATH)
    try:
        issues = review_contract(contract_text, tnc_dictionary)
    except LLMConfigError as error:
        raise AIReviewError(f"{AI_NOT_SET_UP} ({error})") from error
    except Exception as error:
        raise AIReviewError(f"The AI service ({provider_name()}) did not return a usable result. "
                            "Try again later; details were logged.") from error
    return [(issue["quote"], _issue_details(issue, tnc_dictionary)) for issue in issues]

# Scans a contract, writes the annotated copy, and returns the results the workbench shows
# (scan_results.build_results). on_stage is called with the name of each step before it starts,
# so the caller can show progress, or stop the scan by raising an exception.
# Intermediate files go in the same directory as output_filepath, so concurrent scans never share files.
def scan_contract_with_results(filepath, output_filepath, on_stage=lambda stage: None):
    work_dir = os.path.dirname(os.path.abspath(output_filepath))
    contract_txt = os.path.join(work_dir, 'contract_to_txt.txt')
    flagged_txt = os.path.join(work_dir, 'flagged_contract_to_txt.txt')
    file_to_highlight = os.path.join(work_dir, 'flagged_contract_to_docx.docx')

    on_stage("extract")
    convert_to_txt(filepath, contract_txt)
    with open(contract_txt, 'r', encoding='utf-8') as file:
        contract_text = file.read()
    on_stage("review")
    flags = ai_flags(contract_text)
    on_stage("annotate")
    write_flagged_text(contract_text, flags, flagged_txt)
    txt_to_docx(flagged_txt, file_to_highlight)
    label = review_label()
    annotate_contract(FAR_CLAUSE_MATRIX_PATH, file_to_highlight, output_filepath, label)
    far_clauses, far_rows = far_matches(contract_text, FAR_CLAUSE_MATRIX_PATH)
    return build_results(contract_text, flags, far_clauses, far_rows, label)

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
# Scans (US-19). Each upload is scanned in its own thread; the pipeline is ordinary CPU work, and a
# thread per scan is enough for the handful of OSP reviewers using the app at once.

ACCEPTED_EXTENSIONS = (".docx", ".doc", ".pdf")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # the limit the workbench tells reviewers about

class ScanCancelled(Exception):
    pass

# One uploaded contract and its scan. Stages: queued, extract, review, annotate, then done, failed or
# cancelled. Kept in memory only; the upload and the intermediate files leave the disk when the scan ends.
@dataclass
class Scan:
    id: str
    filename: str  # as uploaded; only shown to the reviewer, never used as a path
    docx_name: str  # the annotated copy's download name
    stage: str = "queued"
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    error: str | None = None
    flagged_count: int = 0
    results: dict | None = None
    docx_bytes: bytes | None = None
    cancelled: bool = False

    def elapsed_seconds(self):
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return round(end - self.started_at, 1)

# Every scan of this server session, by id; a restart forgets them
_scans = {}
_scans_lock = threading.Lock()

# Runs one scan in its own thread. Only the annotated copy is kept, in memory, for download.
def run_scan(scan, upload):
    try:
        results, docx_bytes = _scan_in_work_dir(scan, upload)
        if scan.cancelled:
            raise ScanCancelled
    except ScanCancelled:
        _end(scan, "cancelled")
    except Exception as error:
        scan.error = failure_message(scan.filename, error)
        _end(scan, "failed")
    else:
        scan.results, scan.docx_bytes = results, docx_bytes
        scan.flagged_count = len(results["flags"])
        _end(scan, "done")

# Scans the upload in a working directory of its own, which is removed before the scan is marked as ended,
# whatever the outcome, so nothing from the upload is on disk by the time the reviewer sees the result
def _scan_in_work_dir(scan, upload):
    work_dir = new_work_dir()
    try:
        upload_filepath = write_binary_to_temp_file(scan.filename, upload, work_dir)
        output_filepath = os.path.join(work_dir, scan.docx_name)
        results = scan_contract_with_results(upload_filepath, output_filepath, lambda stage: _set_stage(scan, stage))
        with open(output_filepath, 'rb') as file:
            return results, file.read()
    finally:
        remove_work_dir(work_dir)

# Cancelling is checked between steps: a step in progress finishes, then the scan stops with no results
def _set_stage(scan, stage):
    if scan.cancelled:
        raise ScanCancelled
    scan.stage = stage

# The stage is written last, so a reviewer who sees "done" can fetch the results
def _end(scan, stage):
    scan.finished_at = time.monotonic()
    scan.stage = stage

##########################################################################################
# API used by the workbench (frontend/). Errors are returned as {"detail": message}.
# There is no login yet (US-22, US-8): anyone who can reach the server can use it, so it listens
# on 127.0.0.1 unless AICR_HOST says otherwise.

app = FastAPI(title="AU Contract Review")

# Returns the uploaded bytes, or rejects the upload before anything is written to disk
def _read_upload(file, extensions, wrong_type_message):
    if os.path.splitext(file.filename or "")[1].lower() not in extensions:
        raise HTTPException(400, wrong_type_message)
    upload = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not upload:
        raise HTTPException(400, "The file is empty.")
    if len(upload) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 25 MB.")
    return upload

NO_SUCH_SCAN = "No scan with this id. It may have been deleted, or the server restarted."

def _get_scan(scan_id):
    with _scans_lock:
        scan = _scans.get(scan_id)
    if scan is None:
        raise HTTPException(404, NO_SUCH_SCAN)
    return scan

def _get_finished_scan(scan_id):
    scan = _get_scan(scan_id)
    if scan.stage != "done":
        raise HTTPException(409, "The scan has not finished.")
    return scan

@app.post("/api/scans", status_code=202)
def start_scan(file: UploadFile):
    # Without an AI provider there is nothing to scan with, so the upload is turned down before it is read
    problem = ai_setup_problem()
    if problem:
        raise HTTPException(503, problem)
    upload = _read_upload(file, ACCEPTED_EXTENSIONS, "Only .docx, .doc, or .pdf files can be scanned.")
    scan = Scan(id=secrets.token_urlsafe(16), filename=file.filename,
                docx_name=f"{getFilenameStringNoExtension(safe_filename(file.filename))}_scanned.docx")
    with _scans_lock:
        _scans[scan.id] = scan
    # A daemon thread does not hold up stopping the server; a working directory it leaves is removed on the next start
    threading.Thread(target=run_scan, args=(scan, upload), daemon=True).start()
    return {"id": scan.id, "filename": scan.filename, "stage": scan.stage}

@app.get("/api/scans/{scan_id}")
def scan_status(scan_id: str):
    scan = _get_scan(scan_id)
    return {
        "id": scan.id,
        "filename": scan.filename,
        "stage": scan.stage,
        "elapsed_seconds": scan.elapsed_seconds(),
        "flagged_count": scan.flagged_count,
        "error": scan.error,
    }

@app.get("/api/scans/{scan_id}/results")
def get_results(scan_id: str):
    return _get_finished_scan(scan_id).results

@app.get("/api/scans/{scan_id}/download")
def download_scan(scan_id: str):
    scan = _get_finished_scan(scan_id)
    # safe_filename leaves only plain ASCII characters and no quotes, so the name can go in the header as is
    return Response(scan.docx_bytes,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{scan.docx_name}"'})

# Forgets a scan; a scan still running stops at its next step
@app.delete("/api/scans/{scan_id}", status_code=204)
def delete_scan(scan_id: str):
    with _scans_lock:
        scan = _scans.pop(scan_id, None)
    if scan is None:
        raise HTTPException(404, NO_SUCH_SCAN)
    scan.cancelled = True
    return Response(status_code=204)

# Whether the AI review is set up, so the workbench can say so before anyone uploads a contract
@app.get("/api/config")
def get_config():
    problem = ai_setup_problem()
    provider = provider_name()
    return {"ai_ready": problem is None, "problem": problem,
            "provider": provider, "model": model_name() if provider else None}

# Checks a subcontractor's audit report for findings (US-3b). Kept for the subcontract scanner,
# which has no screen in the workbench yet.
@app.post("/api/subcontract-scans")
def scan_subcontract(file: UploadFile):
    upload = _read_upload(file, (".pdf",), "Only .pdf files can be scanned.")
    work_dir = new_work_dir()
    try:
        return {"flagged": pdf_to_txt.scan_for_findings(write_binary_to_temp_file(file.filename, upload, work_dir))}
    except Exception as error:
        raise HTTPException(422, failure_message(file.filename, error)) from None
    finally:
        remove_work_dir(work_dir)

# Serves the built workbench at /. Any other path that is not a file gets index.html, so a reload always
# lands in the app; unknown /api/ paths still get a 404. temp/ is deliberately not served.
class Workbench(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404 or scope["path"].startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)

if os.path.isdir(FRONTEND_DIST):
    app.mount("/", Workbench(directory=FRONTEND_DIST, html=True), name="workbench")
else:
    @app.get("/", response_class=PlainTextResponse)
    def workbench_not_built():
        return "The workbench has not been built. Run npm ci and then npm run build in frontend/, then restart the server."

if __name__ == "__main__":
    try:
        check_matrices()
    except ConfigError as error:
        raise SystemExit(f"Configuration error: {error}")
    # The server still starts, so reviewers see why scans are turned down instead of a dead page
    if configuration_problem():
        logger.warning("AI review is not set up: %s. Uploads will be turned down until it is (docs/AI_REVIEW.md).",
                       configuration_problem())
    remove_stale_work_dirs()
    uvicorn.run(app, host=HOST, port=PORT)
