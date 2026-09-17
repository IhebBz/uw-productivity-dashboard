"""Lines up the two cleaned reports where a rule needs both at once.

clean_dsr.py and clean_rbs.py each clean one report on its own. The rules
here can only be applied once both are loaded, because they settle a
disagreement between DSR and RBS about the same policy.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def align_business_type(dsr: pd.DataFrame, rbs: pd.DataFrame) -> pd.DataFrame:
    """Overwrite DSR's New/Renewal with RBS's wherever a policy is in both.

    Metrics workbook, tab 3, Rule 2: DSR's Business Type and RBS's Renewal
    Status are filled in separately and don't always agree for the same
    policy - "when they disagree, we follow RBS's Renewal Status". Without
    this, a New/Renewal filter would select different policies in each
    report. Policies only in DSR (never won) keep DSR's own value, since RBS
    has nothing to say about them.

    If one RBS policy's lines carry different Renewal Status values, the
    most common one is used for the whole policy (a tie goes to the value
    that sorts first, e.g. "New" before "Renewal").
    """
    # Counted in one pass rather than a per-policy mode() - the per-policy
    # version took ~10 seconds on the real extract, which made every refresh
    # and every filter change slow.
    rbs_value = (
        rbs.dropna(subset=["policy_reference", "business_type"])
        .groupby(["policy_reference", "business_type"]).size()
        .rename("lines").reset_index()
        .sort_values(["policy_reference", "lines", "business_type"],
                     ascending=[True, False, True])
        .drop_duplicates("policy_reference")
        .set_index("policy_reference")["business_type"]
    )
    dsr = dsr.copy()
    from_rbs = dsr["policy_reference"].map(rbs_value)
    changed = from_rbs.notna() & from_rbs.ne(dsr["business_type"])
    if changed.any():
        logger.info(
            "DSR/RBS New-vs-Renewal: %d DSR rows (%d policies) disagreed with RBS "
            "and now follow RBS's Renewal Status (tab 3, Rule 2).",
            changed.sum(), dsr.loc[changed, "policy_reference"].nunique(),
        )
    dsr["business_type"] = from_rbs.where(from_rbs.notna(), dsr["business_type"])
    return dsr
