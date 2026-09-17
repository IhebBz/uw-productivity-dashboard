"""Turns a raw RBS export into a clean dataframe: dates parsed, one
underwriter attributed per row, percentage columns checked for consistent
units, and every column the pipeline uses renamed onto the shared names in
config/field_map.py. No metric is computed here - only cleaning.
"""
import logging

import pandas as pd

from config.field_map import column_for
from ingest.validation import require_columns, warn_if_coercion_dropped_data

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Class of Business", "Renewal Status", "Mapped Method of Placement (MOP)",
    "Type of Layer", "Agency Share Gross Written Premium (USD)",
    "Agency GELR (%)", "Business Plan Loss Ratio (%)", "Original Commission (%)",
    "Excess (USD)", "Deductible (USD)", "Agency Exposure (USD)", "Inception Date",
    "Slip Lead", "Producing Underwriter Name", "Underwriter Name",
    "Producing Mosaic Entity",
]

# Total Fees / Syndicate Fees / SCM Fees are deliberately NOT required here -
# they don't exist in the standard export (metrics workbook, tab 6). Agency
# Revenue stays out of scope until that changes.

PERCENT_COLUMN_ANCHORS = ["Agency GELR (%)", "Original Commission (%)",
                           "Business Plan Loss Ratio (%)"]

# Read but not required - if absent, rarc() degrades to None rather than
# stopping the whole run, since RARC is one metric among many, not
# load-bearing for the rest of the pipeline.
RARC_COLUMN = "Risk Adjusted Rate Change (%)"
EXPIRED_PREMIUM_COLUMN = "Expired Gross Premium Agency (USD) of previous policy"

# After scaling, a real book's GELR should sit somewhere in this range. If it
# doesn't, the unit decision below was wrong - stop rather than publish a
# GELR of 0.4% or 4000%, both of which have happened from this exact bug.
GELR_SANITY_RANGE = (5, 95)


def _percent_columns_to_percent_units(df: pd.DataFrame) -> pd.DataFrame:
    """Detect whether percent columns arrived as fractions (0.35) or already
    as percent units (35.0), and scale EVERY column whose name ends in
    "(%)" x100 if so - not just a hand-picked few, so a new percent column
    added to a future extract is covered automatically rather than silently
    missed because someone forgot to add it to a list here.

    Voting uses only the three columns known to always be populated
    (PERCENT_COLUMN_ANCHORS) - a thin column with few real values would be
    an unreliable vote either way. Detection: the 99th percentile of a
    column's non-zero values is under 3 for fractions, tens-to-hundreds for
    percent units. If the anchors genuinely disagree, that's a data problem
    worth stopping for, not a coin flip worth guessing at - a wrong guess
    here has previously produced a GELR of 0.4% that looked like an
    unbelievably good result rather than a broken one.
    """
    df = df.copy()
    percent_columns = [c for c in df.columns if isinstance(c, str) and c.strip().endswith("(%)")]

    votes = {}
    for col in PERCENT_COLUMN_ANCHORS:
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        vals = vals[vals != 0]
        if len(vals) < 20:
            continue  # not enough evidence from this column to vote either way
        votes[col] = "fraction" if vals.quantile(0.99) <= 3 else "percent"

    if not votes:
        logger.warning("RBS: none of the anchor percent columns had enough data to judge "
                        "units. Assuming they already arrived in percent units.")
        return df

    unique_votes = set(votes.values())
    if len(unique_votes) > 1:
        raise ValueError(
            f"RBS percent columns disagree on units: {votes}. Some look like fractions "
            f"(0.35) and others like percent units (35.0). Refusing to guess - fix the "
            f"extract, or confirm which columns are actually correct."
        )

    if unique_votes == {"fraction"}:
        for col in percent_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce") * 100
        logger.info("RBS: percent columns arrived as fractions, scaled x100 (%d columns).",
                    len(percent_columns))

    gelr_median = pd.to_numeric(df["Agency GELR (%)"], errors="coerce")
    gelr_median = gelr_median[gelr_median != 0].median()
    if gelr_median is not None and not pd.isna(gelr_median):
        if not (GELR_SANITY_RANGE[0] <= gelr_median <= GELR_SANITY_RANGE[1]):
            raise ValueError(
                f"RBS: median GELR is {gelr_median:.2f} after unit handling, expected "
                f"between {GELR_SANITY_RANGE[0]} and {GELR_SANITY_RANGE[1]}. The unit "
                f"decision above is probably wrong - do not trust this data."
            )
    return df


def clean_rbs(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns, parse dates, attribute one underwriter per
    row, and normalise percentage columns to consistent units.
    """
    require_columns(raw, REQUIRED_COLUMNS, "RBS")

    df = _percent_columns_to_percent_units(raw)
    df["policy_reference"] = df["Policy Reference"] if "Policy Reference" in df.columns else None
    df["underwriter"] = df[column_for("underwriter", "rbs")].fillna(
        df[column_for("underwriter_fallback", "rbs")])
    df["entity"] = df[column_for("entity", "rbs")]
    df["line_of_business"] = df[column_for("line_of_business", "rbs")]
    df["business_type"] = df[column_for("business_type", "rbs")]
    df["placement"] = df[column_for("placement", "rbs")]

    raw_premium = df[column_for("premium", "rbs")]
    df["premium"] = pd.to_numeric(raw_premium, errors="coerce")
    warn_if_coercion_dropped_data(raw_premium, df["premium"], "RBS")
    df["premium"] = df["premium"].fillna(0)

    raw_inception = df[column_for("inception_date", "rbs")]
    df["inception_date"] = pd.to_datetime(raw_inception, errors="coerce")
    warn_if_coercion_dropped_data(raw_inception, df["inception_date"], "RBS")

    df["gelr"] = pd.to_numeric(df["Agency GELR (%)"], errors="coerce")
    df["gelr_ok"] = df["gelr"].notna() & df["gelr"].ne(0)
    # Blank commission = 0 is a stated business rule (metrics workbook, tab 4),
    # not a shortcut - Original Commission (%) being genuinely absent means no
    # commission was charged, so it isn't the same kind of gap as a premium or
    # date failing to parse, and is filled here without a warning on purpose.
    df["commission"] = pd.to_numeric(df["Original Commission (%)"], errors="coerce").fillna(0)
    df["plan_loss_ratio"] = pd.to_numeric(df["Business Plan Loss Ratio (%)"], errors="coerce")
    df["layer_type"] = df["Type of Layer"]
    df["slip_lead"] = df["Slip Lead"]

    # Both optional: not every extract carries them, and RARC is one metric
    # among many rather than something the rest of the pipeline depends on.
    df["rarc"] = pd.to_numeric(df[RARC_COLUMN], errors="coerce") if RARC_COLUMN in df.columns \
        else None
    df["expired_premium"] = pd.to_numeric(df[EXPIRED_PREMIUM_COLUMN], errors="coerce") \
        if EXPIRED_PREMIUM_COLUMN in df.columns else None
    return df
