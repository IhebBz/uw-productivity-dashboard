"""Checks the dashboard's filter toolbar (workbook tab 7): reading choices from the
page address, cascading dropdowns, clearing a stranded choice, and that the
whole page renders for each kind of view.
"""
import pandas as pd
import pytest
from starlette.datastructures import QueryParams

import server.app as app
from scope.filter import Scope
from scope.options import filter_options
from server.filters import parse_filters, drop_stranded_selections, default_state
from tests.sample_data import dsr_rows, rbs_rows, prepared

AS_AT = pd.Timestamp("2026-09-15")
CHOICES = dict(years=[2025, 2026], business_types=["New", "Renewal"],
               placements=["Facility/DUA", "Open Market"])


def _parse(query):
    return parse_filters(QueryParams(query), AS_AT, **CHOICES)


def test_defaults_are_this_year_so_far():
    """Data as at 15 Sep 2026 opens on Jan-Aug 2026, all business, inception basis."""
    state = _parse("")
    scope = state.to_scope(AS_AT)
    assert (state.period, scope.year, scope.months, state.bt, state.basis) == \
        ("ytd", 2026, list(range(1, 9)), "", "inception")


@pytest.mark.parametrize("query, months, ttm_end", [
    ("period=ttm&m=1", None, 8),                 # last 12 months ignores picked months
    ("period=full", list(range(1, 13)), None),
    ("period=q2", [4, 5, 6], None),
    ("period=custom&m=3&m=1", [1, 3], None),
    ("period=custom", list(range(1, 9)), None),  # nothing picked: back to this year so far
])
def test_period_choices(query, months, ttm_end):
    """Each period choice turns into the right months."""
    scope = _parse(query).to_scope(AS_AT)
    assert scope.months == months and scope.ttm_end_month == ttm_end and scope.year == 2026


def test_bad_values_fall_back_to_defaults():
    """A typo'd link can't produce a wrong page: unknown values are ignored."""
    state = _parse("year=1999&m=13&m=abc&bt=Bogus&basis=whenever&period=forever")
    assert state == default_state(AS_AT)


def test_address_round_trip():
    """A view's address reads back as exactly the same choices."""
    state = _parse("period=custom&year=2025&m=2&m=3&bt=Renewal&mop=Open+Market"
                   "&basis=submission&ent=Mosaic+UK")
    assert _parse(state.query()[1:]) == state


def test_dropdowns_cascade():
    """With Entity = Mosaic UK, only Jane is offered; Entity itself still lists both."""
    scope = Scope(year=2026, months=list(range(1, 9)), entity="Mosaic UK")
    options = filter_options(dsr_rows(), rbs_rows(), scope)
    assert options["underwriter"] == ["smith jane"]
    assert options["entity"] == ["Mosaic UK", "Mosaic US"]


def test_stranded_underwriter_is_cleared_but_new_entity_kept():
    """Picking Mosaic US while Jane (UK only) is selected clears Jane, keeps the entity."""
    state = _parse("uw=smith+jane&ent=Mosaic+US")
    dsr, rbs = dsr_rows(), rbs_rows()
    state, options = drop_stranded_selections(
        state, lambda s: filter_options(dsr, rbs, s.to_scope(AS_AT)))
    assert state.uw == "" and state.ent == "Mosaic US"
    assert state.cleared == ["smith jane"]
    assert options["underwriter"] == ["lee bob"]


def test_every_kind_of_view_renders():
    """Smoke test on the whole page - catches a figure the page asks for that the
    pipeline no longer produces (the "headcount" key rename broke the page once)."""
    app._latest.update(data=prepared(), error=None, views={}, last_run="now")
    for query in ("", "period=ttm", "period=q1", "basis=submission", "uw=lee+bob",
                  "ent=Mosaic+UK&uw=lee+bob"):
        view = app._view_for(QueryParams(query))
        html = app.render_dashboard(view, "now", None)
        assert "Line of business" in html and "Underwriters" in html
        assert "Not available yet: Product, Role, Tenure" in html
    assert "Cleared Lee, Bob" in html
    assert "Filtered to" in html and "Clear all" in html  # the Mosaic UK chip


def test_chip_removes_only_its_own_filter():
    """The x on a chip keeps every other choice as it was."""
    state = _parse("period=q2&bt=New&lob=Cyber")
    after = _parse(state.query(lob="")[1:])
    assert (after.period, after.bt, after.lob) == ("q2", "New", "")
