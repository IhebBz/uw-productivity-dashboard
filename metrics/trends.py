"""Month-by-month figures for the trend charts and the headline sparklines.

Each monthly value uses exactly the same definition as the whole-period
figure in funnel.py, premium.py and quality.py - worked out for that one
month, with every filter except the period applied. tests/test_trends.py
checks a month here equals the page's figure for that month picked on its own.

The window is the TREND_MONTHS months ending with the last month of the
selected period (never later than the last complete month), so a single
chart shows the selected months in context: what came before, and the same
months a year earlier.
"""
import dataclasses

import pandas as pd

from config.settings import QUOTED_STATUSES, TREND_MONTHS
from scope.filter import INCEPTION, Scope, apply_scope, month_number, month_numbers
from scope.period import MONTH_NAMES, last_complete_month


def _window_end(scope: Scope, as_at) -> int:
    """Month number of the window's last month."""
    last_year, last_month = last_complete_month(as_at)
    latest = month_number(last_year, last_month)
    if scope.year is None:
        return latest
    if scope.ttm_end_month is not None:
        end = month_number(scope.year, scope.ttm_end_month)
    else:
        end = month_number(scope.year, max(scope.months or range(1, 13)))
    return min(end, latest)


def _selected(scope: Scope, number: int) -> bool:
    """Is this month part of the selected period?"""
    year, month = divmod(number, 12)
    month += 1
    if scope.year is None:
        return True
    if scope.ttm_end_month is not None:
        end = month_number(scope.year, scope.ttm_end_month)
        return end - 11 <= number <= end
    return year == scope.year and month in (scope.months or range(1, 13))


def _by_month(values: pd.Series, numbers: list) -> list:
    """A grouped series laid out over the window; months with no rows are None."""
    return [None if pd.isna(values.get(n)) else values.get(n) for n in numbers]


def monthly_trends(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope, as_at) -> dict:
    """Every trend series over the window, plus which months are selected.

    Returns {"months": [{"number", "label", "short", "selected"}], "series": {name: [value per month]}}.
    Series needing RBS are left out on submission-date basis.
    """
    end = _window_end(scope, as_at)
    numbers = list(range(end - TREND_MONTHS + 1, end + 1))
    months = [{"number": n, "label": f"{MONTH_NAMES[n % 12]} {n // 12}",
               "short": f"{MONTH_NAMES[n % 12]} {str(n // 12)[2:]}", "selected": _selected(scope, n)}
              for n in numbers]
    everything_but_period = dataclasses.replace(scope, year=None, months=None, ttm_end_month=None)

    d = apply_scope(dsr, everything_but_period)
    d = d.assign(month=month_numbers(d, scope.date_basis))
    d = d[d["month"].between(numbers[0], numbers[-1])]
    submissions = d.groupby("month")["policy_reference"].nunique()
    quotes = d[d["status"].isin(QUOTED_STATUSES)].groupby("month")["policy_reference"].nunique()
    series = {
        "submissions": _by_month(submissions, numbers),
        "quotes": _by_month(quotes, numbers),
    }
    series["quote_rate"] = [q / s if s else None for q, s in
                            zip([v or 0 for v in series["quotes"]], series["submissions"])]

    if scope.date_basis == INCEPTION:
        r = apply_scope(rbs, everything_but_period)
        r = r.assign(month=month_numbers(r))
        r = r[r["month"].between(numbers[0], numbers[-1])]
        binds = r.groupby("month")["policy_reference"].nunique()
        premium = r.groupby("month")["premium"].sum()
        usable = r[r["gelr_ok"]].assign(gelr_x=lambda x: x["gelr"] * x["premium"],
                                        comm_x=lambda x: x["commission"] * x["premium"])
        usable = usable.groupby("month")[["premium", "gelr_x", "comm_x"]].sum()
        usable = usable[usable["premium"] != 0]
        margin = 100 - usable["gelr_x"] / usable["premium"] - usable["comm_x"] / usable["premium"]
        series["binds"] = _by_month(binds, numbers)
        series["bound_premium"] = _by_month(premium, numbers)
        series["uw_margin_pct"] = _by_month(margin, numbers)
        series["bind_rate"] = [b / q if q else None for b, q in
                               zip([v or 0 for v in series["binds"]], series["quotes"])]
    return {"months": months, "series": series}
