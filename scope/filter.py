"""The single filter gate.

One definition of "in scope" - period, entity, line of business, business
type, placement, underwriter - applied the same way to any cleaned DSR or RBS
dataframe. This works because ingest/clean_dsr.py and clean_rbs.py already
rename each report's own column names onto one shared set (using the
translation table in config/field_map.py) - so this function never needs to
know or care which report it's filtering.

Copying this filter logic by hand into a second function anywhere else is
exactly how the two reports would quietly drift apart (metrics workbook,
tab 3, Rule 1) - this is deliberately the only place it's written. Every
filter on the dashboard (workbook tab 7) ends up as one field on Scope.
"""
from dataclasses import dataclass
import pandas as pd

from config.field_map import normalise_entity
from ingest.underwriter_names import normalise_underwriter_name

INCEPTION = "inception"
SUBMISSION = "submission"


@dataclass
class Scope:
    """One query's worth of filters. Any field left as None means 'no filter'.

    Period is either:
    - year + months: those calendar months of that year (YTD, or any months
      picked by hand), or
    - year + ttm_end_month: the twelve months ending with that month of that
      year ("trailing twelve months"). months is ignored in this case.

    date_basis says which date the period is judged by. "submission" only
    works on DSR - RBS has no submission date (tab 3, Rule 3), so asking RBS
    for it raises an error rather than quietly using a different date.
    """
    year: int = None
    months: list = None
    entity: str = None
    line_of_business: str = None
    business_type: str = None
    placement: str = None
    underwriter: str = None
    date_basis: str = INCEPTION
    ttm_end_month: int = None


def _month_index(year, month):
    """One running number per calendar month, so a window can cross a year end."""
    return year * 12 + month - 1


# The text columns the filter compares against.
TEXT_FILTER_COLUMNS = ("entity", "line_of_business", "business_type", "placement", "underwriter")


def add_filter_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Store fast-to-filter copies of the filter columns, once.

    Two things make a filter step slow on the real extract: pulling year and
    month out of a date (~36ms) and comparing text (~15ms per filter). The
    dashboard runs ~100 filter steps per page, so both are done once here
    instead: each date's month number, and each text column as a pandas
    "category" (compared in well under 1ms). Called once in pipeline/prepare().

    These copies are only ever read by apply_scope. Metrics keep grouping by
    the original columns, so nothing else changes. apply_scope gives the same
    answer with or without them.
    """
    df = df.copy()
    for date_column in ("inception_date", "submission_date"):
        if date_column in df.columns:
            dates = df[date_column]
            df[_fast_column(date_column)] = _month_index(dates.dt.year, dates.dt.month)
    for column in TEXT_FILTER_COLUMNS:
        if column in df.columns:
            df[_fast_column(column)] = df[column].astype("category")
    return df


def _fast_column(column: str) -> str:
    """Name of the fast copy of a column (see add_filter_columns)."""
    return f"{column}_for_filter"


def _month_indexes(df: pd.DataFrame, date_column: str) -> pd.Series:
    """Month number per row: the stored copy if there is one, else worked out now."""
    stored = _fast_column(date_column)
    if stored in df.columns:
        return df[stored]
    return _month_index(df[date_column].dt.year, df[date_column].dt.month)


def month_number(year: int, month: int) -> int:
    """One running number per calendar month (Jan 2026 and Dec 2025 are 1 apart)."""
    return _month_index(year, month)


def month_numbers(df: pd.DataFrame, date_basis: str = INCEPTION) -> pd.Series:
    """Each row's month number on a date basis - for splitting figures by month.

    Same rule as apply_scope: RBS has no submission date, so asking for it
    raises rather than quietly using another date (tab 3, Rule 3).
    """
    date_column = "submission_date" if date_basis == SUBMISSION else "inception_date"
    if date_column not in df.columns:
        raise ValueError(f"This report has no '{date_column}' column (metrics workbook, tab 3, Rule 3).")
    return _month_indexes(df, date_column)


def _equals(df: pd.DataFrame, column: str, value) -> pd.Series:
    """Rows where a text column equals value, using the fast copy if there is one."""
    stored = _fast_column(column)
    return (df[stored] if stored in df.columns else df[column]) == value


def apply_scope(df: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    """Filter a cleaned DSR or RBS dataframe down to one Scope.

    The period goes by INCEPTION date unless the scope asks for submission
    date - tab 3, Rule 3: RBS has no submission date, so any view that
    combines the two must use inception date or it silently mixes two
    different months.

    Entity and underwriter filters go through the same clean-up the data
    went through in ingest/ (tab 3, Rules 2 and 5), so "Mosaic Syndicate
    2610" or "jane  SMITH" still match.
    """
    date_column = "submission_date" if scope.date_basis == SUBMISSION else "inception_date"
    if date_column not in df.columns:
        raise ValueError(
            f"This report has no '{date_column}' column. RBS has no submission date "
            f"(metrics workbook, tab 3, Rule 3) - use inception date for any figure "
            f"that needs RBS.")

    mask = pd.Series(True, index=df.index)
    if scope.year is not None or scope.months is not None:
        index = _month_indexes(df, date_column)
        if scope.year is not None and scope.ttm_end_month is not None:
            end = _month_index(scope.year, scope.ttm_end_month)
            mask &= index.between(end - 11, end)
        else:
            if scope.year is not None:
                mask &= index.between(_month_index(scope.year, 1), _month_index(scope.year, 12))
            if scope.months is not None:
                mask &= (index % 12 + 1).isin(scope.months)
    if scope.entity is not None:
        mask &= _equals(df, "entity", normalise_entity(scope.entity))
    if scope.line_of_business is not None:
        mask &= _equals(df, "line_of_business", scope.line_of_business)
    if scope.business_type is not None:
        mask &= _equals(df, "business_type", scope.business_type)
    if scope.placement is not None:
        mask &= _equals(df, "placement", scope.placement)
    if scope.underwriter is not None:
        mask &= _equals(df, "underwriter", normalise_underwriter_name(scope.underwriter))
    return df[mask]
