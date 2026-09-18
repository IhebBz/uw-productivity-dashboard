"""Turns a raw RBS export into a clean dataframe: dates parsed, one
underwriter attributed per row, percentage columns checked for consistent
units, and every column the pipeline uses renamed onto the shared names in
config/field_map.py. No metric is computed here - only cleaning.
"""
import logging

import pandas as pd

from config.field_map import column_for, normalise_entity
from ingest.underwriter_names import normalise_underwriter_name
from ingest.validation import require_columns, warn_if_coercion_dropped_data

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Class of Business", "Renewal Status", "Mapped Method of Placement (MOP)",
    "Type of Layer", "Agency Share Gross Written Premium (USD)",
    "Agency GELR (%)", "Business Plan Loss Ratio (%)", "Original Commission (%)",
    "Excess (USD)", "Deductible (USD)", "Agency Exposure (USD)", "Inception Date",
    "Slip Lead", "Producing Underwriter Name", "Underwriter Name",
    "Producing Mosaic Entity", "Policy Reference",
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

# Read but not required, same reasoning as RARC above. Shared name -> raw
# RBS column. Each feeds one metric; see the metrics workbook, tab 8.
OPTIONAL_COLUMNS = {
    "agency_share": "Agency Line/Share (%)",                               # Average Agency Share
    "mosaic_1609_premium": "Mosaic 1609 Share Gross Written Premium (USD)",  # SCM Share
    "mosaic_1609_benchmark": "Mosaic 1609 Share Benchmark Premium (USD)",    # Rate Adequacy double-check
    "broker": "Broker Name",                                              # Broker Concentration
    "tenor_months": "Tenor in Months",                                    # Average Policy Length
}

# After scaling, a real book's GELR should sit somewhere in this range. If it
# doesn't, the unit decision below was wrong - stop rather than publish a
# GELR of 0.4% or 4000%, both of which have happened from this exact bug.
GELR_SANITY_RANGE = (5, 95)

# A renewal rate change beyond this (in percent units) isn't a plausible price
# move and is worth a warning - see the end of clean_rbs().
RARC_EXTREME_PCT = 300


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
    # Required, not optional: every bind count (tab 4, "Binds") is a count of
    # distinct Policy References, so without it binds would silently read 0.
    df["policy_reference"] = df[column_for("policy_reference", "rbs")]
    # Tab 3, Rule 5 - same name clean-up as clean_dsr.py, so both sides match.
    df["underwriter_raw"] = df[column_for("underwriter", "rbs")].fillna(
        df[column_for("underwriter_fallback", "rbs")])
    df["underwriter"] = df["underwriter_raw"].map(normalise_underwriter_name)
    df["entity"] = df[column_for("entity", "rbs")].map(normalise_entity)
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

    # gelr keeps its blanks - the margin version of GELR (tab 4) needs to tell a
    # blank apart from a real figure. gelr_ok marks "a usable GELR figure".
    df["gelr"] = pd.to_numeric(df["Agency GELR (%)"], errors="coerce")
    df["gelr_ok"] = df["gelr"].notna() & df["gelr"].ne(0)
    # Commission is filled with 0 here because tab 4 defines the book version
    # as an average "across all rows" - a blank row still counts, as no
    # recorded commission. The same treatment is applied to GELR's book
    # version in metrics/quality.py.
    df["commission"] = pd.to_numeric(df["Original Commission (%)"], errors="coerce").fillna(0)
    df["plan_loss_ratio"] = pd.to_numeric(df["Business Plan Loss Ratio (%)"], errors="coerce")
    df["layer_type"] = df["Type of Layer"]
    df["slip_lead"] = df["Slip Lead"]
    # Attachment point and limit (tab 4). Deductible keeps its blanks here;
    # the Primary attachment point treats a blank as 0 in metrics/quality.py,
    # where that catch is written down next to the figure it affects.
    df["excess"] = pd.to_numeric(df["Excess (USD)"], errors="coerce")
    df["deductible"] = pd.to_numeric(df["Deductible (USD)"], errors="coerce")
    df["exposure"] = pd.to_numeric(df["Agency Exposure (USD)"], errors="coerce")

    # Optional columns for the rest of tab 4 and tab 5. A missing one turns
    # its own metric blank rather than stopping the whole run.
    for name, column in OPTIONAL_COLUMNS.items():
        if column not in df.columns:
            logger.warning("RBS: column '%s' not in this extract - %s will be blank.",
                           column, name)
            df[name] = None
        elif name == "broker":
            df[name] = df[column]
        else:
            df[name] = pd.to_numeric(df[column], errors="coerce")

    # Both optional: not every extract carries them, and RARC is one metric
    # among many rather than something the rest of the pipeline depends on.
    df["rarc"] = pd.to_numeric(df[RARC_COLUMN], errors="coerce") if RARC_COLUMN in df.columns \
        else None
    df["expired_premium"] = pd.to_numeric(df[EXPIRED_PREMIUM_COLUMN], errors="coerce") \
        if EXPIRED_PREMIUM_COLUMN in df.columns else None

    # RARC is a premium-weighted average with no cap, so a handful of extreme
    # rows can set the headline. The unit check above only looks at the MIDDLE
    # value, so it can't catch them (metrics workbook, tab 9, question 28).
    if pd.api.types.is_numeric_dtype(df["rarc"]):
        extreme = df["rarc"].abs() > RARC_EXTREME_PCT
        if extreme.any():
            logger.warning(
                "RBS: %d rows have a Risk Adjusted Rate Change beyond +/-%d%% (largest %.0f%%). They "
                "are included in RARC as they are - on the real extract, dropping them moves RARC by "
                "about 1.7 points.",
                int(extreme.sum()), RARC_EXTREME_PCT, df.loc[extreme, "rarc"].abs().max())
    return df
