"""Profitability and pricing, from RBS: GELR, Commission, UW Margin %, and
Rate Adequacy. See the metrics workbook, tab 4, "HOW GOOD THE BUSINESS IS"
and "PRICING".

GELR and Commission each come in two versions (tab 4), and the dashboard
always says which one it means:
- Book version: premium-weighted average across ALL rows in scope. A row
  with no GELR or commission recorded still counts, as 0.
- Margin version: the same average, but only over rows with a usable GELR
  figure - exactly the rows UW Margin % is built from.

Careful when comparing figures with Matt's build (workbook tab 12): he shows
ONE GELR, which matches our MARGIN version (and also drops 2021 inceptions,
which we don't), and ONE commission, which matches our BOOK version. Lining
up the like-named columns across the two dashboards mis-matches both.
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


def gelr_book_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "GELR": premium-weighted GELR across all rows, blank GELR as 0."""
    f = apply_scope(rbs, scope)
    return _weighted_average(f["gelr"].fillna(0), f["premium"])


def gelr_margin_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "GELR (margin version)": premium-weighted GELR, usable rows only."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    return _weighted_average(f["gelr"], f["premium"])


def commission_book_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Commission": premium-weighted commission across all rows."""
    f = apply_scope(rbs, scope)
    return _weighted_average(f["commission"], f["premium"])


def commission_margin_basis(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Commission (margin version)": restricted to the margin's own rows."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    return _weighted_average(f["commission"], f["premium"])


def uw_margin_pct(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "UW Margin %": 1 minus GELR minus Commission, in percent units.

    Uses the margin versions of both, since those are the rows the margin is
    built from. Open question carried over from the workbook, not yet
    decided: whether Mosaic's own internal commission should also be
    subtracted. It isn't, until that decision is made.
    """
    gelr = gelr_margin_basis(rbs, scope)
    comm = commission_margin_basis(rbs, scope)
    if gelr is None or comm is None:
        return None
    return 100 - gelr - comm


def uw_margin_pct_recorded_commission(rbs: pd.DataFrame, scope: Scope) -> float:
    """UW Margin % over only the rows that record a commission - a diagnostic.

    UW Margin % treats a blank or zero commission as "no commission charged"
    (tab 4), while a blank or zero GELR is treated as "not usable" and left
    out. The two halves of 100 - GELR - Commission therefore handle a missing
    value in opposite ways, and every row with no commission recorded pushes
    the margin up.

    This is the same figure worked out over the rows that do record one, so
    the page can say how much of the margin rests on that treatment. Not a
    headline figure: it drops real zero-commission business, which exists.
    """
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"] & f["commission"].gt(0)]
    gelr = _weighted_average(f["gelr"], f["premium"])
    comm = _weighted_average(f["commission"], f["premium"])
    if gelr is None or comm is None:
        return None
    return 100 - gelr - comm


def margin_cover(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Margin cover": share of premium in scope that has a usable GELR."""
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    if not total:
        return None
    return f.loc[f["gelr_ok"], "premium"].sum() / total


def commission_cover(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Commission cover": share of margin premium with commission above zero."""
    f = apply_scope(rbs, scope)
    f = f[f["gelr_ok"]]
    total = f["premium"].sum()
    if not total:
        return None
    return f.loc[f["commission"] > 0, "premium"].sum() / total


def rate_adequacy(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Rate Adequacy": actual premium / plan-based benchmark premium, as a percent.

    The workbook notes that Matt's version compares ALL premium against a
    benchmark built from only some rows, which overstates the result, and
    says to fix it. Fixed here: both sides use exactly the same rows - those
    with a usable GELR and a Business Plan Loss Ratio above zero (a benchmark
    can't be worked out without both).

    Benchmark premium per row = premium x GELR / Plan Loss Ratio. Both are in
    percent units at this point, so their scales cancel in the ratio.
    """
    f = apply_scope(rbs, scope)
    rows = f[f["gelr_ok"] & f["plan_loss_ratio"].notna() & f["plan_loss_ratio"].gt(0)]
    benchmark = (rows["premium"] * rows["gelr"] / rows["plan_loss_ratio"]).sum()
    if not benchmark:
        return None
    return 100 * rows["premium"].sum() / benchmark


def rarc(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "RARC": weighted-average rate change on renewing business only.

    "Always renewals only, no matter what other filters are set" - so "New"
    business is excluded even if scope asks for it. Every other filter
    (year, entity, ...) still applies. 100 means the rate stayed flat.

    Returns None if the RARC or expired-premium columns weren't present in
    this extract, rather than crashing - see clean_rbs.py.
    """
    if "rarc" not in rbs.columns or rbs["rarc"].isna().all():
        return None
    rarc_scope = dataclasses.replace(scope, business_type="Renewal")
    f = apply_scope(rbs, rarc_scope)
    renewals = f[
        f["expired_premium"].notna()
        & f["expired_premium"].ne(0)
        & f["rarc"].notna()
    ]
    return _weighted_average(renewals["rarc"], renewals["expired_premium"])


def _median(values: pd.Series) -> float:
    """Middle value, or None when there's nothing to take the middle of."""
    values = values.dropna()
    return values.median() if len(values) else None


def attachment_point_excess(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Attachment point (Excess)": median Excess (USD), Excess layers only.

    A median, not an average - one huge tower would otherwise swamp it.
    Rows with no Excess figure are left out rather than counted as 0.
    """
    f = apply_scope(rbs, scope)
    return _median(f.loc[f["layer_type"] == "Excess", "excess"])


def attachment_point_primary(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Attachment point (Primary)": median Deductible (USD), Primary layers only.

    Catch written in the workbook: a blank deductible counts as 0, so this
    figure is often understated - on the real extract that halves it.

    Matt's build isn't directly comparable here (workbook tab 12): his
    attachment column is Excess + Deductible added together and then split by
    layer, and his own note says primary attachment is understated because a
    third of deductibles are blank.
    """
    f = apply_scope(rbs, scope)
    return _median(f.loc[f["layer_type"] == "Primary", "deductible"].fillna(0))


def median_limit(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Average Limit": median Agency Exposure (USD).

    Matt's build calls this "Average Limit", but it's a median - named
    "Median Limit" on screen from the start, as the workbook asks.
    """
    return _median(apply_scope(rbs, scope)["exposure"])


def rate_adequacy_rbs_benchmark(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 5, "Rate Adequacy double-check": RBS's own ready-made benchmark, as a percent.

    Mosaic 1609 share of premium / Mosaic 1609 share benchmark premium, over
    rows that carry a benchmark. Both columns are RBS's own figures, so this
    is an independent check on rate_adequacy() above, which rebuilds the
    benchmark from GELR and plan loss ratio.

    Why not the "Achieved Price (%)" column the workbook names: on the real
    extract its units are unclear (median about 1.3 after percent scaling,
    with outliers in the hundreds of thousands), so a sum of the two premium
    columns is used instead. Logged as an open question in workbook tab 9.
    """
    f = apply_scope(rbs, scope)
    if f["mosaic_1609_benchmark"].isna().all():
        return None
    rows = f[f["mosaic_1609_benchmark"].gt(0)]
    benchmark = rows["mosaic_1609_benchmark"].sum()
    if not benchmark:
        return None
    return 100 * rows["mosaic_1609_premium"].sum() / benchmark
