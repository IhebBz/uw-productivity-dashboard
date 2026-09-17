"""Small validation helpers shared by clean_dsr.py and clean_rbs.py.

Pulled out on purpose: both cleaning modules need the same two checks
(required columns present, a numeric/date conversion didn't quietly drop
data), and duplicating this logic in two places is exactly how one copy
gets fixed later and the other doesn't.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def require_columns(df: pd.DataFrame, required: list, label: str) -> None:
    """Raise a clear error naming every missing column, or do nothing if all are present."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"{label} is missing required column(s): {missing}")


def warn_if_coercion_dropped_data(raw: pd.Series, coerced: pd.Series, label: str,
                                   threshold: float = 0.02) -> None:
    """Log a warning if converting a column to numbers/dates silently lost real values.

    pd.to_numeric(..., errors="coerce") and pd.to_datetime(..., errors="coerce")
    both turn anything they can't parse into NaN/NaT with no error raised. A
    genuinely blank cell becoming NaN is normal; a cell that HAD a value and
    lost it during conversion is a silent data problem, and is exactly the
    kind of thing that should never pass unnoticed into a metric.
    """
    was_present = raw.notna()
    now_missing = coerced.isna()
    newly_lost = (was_present & now_missing).sum()
    if was_present.sum() == 0:
        return
    lost_rate = newly_lost / was_present.sum()
    if lost_rate > threshold:
        logger.warning(
            "%s: %d of %d non-blank values in '%s' could not be parsed and became "
            "blank (%.1f%%). Check the source format hasn't changed.",
            label, newly_lost, was_present.sum(), raw.name, lost_rate * 100,
        )
