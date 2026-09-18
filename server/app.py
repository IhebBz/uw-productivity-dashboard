"""A local stand-in for how this pipeline will eventually run inside MosAIc
Chat: the data is re-read on a timer in the background, and the dashboard
works out the figures for whatever filters are picked.

Run with:
    python run_server.py

Then open http://localhost:8000 in a browser. The page refreshes itself
every few minutes and always shows the most recent background read -
nobody has to click a button to "get" new numbers, same as the production
model. Filters live in the page address, so a filtered view can be
bookmarked or shared.
"""
import logging
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response

from data_sources.excel_source import ExcelSource
from pipeline.build_dashboard_data import prepare, compute_with_comparison
from pipeline.serialize import to_json_safe
from pipeline.logging_setup import setup_logging
from scope.options import filter_options, fixed_choices
from server.dashboard import render_dashboard
from server.exports import figures_csv, underwriters_csv
from server.filters import parse_filters, drop_stranded_selections

setup_logging()
logger = logging.getLogger(__name__)

REFRESH_SECONDS = 300  # stand-in for "daily" - short enough to see it work locally

# Filtered results kept in memory, keyed by page address. Cleared on every
# data refresh, so an old figure can never outlive the data it came from.
MAX_CACHED_VIEWS = 64

app = FastAPI()
_latest = {"data": None, "error": None, "last_run": None, "views": {}}
_lock = threading.Lock()


def _refresh_loop():
    """Re-read and clean the data every REFRESH_SECONDS, forever, in the background."""
    source = ExcelSource(folder="data")
    while True:
        try:
            data = prepare(source)
            with _lock:
                _latest.update(data=data, error=None, views={})
        except Exception as exc:
            logger.exception("Background refresh failed")
            with _lock:
                _latest["error"] = str(exc)
        _latest["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(REFRESH_SECONDS)


@app.on_event("startup")
def start_background_refresh():
    """Kick off the background refresh loop when the server starts."""
    thread = threading.Thread(target=_refresh_loop, daemon=True)
    thread.start()


def _view_for(params):
    """Work out (or reuse) everything the page needs for one set of filters."""
    with _lock:
        data, views = _latest["data"], _latest["views"]
    if data is None:
        return None

    key = str(params)
    if key in views:
        return views[key]

    years = sorted({int(y) for y in data.dsr["inception_date"].dt.year.dropna().unique()
                    if y <= data.as_at.year})
    choices = {
        "years": years,
        "business_types": fixed_choices(data.dsr, data.rbs, "business_type"),
        "placements": fixed_choices(data.dsr, data.rbs, "placement"),
    }
    state = parse_filters(params, data.as_at, years,
                          choices["business_types"], choices["placements"])
    state, options = drop_stranded_selections(
        state, lambda s: filter_options(data.dsr, data.rbs, s.to_scope(data.as_at)))

    view = {
        "filters": state,
        "options": options,
        "choices": choices,
        "as_at": data.as_at,
        "underwriter_names": data.underwriter_names,
        "possible_duplicates": data.possible_duplicates or {},
        "result": compute_with_comparison(data, state.to_scope(data.as_at)),
    }
    with _lock:
        if len(views) >= MAX_CACHED_VIEWS:
            views.pop(next(iter(views)))
        views[key] = view
    return view


@app.get("/metrics")
def get_metrics(request: Request):
    """The figures for the filters in the address, as JSON (same parameters as the page)."""
    view = _view_for(request.query_params)
    return {
        "last_run": _latest["last_run"],
        "error": _latest["error"],
        "data": to_json_safe(view["result"]) if view else None,
    }


def _csv(view, build, name):
    """A CSV download named after the data date, e.g. uw-figures-2026-09-15.csv."""
    if view is None:
        return Response("The data is still loading - try again in a moment.", status_code=503)
    filename = f"uw-{name}-{view['as_at']:%Y-%m-%d}.csv"
    # utf-8-sig so Excel reads the dashes and accents correctly.
    return Response(build(view).encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/export/figures.csv")
def export_figures(request: Request):
    """Every figure on the page, for the filters in the address, with its source columns."""
    return _csv(_view_for(request.query_params), figures_csv, "figures")


@app.get("/export/underwriters.csv")
def export_underwriters(request: Request):
    """The underwriter table, for the filters in the address."""
    return _csv(_view_for(request.query_params), underwriters_csv, "underwriters")


@app.get("/", response_class=HTMLResponse)
def dashboard_preview(request: Request):
    """The actual dashboard - server-rendered for the filters in the address."""
    try:
        view = _view_for(request.query_params)
        error = _latest["error"]
    except Exception as exc:
        logger.exception("Could not build the dashboard for %s", request.query_params)
        view, error = None, str(exc)
    return render_dashboard(view, _latest["last_run"], error)
