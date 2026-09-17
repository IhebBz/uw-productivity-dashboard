"""Checks the funnel metrics against a small, hand-built sample of cleaned
DSR/RBS rows - small enough to know the right answer by counting on your
fingers, which is the point of a unit test.
"""
import pandas as pd

from metrics import funnel
from scope.filter import Scope


def _dsr(rows):
    """Build a minimal already-cleaned DSR dataframe from a list of dicts."""
    df = pd.DataFrame(rows)
    df["inception_date"] = pd.to_datetime(df["inception_date"])
    return df


def _rbs(rows):
    """Build a minimal already-cleaned RBS dataframe from a list of dicts."""
    df = pd.DataFrame(rows)
    df["inception_date"] = pd.to_datetime(df["inception_date"])
    return df


def test_quote_rate_is_none_below_the_minimum_sample_size():
    """quote_rate() should return None, not a number, on too few submissions."""
    dsr = _dsr([
        {"policy_reference": "P1", "status": "Quote", "inception_date": "2025-01-01"},
    ])
    result = funnel.quote_rate(dsr, Scope())
    assert result is None  # only 1 submission, floor is MIN_SUBMISSIONS_FOR_RATE (20)


def test_bind_rate_uses_rbs_not_dsr_binds():
    """bind_rate() must divide by RBS-sourced binds, not DSR's own bind count."""
    # 25 DSR submissions, all quoted, only 20 actually marked "Bound" in DSR -
    # but RBS (the source of truth for binds) only has 10 of those policies.
    dsr_rows = [{"policy_reference": f"P{i}", "status": "Quote", "inception_date": "2025-01-01"}
                for i in range(25)]
    for i in range(20):
        dsr_rows[i]["status"] = "Bound"
    dsr = _dsr(dsr_rows)

    rbs_rows = [{"policy_reference": f"P{i}", "inception_date": "2025-01-01"} for i in range(10)]
    rbs = _rbs(rbs_rows)

    rate = funnel.bind_rate(dsr, rbs, Scope())
    assert rate == 10 / 25  # RBS's 10 binds over DSR's 25 quotes, NOT DSR's own 20 binds
