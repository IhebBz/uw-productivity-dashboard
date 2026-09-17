"""Turns a raw DSR export into a clean dataframe: dates parsed, one
underwriter attributed per row, and every column the pipeline uses renamed
onto the shared names in config/field_map.py. No metric is computed here -
only cleaning, so this stays reusable no matter what later reads it.

Standardizing column names here (rather than at filter/metric time) is what
lets scope/filter.py and every metrics/ function work identically on DSR and
RBS without ever needing to know which one they're looking at.
"""
import logging

import pandas as pd

from config.field_map import column_for
from ingest.validation import require_columns, warn_if_coercion_dropped_data

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Policy Reference", "XFI Policy Status", "Producing Underwriter Name",
    "Underwriter Name", "Producing Mosaic Entity", "Class Of Business",
    "Business Type", "Agency Share Gross Written Premium (USD)",
    "Inception date", "Submission Date", "Mapped Method of Placement (MOP)",
]


def clean_dsr(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns, parse dates, and attribute one underwriter per row.

    Raises a clear error naming the missing column(s) if the export has
    changed shape - a half-cleaned DSR is worse than a run that stops early.
    Logs a warning (does not raise) if converting premium or dates loses a
    meaningful share of real values - see ingest/validation.py.
    """
    require_columns(raw, REQUIRED_COLUMNS, "DSR")

    df = raw.copy()
    df["policy_reference"] = df["Policy Reference"]
    df["status"] = df["XFI Policy Status"]
    df["underwriter"] = df[column_for("underwriter", "dsr")].fillna(
        df[column_for("underwriter_fallback", "dsr")])
    df["entity"] = df[column_for("entity", "dsr")]
    df["line_of_business"] = df[column_for("line_of_business", "dsr")]
    df["business_type"] = df[column_for("business_type", "dsr")]
    df["placement"] = df[column_for("placement", "dsr")]

    raw_premium = df[column_for("premium", "dsr")]
    df["premium"] = pd.to_numeric(raw_premium, errors="coerce")
    warn_if_coercion_dropped_data(raw_premium, df["premium"], "DSR")
    df["premium"] = df["premium"].fillna(0)

    raw_inception = df[column_for("inception_date", "dsr")]
    df["inception_date"] = pd.to_datetime(raw_inception, errors="coerce")
    warn_if_coercion_dropped_data(raw_inception, df["inception_date"], "DSR")

    raw_submission = df[column_for("submission_date", "dsr")]
    df["submission_date"] = pd.to_datetime(raw_submission, errors="coerce")
    warn_if_coercion_dropped_data(raw_submission, df["submission_date"], "DSR")

    unattributed_rate = df["underwriter"].isna().mean()
    if unattributed_rate > 0.10:
        logger.warning(
            "DSR: %.1f%% of rows have no underwriter on either field. Any "
            "underwriter-level metric on this data will be measured on a "
            "shrunken, possibly unrepresentative population.",
            unattributed_rate * 100,
        )

    return df
