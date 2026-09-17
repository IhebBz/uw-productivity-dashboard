"""Checks the time-window filters (workbook tab 7): YTD months, trailing
twelve months across a year end, submission-date basis, the prior-year
comparison, and the fast filter copies giving the same answer.
"""
import pandas as pd
import pytest

from scope.filter import Scope, apply_scope, add_filter_columns
from scope.period import last_complete_month, prior_year_scope, describe_period
from tests.sample_data import dsr_rows, rbs_rows


def test_ytd_months_pick_those_months_of_that_year():
    """Jan-Aug 2026 on inception date: P1-P4, not the 2025 policies."""
    got = apply_scope(dsr_rows(), Scope(year=2026, months=list(range(1, 9))))
    assert sorted(got["policy_reference"]) == ["P1", "P2", "P3", "P4"]


def test_trailing_twelve_months_cross_the_year_end():
    """TTM ending Mar 2026 = Apr 2025 to Mar 2026: P1, P2, P3 only."""
    got = apply_scope(dsr_rows(), Scope(year=2026, ttm_end_month=3))
    assert sorted(got["policy_reference"]) == ["P1", "P2", "P3"]


def test_submission_basis_uses_submission_date():
    """P1 was submitted in Dec 2025, so it drops out of 2026 on submission basis."""
    got = apply_scope(dsr_rows(), Scope(year=2026, months=list(range(1, 9)), date_basis="submission"))
    assert sorted(got["policy_reference"]) == ["P2", "P3", "P4"]


def test_rbs_refuses_submission_basis():
    """Tab 3, Rule 3: RBS has no submission date - error, not a silent swap to inception."""
    with pytest.raises(ValueError, match="submission date"):
        apply_scope(rbs_rows(), Scope(year=2026, date_basis="submission"))


@pytest.mark.parametrize("scope", [
    Scope(year=2026, months=[2, 3]),
    Scope(year=2026, ttm_end_month=3, entity="Mosaic UK"),
    Scope(months=[3], business_type="Renewal", placement="Open Market"),
    Scope(year=2026, underwriter="SMITH, jane", date_basis="submission"),
])
def test_fast_filter_copies_give_the_same_rows(scope):
    """add_filter_columns is a speed-up only: the same rows come back either way."""
    plain = dsr_rows()
    fast = add_filter_columns(plain)
    assert list(apply_scope(fast, scope).index) == list(apply_scope(plain, scope).index)


def test_last_complete_month():
    """Mid-month data: last month is the complete one. Month-end data: this month is."""
    assert last_complete_month(pd.Timestamp("2026-09-15")) == (2026, 8)
    assert last_complete_month(pd.Timestamp("2026-09-30")) == (2026, 9)
    assert last_complete_month(pd.Timestamp("2026-01-10")) == (2025, 12)


def test_prior_year_scope_keeps_every_other_filter():
    """The comparison is the same slice, one year back."""
    scope = Scope(year=2026, months=[1, 2], entity="Mosaic UK", ttm_end_month=None)
    prior = prior_year_scope(scope)
    assert prior.year == 2025 and prior.months == [1, 2] and prior.entity == "Mosaic UK"


def test_describe_period():
    """Plain-English window labels."""
    assert describe_period(Scope(year=2026, months=list(range(1, 9)))) == "Jan–Aug 2026"
    assert describe_period(Scope(year=2026, ttm_end_month=8)) == "Sep 2025–Aug 2026"
    assert describe_period(Scope(year=2026, ttm_end_month=12)) == "Jan 2026–Dec 2026"
    assert describe_period(Scope(year=2026, months=[1, 3])) == "Jan, Mar 2026"
    assert describe_period(Scope(year=2026)) == "2026"
