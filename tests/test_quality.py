"""Checks the quality metrics follow the metrics workbook, tab 4, on rows
small enough to work out the right answer by hand.
"""
import pandas as pd
import pytest

from metrics import quality
from scope.filter import Scope


def _rbs(rows):
    """Build a minimal already-cleaned RBS dataframe from a list of dicts."""
    df = pd.DataFrame(rows)
    df["inception_date"] = pd.to_datetime("2025-01-01")
    df["gelr_ok"] = df["gelr"].notna() & df["gelr"].ne(0)
    return df


ROWS = [
    {"premium": 100.0, "gelr": 40.0, "commission": 20.0, "plan_loss_ratio": 50.0},
    {"premium": 100.0, "gelr": None, "commission": 10.0, "plan_loss_ratio": 50.0},
]


def test_gelr_book_version_counts_blank_gelr_as_zero():
    """Book version averages across ALL rows, so a blank GELR drags it down."""
    assert quality.gelr_book_basis(_rbs(ROWS), Scope()) == pytest.approx(20.0)


def test_gelr_margin_version_uses_usable_rows_only():
    """Margin version skips the blank-GELR row entirely."""
    assert quality.gelr_margin_basis(_rbs(ROWS), Scope()) == pytest.approx(40.0)


def test_book_and_margin_gelr_differ_when_a_gelr_is_missing():
    """The two versions are separate figures, not the same number twice."""
    rbs = _rbs(ROWS)
    assert quality.gelr_book_basis(rbs, Scope()) != quality.gelr_margin_basis(rbs, Scope())


def test_uw_margin_is_one_minus_margin_gelr_minus_margin_commission():
    """100 - 40 (GELR, margin rows) - 20 (commission, margin rows) = 40."""
    assert quality.uw_margin_pct(_rbs(ROWS), Scope()) == pytest.approx(40.0)


def test_rate_adequacy_uses_the_same_rows_on_both_sides():
    """Tab 4 note: premium without a benchmark must not inflate the result.

    Only the first row has a benchmark (100 x 40 / 50 = 80). Actual premium on
    that same row is 100, so adequacy is 125% - not 250%, which is what
    dividing ALL premium (200) by that one row's benchmark would give.
    """
    assert quality.rate_adequacy(_rbs(ROWS), Scope()) == pytest.approx(125.0)
