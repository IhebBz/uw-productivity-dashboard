"""How much we wrote: Bound Premium and Average Deal Size. See the metrics
workbook, tab 4, "HOW MUCH WE WROTE".
"""
import pandas as pd

from config.settings import BIND_STATUSES
from metrics.funnel import binds_from_rbs
from scope.filter import Scope, apply_scope


def bound_premium(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Bound Premium": premium on every RBS row in scope.

    Summed across every line of a policy (tab 3, Rule 4) - never after
    collapsing to one row per policy.
    """
    return apply_scope(rbs, scope)["premium"].sum()


def bound_premium_from_dsr(dsr: pd.DataFrame, scope: Scope) -> float:
    """DSR's own view of bound premium - only used as the tab 3, Rule 6 cross-check."""
    f = apply_scope(dsr, scope)
    return f.loc[f["status"].isin(BIND_STATUSES), "premium"].sum()


def average_deal_size(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Average Deal Size": Bound Premium / Binds. Blank if no binds."""
    binds = binds_from_rbs(rbs, scope)
    if not binds:
        return None
    return bound_premium(rbs, scope) / binds
