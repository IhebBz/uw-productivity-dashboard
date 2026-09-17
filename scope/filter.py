"""The single filter gate.

One definition of "in scope" - year, months, entity, line of business,
business type, placement - applied the same way to any cleaned DSR or RBS
dataframe. This works because ingest/clean_dsr.py and clean_rbs.py already
rename each report's own column names onto one shared set (using the
translation table in config/field_map.py) - so this function never needs to
know or care which report it's filtering.

Copying this filter logic by hand into a second function anywhere else is
exactly how the two reports would quietly drift apart (metrics workbook,
tab 3, Rule 1) - this is deliberately the only place it's written.
"""
from dataclasses import dataclass
import pandas as pd


@dataclass
class Scope:
    """One query's worth of filters. Any field left as None means 'no filter'."""
    year: int = None
    months: list = None
    entity: str = None
    line_of_business: str = None
    business_type: str = None
    placement: str = None
    underwriter: str = None


def apply_scope(df: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    """Filter a cleaned DSR or RBS dataframe down to one Scope."""
    mask = pd.Series(True, index=df.index)
    if scope.year is not None:
        mask &= df["inception_date"].dt.year == scope.year
    if scope.months is not None:
        mask &= df["inception_date"].dt.month.isin(scope.months)
    if scope.entity is not None:
        mask &= df["entity"] == scope.entity
    if scope.line_of_business is not None:
        mask &= df["line_of_business"] == scope.line_of_business
    if scope.business_type is not None:
        mask &= df["business_type"] == scope.business_type
    if scope.placement is not None:
        mask &= df["placement"] == scope.placement
    if scope.underwriter is not None:
        mask &= df["underwriter"] == scope.underwriter
    return df[mask]
