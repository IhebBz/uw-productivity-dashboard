"""Profitability and pricing, from RBS: GELR, Commission, UW Margin %, and
Rate Adequacy. See the metrics workbook, tab 4, "HOW GOOD THE BUSINESS IS"
and "PRICING".

GELR and Commission each have a "book basis" (all premium) and a "margin
basis" (only premium with a usable GELR) version. For GELR specifically,
these two turn out to be numerically identical - the source definition
restricts BOTH to usable-GELR rows, so a blank/zero GELR is excluded either
way. Kept as two functions anyway because the original dashboard displays
them under two different labels in different places; collapsing them into
one function would make that on-screen distinction impossible to reproduce.
Commission's two versions genuinely differ (book basis uses every row,
margin basis doesn't) - see the functions below.
"""
import dataclasses

import pandas as pd

from scope.filter import Scope, apply_scope


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    """Premium-weighted average, returning None rather than dividing by zero."""
    total_weight = weights.sum()
    if not total_weight:
        return None
    return (values * weights).sum() / total_weight


def gelr_margin_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Premium-weighted GELR, restricted to rows with a usable GELR figure."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    return _weighted_average(f["gelr"], f["premium"])


def gelr_book_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Same calculation as gelr_margin_basis - see the module docstring for why
    these are numerically identical rather than two different figures.
    """
    return gelr_margin_basis(rbs, scope)


def commission_book_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Premium-weighted commission over every row in scope."""
    f = apply_scope(rbs, scope)
    return _weighted_average(f["commission"], f["premium"])


def commission_margin_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Premium-weighted commission, restricted to the margin's own rows."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    return _weighted_average(f["commission"], f["premium"])


def uw_margin_pct(rbs: pd.DataFrame, scope: Scope) -> float:
    """1 minus margin-basis GELR minus margin-basis commission, in percent units."""
    gelr = gelr_margin_basis(rbs, scope)
    comm = commission_margin_basis(rbs, scope)
    if gelr is None or comm is None:
        return None
    return 100 - gelr - comm


def margin_cover(rbs: pd.DataFrame, scope: Scope) -> float:
    """Share of premium in scope that actually has a usable GELR."""
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    if not total:
        return None
    return f.loc[f["gelr_ok"], "premium"].sum() / total


def commission_cover(rbs: pd.DataFrame, scope: Scope) -> float:
    """Share of margin premium that carries a recorded commission above zero."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    total = f["premium"].sum()
    if not total:
        return None
    return f.loc[f["commission"] > 0, "premium"].sum() / total


def rate_adequacy(rbs: pd.DataFrame, scope: Scope) -> float:
    """Actual premium divided by the plan-based benchmark premium, as a percent.

    GELR and Plan Loss Ratio are both in percent units at this point, and
    their scales cancel in this ratio - no extra division by 100 needed.
    """
    f = apply_scope(rbs, scope)
    ok = f[f["gelr_ok"]]
    benchmark = (ok["premium"] / ok["plan_loss_ratio"] * ok["gelr"]).sum()
    if not benchmark:
        return None
    return 100 * f["premium"].sum() / benchmark


def rarc(rbs: pd.DataFrame, scope: Scope) -> float:
    """Weighted-average rate change on renewing business, regardless of the
    business_type filter in scope - RARC is a renewals-only measure by
    definition, so "New" business is always excluded here even if scope
    asks for it. 100 means the rate stayed flat.

    Returns None if the RARC or expired-premium columns weren't present in
    this extract, rather than crashing - see clean_rbs.py.
    """
    if "rarc" not in rbs.columns or rbs["rarc"].isna().all():
        return None
    # business_type is deliberately overridden, not inherited from scope -
    # RARC always means renewals, no matter what the caller filtered for
    # (metrics workbook, tab 6: "RARC ignores the filter altogether").
    rarc_scope = dataclasses.replace(scope, business_type="Renewal")
    f = apply_scope(rbs, rarc_scope)
    renewals = f[
        f["expired_premium"].notna()
        & f["expired_premium"].ne(0)
        & f["rarc"].notna()
    ]
    return _weighted_average(renewals["rarc"], renewals["expired_premium"])
