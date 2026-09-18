"""Checks the month-by-month trends, the charts, the downloads, possible
duplicate names, and that the tabbed page has every panel.
"""
import csv
import io

import pytest
from starlette.datastructures import QueryParams

import server.app as app
from ingest.underwriter_names import possible_duplicates
from metrics.trends import monthly_trends
from pipeline.build_dashboard_data import compute
from scope.filter import Scope
from server.charts import nice_ticks, sparkline, _segments
from server.exports import figures_csv, underwriters_csv
from tests.sample_data import prepared


def test_each_month_matches_the_page_figure_for_that_month_alone():
    """A monthly value must equal the whole-page figure with only that month picked."""
    data = prepared()
    scope = Scope(year=2026, months=list(range(1, 9)))
    trends = monthly_trends(data.dsr, data.rbs, scope, data.as_at)
    labels = [m["label"] for m in trends["months"]]
    for year, month, label in ((2026, 2, "Feb 2026"), (2026, 4, "Apr 2026"), (2025, 2, "Feb 2025")):
        i = labels.index(label)
        one = compute(data, Scope(year=year, months=[month]))
        assert trends["series"]["submissions"][i] == one["funnel"]["submissions"]
        assert (trends["series"]["binds"][i] or 0) == one["funnel"]["binds"]
        assert (trends["series"]["bound_premium"][i] or 0) == pytest.approx(one["premium"]["bound_premium"])
        assert trends["series"]["uw_margin_pct"][i] == one["quality"]["uw_margin_pct"]


def test_trend_window_ends_at_last_complete_month_and_marks_the_period():
    """Full year 2026 as at 15 Sep: the window stops at Aug 2026; Jan-Aug are marked selected."""
    data = prepared()
    trends = monthly_trends(data.dsr, data.rbs, Scope(year=2026, months=list(range(1, 13))), data.as_at)
    assert trends["months"][-1]["label"] == "Aug 2026"
    assert len(trends["months"]) == 24
    assert [m["label"] for m in trends["months"] if m["selected"]][0] == "Jan 2026"


def test_submission_basis_trends_leave_out_rbs_series():
    data = prepared()
    trends = monthly_trends(data.dsr, data.rbs, Scope(year=2026, months=[1, 2], date_basis="submission"),
                            data.as_at)
    assert "submissions" in trends["series"] and "binds" not in trends["series"]


def test_nice_ticks():
    assert nice_ticks(0.41, 0.49, include_zero=False) == [0.4, 0.425, 0.45, 0.475, 0.5]
    assert nice_ticks(3e6, 1.1e8)[0] == 0


def test_line_breaks_at_missing_months_and_changes_colour_at_the_period():
    points = [(0, 1, False), (1, 2, False), (2, None, False), (3, 3, False), (4, 4, True)]
    runs = _segments(points)
    assert runs == [(False, [(0, 1), (1, 2)]), (False, [(3, 3)]), (True, [(3, 3), (4, 4)])]
    assert sparkline([None, 5], [False, True], "x") == ""  # one real point: nothing to draw


def test_possible_duplicates_flags_likely_pairs_only():
    names = {"stedman rob": "Stedman, Rob", "stedman robert": "Stedman, Robert",
             "hirst justin": "Hirst, Justin", "hurst justin": "Hurst, Justin",
             "anderson marc": "Anderson, Marc", "anderson mason": "Anderson, Mason"}
    found = possible_duplicates(names)
    assert found["stedman rob"] == ["Stedman, Robert"]
    assert found["hirst justin"] == ["Hurst, Justin"]
    assert "anderson marc" not in found  # a different first name is a different person


def _view(query=""):
    app._latest.update(data=prepared(), error=None, views={}, last_run="now")
    return app._view_for(QueryParams(query))


def test_downloads_carry_filters_and_lineage():
    view = _view("period=q1&lob=Cyber")
    figures = list(csv.reader(io.StringIO(figures_csv(view))))
    assert ["Period", "Jan–Mar 2026"] in figures and ["Line of business", "Cyber"] in figures
    header = next(r for r in figures if r and r[0] == "Section")
    submissions = next(r for r in figures if len(r) > 1 and r[1] == "Submissions")
    assert submissions[header.index("Original columns")] == "DSR: Policy Reference"
    table = list(csv.reader(io.StringIO(underwriters_csv(view))))
    assert any(r and r[0] == "Smith, Jane" for r in table)


def test_page_has_every_tab_and_the_new_pieces():
    html = app.render_dashboard(_view(), "now", None)
    for tab in ("overview", "funnel", "quality", "book", "productivity", "underwriters", "trends"):
        assert f'data-panel="{tab}"' in html
    assert 'class="trend-svg"' in html and "Show as table" in html
    assert "data-copy-link" in html and "/export/figures.csv" in html
    assert 'class="uw-search"' in html
    assert "<title>UW Productivity · Jan–Aug 2026</title>" in html
    empty = app.render_dashboard(_view("period=q4&year=2025"), "now", None)
    assert "Nothing matches these filters" in empty
