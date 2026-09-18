"""Looking at one underwriter: the funnel, premium and book quality per
underwriter, plus how each compares to their peers. See the metrics
workbook, tab 4, "LOOKING AT ONE UNDERWRITER".

Every figure here uses the same definition as its whole-book version in
funnel.py, premium.py and quality.py - only grouped by underwriter, in one
pass, because calling those functions once per underwriter would take
minutes on the real extract. tests/test_underwriters.py checks that a row
here matches the whole-book function run for that one underwriter, so the
two can't drift apart unnoticed.

All subject to the name-spelling limitation in tab 3, Rule 5.
"""
import pandas as pd

from config.settings import QUOTED_STATUSES, PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM
from scope.filter import Scope, apply_scope


def _uw_margin_by_underwriter(rbs_in_scope: pd.DataFrame) -> pd.Series:
    """UW Margin % per underwriter: 100 - margin GELR - margin commission (usable-GELR rows)."""
    ok = rbs_in_scope[rbs_in_scope["gelr_ok"]].dropna(subset=["underwriter"])
    grouped = ok.assign(
        gelr_x_premium=ok["gelr"] * ok["premium"],
        commission_x_premium=ok["commission"] * ok["premium"],
    ).groupby("underwriter")[["premium", "gelr_x_premium", "commission_x_premium"]].sum()
    grouped = grouped[grouped["premium"] != 0]
    return (100 - grouped["gelr_x_premium"] / grouped["premium"]
            - grouped["commission_x_premium"] / grouped["premium"])


def _rate(numerator, denominator):
    """A ratio that is blank (None, not zero) when there's nothing to divide by."""
    return numerator / denominator if denominator else None


def underwriter_table(dsr: pd.DataFrame, rbs: pd.DataFrame, scope: Scope,
                      display_names: dict = None) -> dict:
    """One row per underwriter in scope, plus the peer median used for comparison.

    Pass rbs=None when the scope is on submission-date basis: RBS has no
    submission date (tab 3, Rule 3), so binds, premium and margin are blank.

    Peer comparison (tab 4): an underwriter's premium / the median premium of
    the underwriters in the table - themselves included, which keeps the
    median the same figure for everyone. The peer group is whoever is in the
    current filters. Whether zero-premium underwriters count towards the
    median is PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM in config/settings.py.
    Matt's build uses a stricter comparison (workbook tab 12).
    """
    display_names = display_names or {}
    dsr_s = apply_scope(dsr, scope).dropna(subset=["underwriter"])
    submissions = dsr_s.groupby("underwriter")["policy_reference"].nunique()
    quotes = (dsr_s[dsr_s["status"].isin(QUOTED_STATUSES)]
              .groupby("underwriter")["policy_reference"].nunique())

    if rbs is not None:
        rbs_all = apply_scope(rbs, scope)
        rbs_s = rbs_all.dropna(subset=["underwriter"])
        binds = rbs_s.groupby("underwriter")["policy_reference"].nunique()
        premium = rbs_s.groupby("underwriter")["premium"].sum()
        margin = _uw_margin_by_underwriter(rbs_all)
    else:
        binds = premium = margin = pd.Series(dtype=float)

    names = submissions.index.union(binds.index)
    peers = premium[premium > 0] if PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM else premium.reindex(names, fill_value=0)
    peer_median = peers.median() if len(peers) else None

    rows = []
    for key in names:
        s = int(submissions.get(key, 0))
        q = int(quotes.get(key, 0))
        b = int(binds.get(key, 0)) if rbs is not None else None
        p = float(premium.get(key, 0)) if rbs is not None else None
        rows.append({
            "underwriter": key,
            "name": display_names.get(key, key),
            "submissions": s,
            "quotes": q,
            "quote_rate": _rate(q, s),
            "binds": b,
            "bind_rate": _rate(b, q) if b is not None else None,
            "premium": p,
            "uw_margin_pct": float(margin[key]) if key in margin.index else None,
            "premium_vs_peer_median": _rate(p, peer_median) if p is not None else None,
        })
    rows.sort(key=lambda r: (-(r["premium"] or 0), -r["submissions"], r["name"]))
    return {"rows": rows, "peer_median_premium": peer_median}
