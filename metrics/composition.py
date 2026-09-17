"""What kind of book we write, and the new metrics added on top of Matt's
original build. See the metrics workbook, tab 4 "WHAT KIND OF BOOK WE WRITE"
and tab 5 "New ideas".
"""
import dataclasses

import pandas as pd

from config.settings import BROKER_CONCENTRATION_TOP_N
from scope.filter import Scope, apply_scope


def mosaic_as_lead(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Mosaic as Lead": rows where Mosaic is slip lead / all rows. A row count, not premium."""
    f = apply_scope(rbs, scope)
    if not len(f):
        return None
    is_lead = f["slip_lead"].astype(str).str.contains("Mosaic", case=False, na=False)
    return is_lead.mean()


def primary_share(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Primary Share": Primary rows / all rows. A row count, not premium."""
    f = apply_scope(rbs, scope)
    if not len(f):
        return None
    return (f["layer_type"] == "Primary").mean()


def new_vs_renewal_mix(rbs: pd.DataFrame, scope: Scope) -> dict:
    """Tab 5, "New vs. Renewal Mix": split of premium and count between New and Renewal.

    Built from RBS's Renewal Status, which is the value tab 3, Rule 2 says to
    follow when DSR and RBS disagree.

    Uses dropna=False so a row with a blank business_type still shows up as
    its own group instead of silently disappearing from the split - a
    dropped group would make the percentages look complete while quietly
    not summing to the true total.
    """
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    out = {}
    for label, group in f.groupby("business_type", dropna=False):
        key = label if pd.notna(label) else "(blank)"
        out[key] = {
            "premium": group["premium"].sum(),
            "premium_share": group["premium"].sum() / total if total else None,
            "count": len(group),
        }
    return out


def placement_mix(rbs: pd.DataFrame, scope: Scope) -> dict:
    """Tab 5, "Placement Mix": split of premium between Open Market, Facility/DUA, and Agreement.

    Uses dropna=False for the same reason as new_vs_renewal_mix above.
    """
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    out = {}
    for label, group in f.groupby("placement", dropna=False):
        key = label if pd.notna(label) else "(blank)"
        out[key] = group["premium"].sum() / total if total else None
    return out


def average_agency_share(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "Average Agency Share": premium-weighted Agency Line/Share, in percent units.

    Weighted by premium, as in Matt's build, so a big line on a big risk
    counts for more than a small line on a small one.
    """
    f = apply_scope(rbs, scope)
    f = f[f["agency_share"].notna()]
    total = f["premium"].sum()
    if not total:
        return None
    return (f["agency_share"] * f["premium"]).sum() / total


def scm_share(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 4, "SCM Share": 1 - (Mosaic 1609 share of premium / all agency premium). A 0-1 ratio.

    What's left once Mosaic's own balance sheet (syndicate 1609) is taken out
    is the share carried by third-party capital. A ratio of sums, not an
    average of per-row percentages.
    """
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    if not total or f["mosaic_1609_premium"].isna().all():
        return None
    return 1 - f["mosaic_1609_premium"].sum() / total


def broker_concentration(rbs: pd.DataFrame, scope: Scope,
                         top_n: int = BROKER_CONCENTRATION_TOP_N) -> float:
    """Tab 5, "Broker Concentration": top N brokers' premium / all premium. A 0-1 ratio.

    Brokers are ranked by premium within the scope. Rows with no broker name
    stay in the total but can't be one of the top brokers.
    """
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    if not total or f["broker"].isna().all():
        return None
    by_broker = f.groupby("broker")["premium"].sum().sort_values(ascending=False)
    return by_broker.head(top_n).sum() / total


def average_policy_length(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 5, "Average Policy Length": average Tenor in Months, one value per policy.

    Counted once per policy, not once per line (tab 3, Rule 4) - a policy
    with five lines would otherwise count five times.
    """
    f = apply_scope(rbs, scope).dropna(subset=["tenor_months"])
    if not len(f):
        return None
    return f.groupby("policy_reference")["tenor_months"].first().mean()


def renewal_premium_growth(rbs: pd.DataFrame, scope: Scope) -> float:
    """Tab 5, "Renewal Premium Growth": renewal premium / the same business's expiring premium.

    A 0-1+ ratio: 1.05 means 5% more premium came back than was expiring.
    Only renewals with a recorded expiring premium above zero count, on both
    sides. Like RARC, always renewals only, whatever the business type filter.

    Not a true retention rate (metrics workbook, tab 5): a policy that didn't
    renew leaves a DSR row but no RBS row, so the dollar figure here only
    covers renewals that did happen.
    """
    if rbs["expired_premium"].isna().all():
        return None
    f = apply_scope(rbs, dataclasses.replace(scope, business_type="Renewal"))
    f = f[f["expired_premium"].gt(0)]
    expiring = f["expired_premium"].sum()
    if not expiring:
        return None
    return f["premium"].sum() / expiring
