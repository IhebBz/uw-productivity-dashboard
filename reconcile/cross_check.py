"""Compares DSR's and RBS's own versions of a figure (bound premium, bind
count) over the same scope, and decides which one the dashboard shows.

RBS is the company's established source of truth for bound business (metrics
workbook, tab 3, Rules 6-7), so its figure is kept whenever the two disagree.
DSR's figure is still calculated every time and logged, so a large gap is
never hidden - it's a signal something upstream needs checking, not a bug to
paper over.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from config.settings import RECONCILIATION_TOLERANCE_PCT

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """Both competing figures, their gap, and which one the dashboard keeps.

    gap_pct is None when RBS's figure is zero and DSR's isn't - a
    percentage gap against a zero reference is undefined, not "100%" or any
    other number, and reporting a made-up figure there would be its own
    silent failure. is_undefined_gap says exactly why gap_pct is None.
    """
    dsr_value: float
    rbs_value: float
    gap_pct: Optional[float]
    kept_value: float
    flagged: bool
    is_undefined_gap: bool = False


def reconcile(dsr_value: float, rbs_value: float, label: str = "") -> ReconciliationResult:
    """Compare a DSR figure and an RBS figure for the same scope, keep RBS's.

    Logs a warning when the gap is past RECONCILIATION_TOLERANCE_PCT, so a
    background/unattended run still surfaces the problem instead of it only
    being visible to someone who happens to inspect the result later.
    """
    if rbs_value:
        gap_pct = abs(dsr_value - rbs_value) / abs(rbs_value)
        is_undefined = False
    elif not dsr_value:
        gap_pct = 0.0
        is_undefined = False
    else:
        gap_pct = None
        is_undefined = True

    flagged = is_undefined or (gap_pct is not None and gap_pct > RECONCILIATION_TOLERANCE_PCT)

    if flagged:
        gap_desc = "undefined (RBS is zero, DSR is not)" if is_undefined else f"{gap_pct:.1%}"
        logger.warning(
            "Reconciliation gap%s: DSR=%s, RBS=%s, gap=%s. Keeping RBS's value.",
            f" ({label})" if label else "", dsr_value, rbs_value, gap_desc,
        )

    return ReconciliationResult(
        dsr_value=dsr_value,
        rbs_value=rbs_value,
        gap_pct=gap_pct,
        kept_value=rbs_value,
        flagged=flagged,
        is_undefined_gap=is_undefined,
    )
