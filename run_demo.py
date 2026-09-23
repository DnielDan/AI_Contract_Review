"""Browser-based launcher for demoing the AI Contract Scanner.

`main.py` calls `ui.run(native=True, ...)` which needs a desktop webview window.
This launcher reuses main.py's page definitions but serves them in the browser
at http://localhost:8080 instead. Run:  python run_demo.py
"""
import main  # registers the "/" page and upload handler
from nicegui import ui, app

if __name__ in {"__main__", "__mp_main__"}:
    app.add_static_files("/static", "static")
    app.add_static_files("/temp", "temp")
    ui.run(native=False, host="127.0.0.1", port=8080, show=False, reload=False)
