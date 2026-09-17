"""Starts the local server the same way run_pipeline_once.py runs the
pipeline: as a plain `python run_server.py`, nothing else.

Some locked-down Windows setups block the standalone uvicorn.exe launcher
script that pip installs in venv/Scripts (an org policy on executables, not
a problem with this project). Calling uvicorn programmatically from inside
a normal Python script sidesteps that entirely - the only thing being run
is python.exe itself.

reload=False on purpose: --reload watches every file in the project (not
just .py files) and restarts the whole app, background thread included,
the moment anything changes. On a slow first run that can restart the app
before it ever finishes, which looks exactly like "stuck on null forever."
Only turn reload on while actively editing the code, never while just
running it.

Usage:
    python run_server.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=False)