"""Checks the fixes for the problems the September 2026 audit found
(metrics workbook, tab 9, questions 22-28 and tab 12).

Each test names the problem it guards against, so the reason survives even if
the fix is ever refactored away.
"""
import pandas as pd
import pytest
from starlette.datastructures import QueryParams

import server.app as app
from metrics import funnel
from pipeline.build_dashboard_data import compute_with_comparison
from scope.filter import Scope
from server.insights import extra_note
from tests.sample_data import prepared

YTD_2026 = Scope(year=2026, months=list(range(1, 9)))


def _frames():
    """DSR knows about P1 only; RBS also holds P2, which DSR has never seen."""
    dsr = pd.DataFrame({
        "policy_reference": ["P1", "P3"],
        "status": ["Quote", "Quote"],
        "premium": [0.0, 0.0],
        "inception_date": pd.to_datetime(["2026-02-01", "2026-02-01"]),
    })
    rbs = pd.DataFrame({
        "policy_reference": ["P1", "P2"],
        "premium": [100.0, 300.0],
        "inception_date": pd.to_datetime(["2026-02-01", "2026-02-01"]),
    })
    return dsr, rbs


def test_binds_dsr_has_never_seen_are_measured():
    """B/Q divides RBS binds by DSR quotes, so a bind DSR lacks inflates it."""
    dsr, rbs = _frames()
    gap = funnel.binds_not_in_dsr(dsr, rbs, YTD_2026)
    assert gap["policies"] == 1 and gap["of_binds"] == 2
    assert gap["premium_share"] == pytest.approx(0.75)      # $300 of $400
    assert funnel.bind_rate(dsr, rbs, YTD_2026) == pytest.approx(1.0)   # 2 binds / 2 quotes
    assert gap["bind_rate"] == pytest.approx(0.5)           # only P1 is in both


def test_the_page_says_so_next_to_the_win_rate():
    """The overstatement is shown under B/Q, not just recorded in the workbook."""
    current = {"funnel": {"quotes": 100, "binds": 120,
                          "binds_not_in_dsr": {"policies": 30, "of_binds": 120,
                                               "premium_share": 0.09, "bind_rate": 0.9}}}
    note = extra_note(current, "funnel.bind_rate")
    assert "no DSR row at all" in note and "would read 90.0%" in note
    assert "More binds (120) than quotes (100)" in note      # the rate is above 100%
    assert "no DSR row at all" in extra_note(current, "funnel.end_to_end_win_rate")


def _view(query=""):
    app._latest.update(data=prepared(), error=None, views={}, last_run="now")
    return app._view_for(QueryParams(query))


def test_a_comparison_year_that_is_not_in_the_extract_is_blank_not_zero():
    """2021 against 2020 used to read as a book that collapsed to $0."""
    data = prepared()
    comparison = compute_with_comparison(data, Scope(year=2025, months=[1, 2]))
    assert comparison["prior"] is None                      # 2024 isn't in the sample
    assert comparison["missing_prior_year"] == 2024
    html = app.render_dashboard(_view("year=2025&period=custom&m=1&m=2"), "now", None)
    assert "This extract has no 2024 data" in html
    assert "left blank rather than shown as zero" in html


def test_commission_note_says_what_the_blank_zero_rule_is_worth():
    """A blank commission counts as none charged, which pushes the margin up."""
    current = {"quality": {"margin_cover": 0.995, "commission_cover": 0.885,
                           "uw_margin_pct": 44.4, "uw_margin_pct_recorded_commission": 43.0}}
    note = extra_note(current, "quality.uw_margin_pct")
    assert "11.5% of the margin premium records no commission" in note
    assert "margin reads 43.0%" in note
    # The same warning belongs on the per-underwriter version of the figure.
    assert "records no commission" in extra_note(
        current, "productivity_stand_in.uw_margin_per_active_underwriter")


def test_drivers_are_not_split_for_a_period_with_barely_any_deals():
    """The sample has 2 binds, so a four-driver story would be noise."""
    html = app.render_dashboard(_view(), "now", None)
    assert "Not split for these filters" in html


def test_trends_say_so_when_the_period_is_past_the_last_complete_month():
    """Q4 of this year has no complete months yet, so there is nothing to chart."""
    html = app.render_dashboard(_view("period=q4"), "now", None)
    assert "Nothing to chart" in html and "last month with complete data" in html
