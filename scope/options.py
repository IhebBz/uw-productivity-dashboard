"""Which choices each dropdown filter offers, given the other filters.

Same idea as Matt's build ("cascading filters"): a dropdown that offers an
underwriter who can't appear in the current scope is a dead end - you pick
them and the page empties. So each list is built from the data under every
OTHER active filter, with its own filter left out, so the current choice
stays visible. See the metrics workbook, tab 7.

Values are collected from both reports, across the selected period AND the
comparison period, so nobody disappears just because they only wrote
business last year.
"""
import dataclasses

import pandas as pd

from scope.filter import Scope, SUBMISSION, apply_scope
from scope.period import prior_year_scope

# Scope field -> cleaned column. Business type and placement are pills with
# fixed choices, so they don't cascade.
DROPDOWNS = {
    "line_of_business": "line_of_business",
    "entity": "entity",
    "underwriter": "underwriter",
}


def filter_options(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> dict:
    """Return {scope field: sorted list of values still available}."""
    frames = [dsr] if scope.date_basis == SUBMISSION else [dsr, rbs]
    periods = [scope] + ([prior_year_scope(scope)] if scope.year is not None else [])

    options = {}
    for field, column in DROPDOWNS.items():
        values = set()
        for period in periods:
            others_only = dataclasses.replace(period, **{field: None})
            for frame in frames:
                values.update(apply_scope(frame, others_only)[column].dropna().unique())
        options[field] = sorted(values, key=lambda v: str(v).lower())
    return options


def fixed_choices(dsr: pd.DataFrame, rbs: pd.DataFrame, column: str) -> list:
    """Every value a pill filter can take, from the whole of both reports."""
    values = set(dsr[column].dropna().unique()) | set(rbs[column].dropna().unique())
    return sorted(values)
