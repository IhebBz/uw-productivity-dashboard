"""Runs the full pipeline end to end: load from whichever DataSource is
configured, clean both reports, line them up (metrics workbook, tab 3),
compute every metric, and hand back one tidy dict for the dashboard front
end to read.

Split in two so the dashboard's filters stay fast:
- prepare(): read, clean and line up the two reports. Slow-ish, done once
  per data refresh.
- compute(): every metric for one set of filters. Run on each filter change.
build() does both, for one-off runs.

Called by run_pipeline_once.py and server/app.py. Everything it calls is
independently testable on its own.
"""
import dataclasses
import logging
from dataclasses import dataclass

import pandas as pd

from data_sources.base import DataSource
from scope.filter import Scope, INCEPTION, add_filter_columns
from scope.period import data_as_at, prior_year_scope, describe_period
from ingest.clean_dsr import clean_dsr
from ingest.clean_rbs import clean_rbs
from ingest.align_reports import align_business_type
from ingest.underwriter_names import display_names
from reconcile.cross_check import reconcile
from metrics import funnel, premium, quality, composition, headcount, underwriters

logger = logging.getLogger(__name__)

# Tab 1, point 5: every figure built on a headcount stand-in is labelled as
# one, and never called "headcount" without saying which version.
STAND_IN_NOTE = (
    "Stand-in, not true headcount (no HR file). Active underwriters = won at "
    "least one deal (RBS). Roster underwriters = at least one submission (DSR). "
    "Both leave out non-selling leaders, new joiners and people on leave, so "
    "per-person figures read a little better than the true figure."
)

# Tab 3, Rule 3: shown whenever the Date basis filter is on Submission.
SUBMISSION_BASIS_NOTE = (
    "Submission date basis: only figures from DSR alone are shown (Submissions, "
    "Quotes, Quote rate, Roster underwriters). Binds, premium and every RBS "
    "figure need Inception date basis - RBS has no submission date, and mixing "
    "the two would compare different months (workbook tab 3, Rule 3)."
)


@dataclass
class PreparedData:
    """Both reports cleaned and lined up, plus facts about the data itself."""
    dsr: pd.DataFrame
    rbs: pd.DataFrame
    as_at: pd.Timestamp
    underwriter_names: dict


