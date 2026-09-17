"""The funnel: Submissions and Quotes come only from DSR (RBS has no opinion
on business that wasn't won). Binds is reconciled between the two, and RBS's
figure is what the win rates actually use, since RBS is the source of truth
for bound business. See the metrics workbook, tab 4, "THE FUNNEL".
"""
import pandas as pd

from config.settings import QUOTED_STATUSES, BIND_STATUSES, MIN_SUBMISSIONS_FOR_RATE, \
    MIN_QUOTES_FOR_BIND_RATE
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
    """Count distinct policies in scope. Every RBS row is already a bind."""
    return apply_scope(rbs, scope)["policy_reference"].nunique()


def quote_rate(dsr: pd.DataFrame, scope: Scope) -> float:
    """Quotes divided by Submissions. Blank (None) if there were too few submissions."""
    s = submissions(dsr, scope)
    if s < MIN_SUBMISSIONS_FOR_RATE:
        return None
    return quotes(dsr, scope) / s


def bind_rate(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> float:
    """RBS-sourced Binds divided by DSR-sourced Quotes. Blank if too few quotes."""
    q = quotes(dsr, scope)
    if q < MIN_QUOTES_FOR_BIND_RATE:
        return None
    return binds_from_rbs(rbs, scope) / q


def end_to_end_win_rate(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope) -> float:
    """RBS-sourced Binds divided by DSR-sourced Submissions."""
    s = submissions(dsr, scope)
    if s < MIN_SUBMISSIONS_FOR_RATE:
        return None
    return binds_from_rbs(rbs, scope) / s
