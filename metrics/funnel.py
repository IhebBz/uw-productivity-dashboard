"""The funnel: Submissions and Quotes come only from DSR (RBS has no opinion
on business that wasn't won). Binds is reconciled between the two, and RBS's
figure is what the win rates actually use, since RBS is the source of truth
for bound business. See the metrics workbook, tab 4, "THE FUNNEL".
"""
import pandas as pd

from config.settings import QUOTED_STATUSES, BIND_STATUSES
from scope.filter import Scope, apply_scope


def submissions(dsr: pd.DataFrame, scope: Scope) -> int:
    """Count distinct policies in scope, at any status."""
    return apply_scope(dsr, scope)["policy_reference"].nunique()


def quotes(dsr: pd.DataFrame, scope: Scope) -> int:
    """Count distinct policies in scope with a quoted status."""
    f = apply_scope(dsr, scope)
    return f.loc[f["status"].isin(QUOTED_STATUSES), "policy_reference"].nunique()


def binds_from_dsr(dsr: pd.DataFrame, scope: Scope) -> int:
    """Count distinct policies in scope with a bound status.

    This is DSR's own opinion of Binds, kept only as the reconciliation
    check against RBS's bind count - RBS is the figure the dashboard shows.
    """
    f = apply_scope(dsr, scope)
    return f.loc[f["status"].isin(BIND_STATUSES), "policy_reference"].nunique()


def binds_from_rbs(rbs: pd.DataFrame, scope: Scope) -> int:
    """Tab 4, "Binds": count distinct policies with a bound RBS row, in scope.

    Every RBS row is already a bind. Counting distinct Policy References
    (not rows) follows tab 3, Rule 4 - a policy with several lines is one bind.
    """
    return apply_scope(rbs, scope)["policy_reference"].nunique()


def quote_rate(dsr: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Q/S": Quotes / Submissions. Blank (None, not zero) if no submissions."""
    s = submissions(dsr, scope)
    if not s:
        return None
    return quotes(dsr, scope) / s


def bind_rate(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "B/Q": Binds (RBS) / Quotes (DSR). Blank (None, not zero) if no quotes.

    Mixes the two reports on purpose - Binds comes from RBS, the source of
    truth for bound business (tab 3, Rule 7).
    """
    q = quotes(dsr, scope)
    if not q:
        return None
    return binds_from_rbs(rbs, scope) / q


def end_to_end_win_rate(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "B/S": Binds (RBS) / Submissions (DSR). Blank if no submissions."""
    s = submissions(dsr, scope)
    if not s:
        return None
    return binds_from_rbs(rbs, scope) / s