def _cleaned_columns_only(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the raw report columns, keeping the shared names ingest/ created."""
    return df[[c for c in df.columns if isinstance(c, str) and c.isidentifier() and c.islower()]]


def prepare(data_source: DataSource) -> PreparedData:
    """Read, clean and line up DSR and RBS. No metrics computed here."""
    logger.info("Reading and cleaning DSR...")
    dsr = clean_dsr(data_source.get_dsr())

    logger.info("Reading and cleaning RBS...")
    rbs = clean_rbs(data_source.get_rbs())

    logger.info("Lining up DSR and RBS...")
    dsr = align_business_type(dsr, rbs)

    # Keep only the shared, cleaned columns (lower_case names), then add the
    # fast filter copies. Metrics never read a raw report column, and every
    # filter step copies whatever columns are left - with all ~160 raw RBS
    # columns kept, one filter change took about 5 seconds.
    dsr = add_filter_columns(_cleaned_columns_only(dsr))
    rbs = add_filter_columns(_cleaned_columns_only(rbs))

    return PreparedData(dsr=dsr, rbs=rbs, as_at=data_as_at(dsr),
                        underwriter_names=display_names(dsr, rbs))


def compute(data: PreparedData, scope: Scope) -> dict:
    """Every implemented metric for one Scope; return a dict.

    On submission-date basis, anything that needs RBS is None (not zero) and
    "basis_note" says why - see SUBMISSION_BASIS_NOTE.
    """
    dsr, rbs = data.dsr, data.rbs
    rbs_ok = scope.date_basis == INCEPTION

    def from_rbs(metric, *args):
        """Run an RBS-dependent metric, or return None on submission basis."""
        return metric(*args) if rbs_ok else None

    # Tab 3, Rule 6: bound premium and bind count worked out two ways and
    # compared; RBS's figure is the one kept.
    premium_check = binds_check = None
    if rbs_ok:
        premium_check = reconcile(
            dsr_value=premium.bound_premium_from_dsr(dsr, scope),
            rbs_value=premium.bound_premium(rbs, scope),
            label="bound premium",
        )
        binds_check = reconcile(
            dsr_value=funnel.binds_from_dsr(dsr, scope),
            rbs_value=funnel.binds_from_rbs(rbs, scope),
            label="bind count",
        )

    return {
        "scope": scope,
        "period_label": describe_period(scope),
        "basis_note": None if rbs_ok else SUBMISSION_BASIS_NOTE,
        "funnel": {
            "submissions": funnel.submissions(dsr, scope),
            "quotes": funnel.quotes(dsr, scope),
            "binds": binds_check.kept_value if binds_check else None,
            "binds_reconciliation": binds_check,
            "quote_rate": funnel.quote_rate(dsr, scope),
            "bind_rate": from_rbs(funnel.bind_rate, dsr, rbs, scope),
            "end_to_end_win_rate": from_rbs(funnel.end_to_end_win_rate, dsr, rbs, scope),
        },
        "premium": {
            "bound_premium": premium_check.kept_value if premium_check else None,
            "reconciliation": premium_check,
            "average_deal_size": from_rbs(premium.average_deal_size, rbs, scope),
        },
        "quality": {
            "gelr_book_basis": from_rbs(quality.gelr_book_basis, rbs, scope),
            "gelr_margin_basis": from_rbs(quality.gelr_margin_basis, rbs, scope),
            "commission_book_basis": from_rbs(quality.commission_book_basis, rbs, scope),
            "commission_margin_basis": from_rbs(quality.commission_margin_basis, rbs, scope),
            "uw_margin_pct": from_rbs(quality.uw_margin_pct, rbs, scope),
            "margin_cover": from_rbs(quality.margin_cover, rbs, scope),
            "commission_cover": from_rbs(quality.commission_cover, rbs, scope),
            "attachment_point_excess": from_rbs(quality.attachment_point_excess, rbs, scope),
            "attachment_point_primary": from_rbs(quality.attachment_point_primary, rbs, scope),
            "median_limit": from_rbs(quality.median_limit, rbs, scope),
        },
        "pricing": {
            "rate_adequacy": from_rbs(quality.rate_adequacy, rbs, scope),
            "rate_adequacy_rbs_benchmark": from_rbs(
                quality.rate_adequacy_rbs_benchmark, rbs, scope),
            "rarc": from_rbs(quality.rarc, rbs, scope),
        },
        "composition": {
            "mosaic_as_lead": from_rbs(composition.mosaic_as_lead, rbs, scope),
            "primary_share": from_rbs(composition.primary_share, rbs, scope),
            "average_agency_share": from_rbs(composition.average_agency_share, rbs, scope),
            "scm_share": from_rbs(composition.scm_share, rbs, scope),
            "new_vs_renewal_mix": from_rbs(composition.new_vs_renewal_mix, rbs, scope),
            "placement_mix": from_rbs(composition.placement_mix, rbs, scope),
            "broker_concentration": from_rbs(composition.broker_concentration, rbs, scope),
            "average_policy_length": from_rbs(composition.average_policy_length, rbs, scope),
            "renewal_premium_growth": from_rbs(composition.renewal_premium_growth, rbs, scope),
        },
        "productivity_stand_in": {
            "note": STAND_IN_NOTE,
            "active_underwriters_stand_in": from_rbs(headcount.active_underwriters, rbs, scope),
            "roster_underwriters_stand_in": headcount.roster_underwriters(dsr, scope),
            "premium_per_active_underwriter": from_rbs(
                headcount.premium_per_active_underwriter, rbs, scope),
            "premium_per_roster_underwriter": from_rbs(
                headcount.premium_per_roster_underwriter, dsr, rbs, scope),
            "uw_margin_per_active_underwriter": from_rbs(
                headcount.uw_margin_per_active_underwriter, rbs, scope),
        },
        # The peer group ignores the Underwriter filter: one underwriter
        # compared only against themselves would always read 1.0x. With a
        # name picked, the dashboard highlights their row among their peers.
        "underwriters": underwriters.underwriter_table(
            dsr, rbs if rbs_ok else None, dataclasses.replace(scope, underwriter=None),
            data.underwriter_names),
    }


def compute_with_comparison(data: PreparedData, scope: Scope) -> dict:
    """The selected period and the same period one year earlier, side by side."""
    prior = prior_year_scope(scope)
    return {
        "current": compute(data, scope),
        "prior": compute(data, prior) if prior is not None else None,
    }


def build(data_source: DataSource, scope: Scope) -> dict:
    """Prepare the data and compute every metric for one Scope; return a dict."""
    return compute(prepare(data_source), scope)
