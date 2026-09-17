"""Runs the full pipeline end to end: load from whichever DataSource is
configured, clean both reports, compute every metric, and hand back one
tidy dict for the dashboard front end to read.

This is the only file that should ever be run directly. Everything it calls
is independently testable on its own.
"""
from config.settings import BIND_STATUSES
from data_sources.base import DataSource
from scope.filter import Scope, apply_scope
from ingest.clean_dsr import clean_dsr
from ingest.clean_rbs import clean_rbs
from reconcile.cross_check import reconcile
from metrics import funnel, quality, composition, headcount

import logging
logger = logging.getLogger(__name__)

def build(data_source: DataSource, scope: Scope) -> dict:
    """Run ingest and every implemented metric for one Scope; return a dict."""
    logger.info("Reading and cleaning DSR...")
    dsr = clean_dsr(data_source.get_dsr())

    logger.info("Reading and cleaning RBS...")
    rbs = clean_rbs(data_source.get_rbs())

    logger.info("Computing metrics...")
    dsr_in_scope = apply_scope(dsr, scope)
    dsr_bound_premium = dsr_in_scope.loc[
        dsr_in_scope["status"].isin(BIND_STATUSES), "premium"].sum()

    premium_check = reconcile(
        dsr_value=dsr_bound_premium,
        rbs_value=apply_scope(rbs, scope)["premium"].sum(),
        label="bound premium",
    )
    binds_check = reconcile(
        dsr_value=funnel.binds_from_dsr(dsr, scope),
        rbs_value=funnel.binds_from_rbs(rbs, scope),
        label="bind count",
    )

    return {
        "scope": scope,
        "funnel": {
            "submissions": funnel.submissions(dsr, scope),
            "quotes": funnel.quotes(dsr, scope),
            "binds": binds_check.kept_value,
            "binds_reconciliation": binds_check,
            "quote_rate": funnel.quote_rate(dsr, scope),
            "bind_rate": funnel.bind_rate(dsr, rbs, scope),
            "end_to_end_win_rate": funnel.end_to_end_win_rate(dsr, rbs, scope),
        },
        "premium": {
            "bound_premium": premium_check.kept_value,
            "reconciliation": premium_check,
        },
        "quality": {
            "gelr_book_basis": quality.gelr_book_basis(rbs, scope),
            "gelr_margin_basis": quality.gelr_margin_basis(rbs, scope),
            "commission_book_basis": quality.commission_book_basis(rbs, scope),
            "commission_margin_basis": quality.commission_margin_basis(rbs, scope),
            "uw_margin_pct": quality.uw_margin_pct(rbs, scope),
            "margin_cover": quality.margin_cover(rbs, scope),
            "commission_cover": quality.commission_cover(rbs, scope),
            "rate_adequacy": quality.rate_adequacy(rbs, scope),
            "rarc": quality.rarc(rbs, scope),
        },
        "composition": {
            "mosaic_as_lead": composition.mosaic_as_lead(rbs, scope),
            "primary_share": composition.primary_share(rbs, scope),
            "new_vs_renewal_mix": composition.new_vs_renewal_mix(rbs, scope),
            "placement_mix": composition.placement_mix(rbs, scope),
        },
        "headcount": {
            "active_underwriters": headcount.active_underwriters(rbs, scope),
            "roster_underwriters": headcount.roster_underwriters(dsr, scope),
            "premium_per_active_underwriter": headcount.premium_per_active_underwriter(
                rbs, scope),
            "uw_margin_per_active_underwriter": headcount.uw_margin_per_active_underwriter(
                rbs, scope),
        },
    }
