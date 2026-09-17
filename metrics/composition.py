"""What kind of book we write, and the new metrics added on top of Matt's
original build. See the metrics workbook, tab 4 "WHAT KIND OF BOOK WE WRITE"
and tab 5 "New ideas".
"""
import pandas as pd

from scope.filter import Scope, apply_scope


def mosaic_as_lead(rbs: pd.DataFrame, scope: Scope) -> float:
    """Share of RBS rows where Mosaic is the slip lead. A row count, not premium-weighted."""
    f = apply_scope(rbs, scope)
    if not len(f):
        return None
    is_lead = f["slip_lead"].astype(str).str.contains("Mosaic", case=False, na=False)
    return is_lead.mean()


def primary_share(rbs: pd.DataFrame, scope: Scope) -> float:
    """Share of RBS rows written as primary layers. A row count, not premium-weighted."""
    f = apply_scope(rbs, scope)
    if not len(f):
        return None
    return (f["layer_type"] == "Primary").mean()


def new_vs_renewal_mix(rbs: pd.DataFrame, scope: Scope) -> dict:
    """Split of premium and count between New and Renewal business.

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
    """Split of premium between Open Market, Facility/DUA, and Agreement business.

    Uses dropna=False for the same reason as new_vs_renewal_mix above.
    """
    f = apply_scope(rbs, scope)
    total = f["premium"].sum()
    out = {}
    for label, group in f.groupby("placement", dropna=False):
        key = label if pd.notna(label) else "(blank)"
        out[key] = group["premium"].sum() / total if total else None
    return out


def broker_concentration(rbs: pd.DataFrame, scope: Scope, top_n: int = 5) -> float:
    """Share of premium held by the top N brokers by premium.

    Not implemented in this slice - Broker Name isn't in the standardized
    columns yet. Left as a clear next step rather than a silent gap.
    """
    raise NotImplementedError("Add 'Broker Name' to clean_rbs.py before using this.")


def average_policy_tenor(rbs: pd.DataFrame, scope: Scope) -> float:
    """Average policy length in months.

    Not implemented in this slice - Tenor in Months isn't in the
    standardized columns yet.
    """
    raise NotImplementedError("Add 'Tenor in Months' to clean_rbs.py before using this.")


def renewal_premium_growth(rbs: pd.DataFrame, scope: Scope) -> float:
    """Current renewal premium divided by the same business's prior expiring premium.

    Not a true retention rate - a policy that never renewed at all has no
    RBS row and so is invisible here (metrics workbook, tab 5). Not
    implemented in this slice - needs the 'Expired Gross Premium Agency
    (USD) of previous policy' column added to clean_rbs.py.
    """
    raise NotImplementedError("Add the expired-premium column to clean_rbs.py before using this.")
