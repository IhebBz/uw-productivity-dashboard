"""Everything about time windows: how old the data is, which month is the
last complete one, the matching prior-year window, and a plain-English label
for any window. See the metrics workbook, tab 7 ("Timeframe", "Months",
"Year").
"""
import calendar
import dataclasses

import pandas as pd

from config.settings import COMPARISON_YEARS_BACK
from scope.filter import Scope

MONTH_NAMES = [calendar.month_abbr[m] for m in range(1, 13)]


def data_as_at(dsr: pd.DataFrame) -> pd.Timestamp:
    """The date the data runs up to: the latest DSR submission date.

    Submission date is used because a new submission is logged the day it
    arrives, while inception dates run months into the future.
    """
    latest = dsr["submission_date"].max()
    if pd.isna(latest):
        raise ValueError("DSR has no usable submission dates - can't tell how current the data is.")
    return latest.normalize()


def last_complete_month(as_at: pd.Timestamp) -> tuple:
    """(year, month) of the last month with a full month of data behind it.

    Data as at 15 Sep 2026 -> (2026, 8): September is still in progress.
    Data as at 30 Sep 2026 -> (2026, 9): the month has ended.
    """
    if as_at.is_month_end:
        return as_at.year, as_at.month
    previous = as_at - pd.offsets.MonthEnd(1)
    return previous.year, previous.month


def prior_year_scope(scope: Scope) -> Scope:
    """The same filters, moved back COMPARISON_YEARS_BACK years (same months)."""
    if scope.year is None:
        return None
    return dataclasses.replace(scope, year=scope.year - COMPARISON_YEARS_BACK)


def describe_period(scope: Scope) -> str:
    """A short label for a scope's window, e.g. "Jan-Aug 2026" or "Sep 2025-Aug 2026"."""
    if scope.year is None:
        return "All years"
    if scope.ttm_end_month is not None:
        end_month = scope.ttm_end_month
        start_month = end_month % 12 + 1
        start_year = scope.year if end_month == 12 else scope.year - 1
        return (f"{MONTH_NAMES[start_month - 1]} {start_year}"
                f"–{MONTH_NAMES[end_month - 1]} {scope.year}")
    months = sorted(scope.months or range(1, 13))
    if len(months) == 12:
        return str(scope.year)
    if len(months) == 1:
        return f"{MONTH_NAMES[months[0] - 1]} {scope.year}"
    contiguous = months == list(range(months[0], months[-1] + 1))
    if contiguous:
        return f"{MONTH_NAMES[months[0] - 1]}–{MONTH_NAMES[months[-1] - 1]} {scope.year}"
    return ", ".join(MONTH_NAMES[m - 1] for m in months) + f" {scope.year}"
