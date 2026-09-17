"""A local stand-in for how this pipeline will eventually run inside MosAIc
Chat: refreshed on a timer in the background, with the dashboard just
reading whatever the latest result was, rather than triggering a run itself.

Run with:
    python run_server.py

Then open http://localhost:8000 in a browser. The page refreshes itself
every few seconds and always shows the most recent background run - nobody
has to click a button to "get" new numbers, same as the production model.
"""
import logging
import threading
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from data_sources.excel_source import ExcelSource
from scope.filter import Scope
from pipeline.build_dashboard_data import build
from pipeline.serialize import to_json_safe
from pipeline.logging_setup import setup_logging
from server.dashboard import render_dashboard

setup_logging()
logger = logging.getLogger(__name__)

REFRESH_SECONDS = 300  # stand-in for "daily" - short enough to see it work locally

app = FastAPI()
_latest_result = {"data": None, "error": None, "last_run": None}


def _refresh_loop():
    """Re-run the pipeline every REFRESH_SECONDS, forever, in the background."""
    source = ExcelSource(folder="data")
    scope = Scope()
    while True:
        try:
            _latest_result["data"] = to_json_safe(build(source, scope))
            _latest_result["error"] = None
        except Exception as exc:
            logger.exception("Background refresh failed")
            _latest_result["error"] = str(exc)
        _latest_result["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(REFRESH_SECONDS)


@app.on_event("startup")
def start_background_refresh():
    """Kick off the background refresh loop when the server starts."""
    thread = threading.Thread(target=_refresh_loop, daemon=True)
    thread.start()


@app.get("/metrics")
def get_metrics():
    """Return the most recent computed result as JSON."""
    return _latest_result


@app.get("/", response_class=HTMLResponse)
def dashboard_preview():
    """The actual dashboard - server-rendered from the latest background run."""
    return render_dashboard(
        _latest_result["data"], _latest_result["last_run"], _latest_result["error"])