"""Local stand-ins for headcount. The HR file is not available, so neither of
these is true employed headcount - see the metrics workbook, tab 1, point 5.

Active underwriters (RBS-based) is the recommended default: it's built
entirely from RBS, our source of truth for bound business. Roster
underwriters (DSR-based) is broader and kept as secondary context, since it's
the only one that can see people who tried and didn't win.

Neither can see a non-selling leader, a brand-new joiner, or someone on long
leave, and neither can be split by Role or Tenure - all three need the HR
file. Never call either of these "headcount" without naming which one.
"""
import pandas as pd

from scope.filter import Scope, apply_scope
from metrics.quality import uw_margin_pct


def active_underwriters(rbs: pd.DataFrame, scope: Scope) -> int:
    """Count distinct underwriters with at least one bound RBS row in scope."""
    f = apply_scope(rbs, scope)
    return f["underwriter"].dropna().nunique()


def roster_underwriters(dsr: pd.DataFrame, scope: Scope) -> int:
    """Count distinct underwriters with at least one DSR row in scope, win or not."""
    f = apply_scope(dsr, scope)
    return f["underwriter"].dropna().nunique()


def premium_per_active_underwriter(rbs: pd.DataFrame, scope: Scope) -> float:
    """Bound Premium divided by Active underwriters. The recommended default productivity figure."""
    heads = active_underwriters(rbs, scope)
    if not heads:
        return None
    return apply_scope(rbs, scope)["premium"].sum() / heads


def uw_margin_per_active_underwriter(rbs: pd.DataFrame, scope: Scope) -> float:
    """(Bound Premium x UW Margin %) divided by Active underwriters."""
    heads = active_underwriters(rbs, scope)
    margin_pct = uw_margin_pct(rbs, scope)
    if not heads or margin_pct is None:
        return None
    premium = apply_scope(rbs, scope)["premium"].sum()
    return premium * margin_pct / 100 / heads


def premium_per_roster_underwriter(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> float:
    """Bound Premium divided by Roster underwriters. A second, broader view."""
    heads = roster_underwriters(dsr, scope)
    if not heads:
        return None
    return apply_scope(rbs, scope)["premium"].sum() / heads
