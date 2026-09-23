"""Browser launcher for the multi-page GUI (Blue Team, Cycle 3).

This branch's main.py already runs in the browser, but on the default port 8080
(which the main-branch demo uses). This serves the same pages on port 8081.
Run:  python run_demo.py   ->   http://127.0.0.1:8081
"""
import main  # registers "/", "/contractscanner", "/subscanner"
from nicegui import ui, app

if __name__ in {"__main__", "__mp_main__"}:
    app.add_static_files("/static", "static")
    app.add_static_files("/temp", "temp")
    ui.run(native=False, host="127.0.0.1", port=8081, show=False, reload=False)
