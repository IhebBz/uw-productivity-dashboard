"""Where every dashboard figure comes from, in plain English.

For each figure: the original DSR / RBS column names it is built from, what
the pipeline does to each of those columns on the way in, which rows count,
and the formula. This is the ONE place that's written down - the dashboard's
help hover (server/dashboard.py), the metrics workbook's tabs 10 and 11
(docs/update_lineage_tabs.py) and tests/test_lineage.py all read it.

Column names come from config/field_map.py and ingest/ wherever the code
already names them, so this can't quietly disagree with what the pipeline
reads. tests/test_lineage.py fails if a figure on the page has no entry here,
or if a column here isn't one the pipeline reads (or the other way round).

When you change how a metric or a column is handled: change the code, then
this file, then rerun docs/update_lineage_tabs.py.
"""
from dataclasses import dataclass, field

from config.field_map import ENTITY_ALIASES, column_for
from config.settings import (BIND_STATUSES, BROKER_CONCENTRATION_TOP_N,
                             PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM, QUOTED_STATUSES)
from ingest.clean_rbs import EXPIRED_PREMIUM_COLUMN, OPTIONAL_COLUMNS, RARC_COLUMN

DSR, RBS = "DSR", "RBS"

# The export stores percentages as fractions; this is what the pipeline does about it.
# (ingest/clean_rbs.py decides this by checking GELR, Commission and Plan Loss Ratio together, and
# stops the refresh if they disagree or the middle GELR ends up outside 5-95%.)
PERCENT_STEP = ("Stored in the export as a fraction (0.40); multiplied by 100 to read as 40.0%. "
                "The refresh stops if the percentage columns don't agree on this.")


@dataclass
class SourceColumn:
    """One idea the pipeline reads from the exports, e.g. premium."""
    label: str                       # plain-English name
    dsr: tuple = ()                  # original DSR column name(s), in the order they're used
    rbs: tuple = ()                  # original RBS column name(s)
    steps: list = field(default_factory=list)      # what happens to it, on both reports
    dsr_steps: list = field(default_factory=list)  # extra steps on DSR only
    rbs_steps: list = field(default_factory=list)  # extra steps on RBS only
    required: bool = True            # False: if missing, only the figures using it go blank

    def raw(self, report):
        return self.dsr if report == DSR else self.rbs

    def steps_for(self, report):
        return self.steps + (self.dsr_steps if report == DSR else self.rbs_steps)


def _both(concept):
    """The DSR and RBS column names for a concept in config/field_map.py."""
    dsr, rbs = column_for(concept, "dsr"), column_for(concept, "rbs")
    return ((dsr,) if dsr else ()), ((rbs,) if rbs else ())


def _statuses(statuses):
    return ", ".join(sorted(statuses))


_uw_dsr = (column_for("underwriter", "dsr"), column_for("underwriter_fallback", "dsr"))
_uw_rbs = (column_for("underwriter", "rbs"), column_for("underwriter_fallback", "rbs"))

# Shared name in the code -> where it comes from and what happens to it.
COLUMNS = {
    "policy_reference": SourceColumn(
        "Policy", *_both("policy_reference"), steps=["Used as it is."]),
    "status": SourceColumn(
        "Policy status", dsr=_both("status")[0],
        steps=["Used as it is.",
               f"Counts as a quote if it is one of: {_statuses(QUOTED_STATUSES)}.",
               f"Counts as bound if it is one of: {_statuses(BIND_STATUSES)}."]),
    "underwriter": SourceColumn(
        "Underwriter", dsr=_uw_dsr, rbs=_uw_rbs,
        steps=[f"Takes {_uw_dsr[0]}; where that's blank, {_uw_dsr[1]}.",
               "For matching: lower-cased, punctuation and extra spaces removed, so \"SMITH, Jane\" "
               "and \"smith jane\" are one person. A name typed two genuinely different ways still "
               "counts as two people (workbook tab 3, Rule 5).",
               "Shown on screen with the most common original spelling."]),
    "entity": SourceColumn(
        "Entity", *_both("entity"),
        steps=["Extra spaces removed."],
        dsr_steps=["Renamed to RBS's spelling: " + "; ".join(
            f"\"{k}\" -> \"{v}\"" for k, v in ENTITY_ALIASES.items()) + "."]),
    "line_of_business": SourceColumn(
        "Line of business", *_both("line_of_business"), steps=["Used as it is."]),
    "business_type": SourceColumn(
        "New or renewal", *_both("business_type"),
        dsr_steps=["Where the same policy is also in RBS and the two disagree, replaced by RBS's "
                   "Renewal Status (the most common value across that policy's RBS lines). "
                   "Policies only in DSR keep their own value (workbook tab 3, Rule 2)."],
        rbs_steps=["Used as it is."]),
    "placement": SourceColumn(
        "Placement", *_both("placement"), steps=["Used as it is."]),
    "inception_date": SourceColumn(
        "Inception date", *_both("inception_date"),
        steps=["Read as a date. A value that can't be read leaves the row out of every period "
               "(a warning is logged if more than 2% fail)."]),
    "submission_date": SourceColumn(
        "Submission date", dsr=_both("submission_date")[0],
        steps=["Read as a date, as above. Also sets \"data as at\" (the latest submission)."]),
    "premium": SourceColumn(
        "Premium", *_both("premium"),
        steps=["Read as a number.",
               "Blank counts as $0 (a warning is logged if more than 2% of filled cells can't be "
               "read as numbers).",
               "Negative values (e.g. return premium) are kept, so totals are net."]),
    "gelr": SourceColumn(
        "Expected loss ratio (GELR)", rbs=("Agency GELR (%)",),
        steps=[PERCENT_STEP, "Blanks kept as blank.",
               "\"Usable GELR\" = not blank and not exactly 0."]),
    "commission": SourceColumn(
        "Commission", rbs=("Original Commission (%)",),
        steps=[PERCENT_STEP, "Blank counts as 0 (no commission)."]),
    "plan_loss_ratio": SourceColumn(
        "Plan loss ratio", rbs=("Business Plan Loss Ratio (%)",),
        steps=[PERCENT_STEP, "Blanks kept as blank."]),
    "layer_type": SourceColumn(
        "Layer", rbs=("Type of Layer",), steps=["Used as it is (Primary / Excess / Quota Share)."]),
    "slip_lead": SourceColumn(
        "Slip lead", rbs=("Slip Lead",),
        steps=["Used as it is. Counts as Mosaic when the text contains \"Mosaic\" (any capitals)."]),
    "excess": SourceColumn(
        "Excess", rbs=("Excess (USD)",), steps=["Read as a number; blanks kept as blank."]),
    "deductible": SourceColumn(
        "Deductible", rbs=("Deductible (USD)",), steps=["Read as a number; blanks kept as blank."]),
    "exposure": SourceColumn(
        "Exposure (limit)", rbs=("Agency Exposure (USD)",),
        steps=["Read as a number; blanks kept as blank."]),
    "agency_share": SourceColumn(
        "Agency line share", rbs=(OPTIONAL_COLUMNS["agency_share"],),
        steps=[PERCENT_STEP, "Blanks kept as blank."], required=False),
    "mosaic_1609_premium": SourceColumn(
        "Mosaic 1609 premium", rbs=(OPTIONAL_COLUMNS["mosaic_1609_premium"],),
        steps=["Read as a number; blanks kept as blank (add nothing to a total)."], required=False),
    "mosaic_1609_benchmark": SourceColumn(
        "Mosaic 1609 benchmark premium", rbs=(OPTIONAL_COLUMNS["mosaic_1609_benchmark"],),
        steps=["Read as a number; blanks kept as blank."], required=False),
    "broker": SourceColumn(
        "Broker", rbs=(OPTIONAL_COLUMNS["broker"],),
        steps=["Used exactly as typed - one broker spelled two ways counts as two."], required=False),
    "tenor_months": SourceColumn(
        "Policy length", rbs=(OPTIONAL_COLUMNS["tenor_months"],),
        steps=["Read as a number; blanks kept as blank."], required=False),
    "rarc": SourceColumn(
        "Rate change (RARC)", rbs=(RARC_COLUMN,),
        steps=[PERCENT_STEP, "Blanks kept as blank. 100% = rate unchanged."], required=False),
    "expired_premium": SourceColumn(
        "Expiring premium", rbs=(EXPIRED_PREMIUM_COLUMN,),
        steps=["Read as a number; blanks kept as blank."], required=False),
}

# The columns every filter uses - they narrow the rows before any figure is worked out.
FILTER_COLUMNS = ["inception_date", "submission_date", "business_type", "placement",
                  "line_of_business", "entity", "underwriter"]


@dataclass
class Metric:
    """One figure on the dashboard."""
    title: str
    meaning: str                 # what it tells you, in a sentence
    formula: str                 # how it's worked out
    rows: str                    # which rows count
    columns: list                # [(report, shared column name), ...]
    code: str                    # where the calculation lives
    counted_per: str = "Line"    # Line, Policy or Person
    catches: list = field(default_factory=list)
    traced: bool = True          # rebuilt from raw columns by tests/test_trace_to_source.py
    workbook: str = "Tab 4"
    check_note: str = None       # when not traced: why, and what it relies on instead

    def reports(self):
        return sorted({report for report, _ in self.columns})


P = "premium"
_rbs_premium = [(RBS, "policy_reference"), (RBS, P)]
_usable = "Only RBS rows with a usable GELR (not blank, not 0)."
_all_rbs = "Every RBS row left after your filters."
_all_dsr = "Every DSR row left after your filters, whatever its status."

METRICS = {
    # ---- The funnel -------------------------------------------------------
    "funnel.submissions": Metric(
        "Submissions", "How many risks came in, won or not.",
        "Number of different policies.", _all_dsr, [(DSR, "policy_reference")],
        "metrics/funnel.py submissions", "Policy"),
    "funnel.quotes": Metric(
        "Quotes", "How many risks we priced.",
        "Number of different policies with a quote status.",
        "DSR rows whose status counts as a quote.", [(DSR, "policy_reference"), (DSR, "status")],
        "metrics/funnel.py quotes", "Policy",
        catches=["A status that appears in the export for the first time is NOT a quote until it's "
                 "added to QUOTED_STATUSES in config/settings.py."]),
    "funnel.binds": Metric(
        "Binds", "How many risks we won.",
        "Number of different policies in RBS.",
        _all_rbs + " Every RBS row is a won risk.", [(RBS, "policy_reference")],
        "metrics/funnel.py binds_from_rbs", "Policy",
        catches=["Cross-checked against DSR's own count (policies with a bound status). A red badge "
                 "means they're more than 2% apart; RBS's figure is the one shown.",
                 "Matt's build counts binds from DSR's statuses instead, so his bind count is our "
                 "cross-check figure (workbook tab 12)."]),
    "funnel.quote_rate": Metric(
        "Quote rate (Q/S)", "Of everything that came in, the share we priced.",
        "Quotes ÷ Submissions.", _all_dsr, [(DSR, "policy_reference"), (DSR, "status")],
        "metrics/funnel.py quote_rate", "Policy",
        catches=["Blank (not 0%) when there are no submissions."]),
    "funnel.bind_rate": Metric(
        "Win rate (B/Q)", "Of everything we priced, the share we won.",
        "Binds (from RBS) ÷ Quotes (from DSR).", "As Binds and Quotes.",
        [(RBS, "policy_reference"), (DSR, "policy_reference"), (DSR, "status")],
        "metrics/funnel.py bind_rate", "Policy",
        catches=["Mixes the two reports on purpose: RBS is the source of truth for wins.",
                 "Blank when there are no quotes, and on Submission date basis.",
                 "Overstated wherever RBS holds a bound policy DSR has no record of - the page says "
                 "how many and what the rate would be without them (open question 26). On a narrow "
                 "slice or one underwriter it can pass 100%."]),
    "funnel.end_to_end_win_rate": Metric(
        "End-to-end win rate (B/S)", "Of everything that came in, the share we won.",
        "Binds (from RBS) ÷ Submissions (from DSR).", "As Binds and Submissions.",
        [(RBS, "policy_reference"), (DSR, "policy_reference")],
        "metrics/funnel.py end_to_end_win_rate", "Policy",
        catches=["Blank when there are no submissions, and on Submission date basis.",
                 "Overstated for the same reason as B/Q: some bound policies have no DSR row "
                 "(open question 26)."]),
    # ---- How much we wrote ------------------------------------------------
    "premium.bound_premium": Metric(
        "Bound Premium", "Total premium on business we won.",
        "Sum of premium across every line of every policy.", _all_rbs, [(RBS, P)],
        "metrics/premium.py bound_premium",
        catches=["Summed across every line first, never after collapsing to one row per policy "
                 "(workbook tab 3, Rule 4).",
                 "Matt's headline premium comes from DSR, not RBS - his figure is the cross-check "
                 "below, and every per-person and deal-size figure of his sits on that base "
                 "(workbook tab 12).",
                 "Cross-checked against DSR: the same premium column on DSR rows with a bound "
                 "status. A red badge means more than 2% apart; RBS's figure is shown."]),
    "premium.average_deal_size": Metric(
        "Average Deal Size", "The average premium on a won policy.",
        "Bound Premium ÷ Binds.", _all_rbs, _rbs_premium,
        "metrics/premium.py average_deal_size", "Policy",
        catches=["Blank when there are no binds."]),
    # ---- How good the business is -----------------------------------------
    "quality.uw_margin_pct": Metric(
        "UW Margin %", "What's left of each premium dollar after expected claims and commission.",
        "100% − GELR (margin version) − Commission (margin version).", _usable,
        [(RBS, "gelr"), (RBS, "commission"), (RBS, P)], "metrics/quality.py uw_margin_pct",
        catches=["Mosaic's own internal commission is NOT subtracted - open question 2.",
                 "A blank or zero commission counts as \"none charged\" while a blank or zero GELR is "
                 "treated as unusable and left out, so the two halves handle a missing value in "
                 "opposite ways and the margin reads high. The page says by how much "
                 "(open question 25)."]),
    "quality.gelr_book_basis": Metric(
        "GELR – book version", "Expected share of premium paid out in claims, across the whole book.",
        "Σ(GELR × premium) ÷ Σ premium.", _all_rbs, [(RBS, "gelr"), (RBS, P)],
        "metrics/quality.py gelr_book_basis",
        catches=["A blank GELR counts as 0 here, which pulls the figure down - open question, "
                 "workbook tab 9.",
                 "Matt's build has no book version: his single GELR matches our margin version, and "
                 "also drops 2021 inceptions, which we don't (workbook tab 12)."]),
    "quality.gelr_margin_basis": Metric(
        "GELR – margin version", "Expected claims share, on exactly the rows UW Margin % uses.",
        "Σ(GELR × premium) ÷ Σ premium.", _usable, [(RBS, "gelr"), (RBS, P)],
        "metrics/quality.py gelr_margin_basis"),
    "quality.commission_book_basis": Metric(
        "Commission – book version", "Share of premium paid away as commission, whole book.",
        "Σ(commission × premium) ÷ Σ premium.", _all_rbs,
        [(RBS, "commission"), (RBS, P)], "metrics/quality.py commission_book_basis"),
    "quality.commission_margin_basis": Metric(
        "Commission – margin version", "Commission share, on exactly the rows UW Margin % uses.",
        "Σ(commission × premium) ÷ Σ premium.", _usable,
        [(RBS, "commission"), (RBS, "gelr"), (RBS, P)], "metrics/quality.py commission_margin_basis"),
    "quality.uw_margin_pct_recorded_commission": Metric(
        "UW Margin % over rows that record a commission",
        "A check on UW Margin %: the same figure over the rows that actually record a commission.",
        "100% − GELR − Commission, over usable-GELR rows with a commission above 0.",
        "RBS rows with a usable GELR AND a commission above 0.",
        [(RBS, "gelr"), (RBS, "commission"), (RBS, P)],
        "metrics/quality.py uw_margin_pct_recorded_commission", traced=False,
        check_note="A variant of UW Margin %, which is itself checked against the raw columns.",
        catches=["Shown only as a note under UW Margin %, never as a headline: it drops real "
                 "zero-commission business, which exists.",
                 "The gap between the two is what the \"blank commission = none charged\" rule is "
                 "worth - open question 25."]),
    "quality.margin_cover": Metric(
        "Margin cover", "How much of the premium UW Margin % is actually based on.",
        "Premium on rows with a usable GELR ÷ all premium.", _all_rbs,
        [(RBS, "gelr"), (RBS, P)], "metrics/quality.py margin_cover"),
    "quality.commission_cover": Metric(
        "Commission cover", "How much of the margin premium has a commission recorded.",
        "Premium on those rows with commission above 0 ÷ their premium.", _usable,
        [(RBS, "commission"), (RBS, "gelr"), (RBS, P)], "metrics/quality.py commission_cover"),
    "quality.attachment_point_excess": Metric(
        "Median attachment point – Excess", "The typical loss level before an excess layer pays.",
        "Middle value (median) of Excess.", "RBS rows whose layer is Excess.",
        [(RBS, "excess"), (RBS, "layer_type")], "metrics/quality.py attachment_point_excess",
        catches=["Rows with a blank Excess are left out."]),
    "quality.attachment_point_primary": Metric(
        "Median attachment point – Primary", "The typical loss level before a primary layer pays.",
        "Middle value (median) of Deductible.", "RBS rows whose layer is Primary.",
        [(RBS, "deductible"), (RBS, "layer_type")], "metrics/quality.py attachment_point_primary",
        catches=["A blank deductible counts as 0 (many Primary rows are blank), so this is often "
                 "understated - on the real extract it halves the figure.",
                 "Not directly comparable with Matt's build, which adds Excess and Deductible "
                 "together before splitting by layer (workbook tab 12)."]),
    "quality.median_limit": Metric(
        "Median limit", "The typical size of cover we're on the hook for.",
        "Middle value (median) of Exposure.", _all_rbs, [(RBS, "exposure")],
        "metrics/quality.py median_limit",
        catches=["Rows with a blank exposure are left out.",
                 "Matt's build calls this \"Average Limit\", but it's a median."]),
    # ---- Pricing -----------------------------------------------------------
    "pricing.rate_adequacy": Metric(
        "Rate Adequacy", "Are we charging enough compared with plan? Above 100% = above plan.",
        "Σ premium ÷ Σ(premium × GELR ÷ Plan loss ratio), as a %.",
        "RBS rows with a usable GELR AND a plan loss ratio above 0 - on both sides of the division.",
        [(RBS, P), (RBS, "gelr"), (RBS, "plan_loss_ratio")], "metrics/quality.py rate_adequacy",
        catches=["Matt's version divides ALL premium by a benchmark built from only some rows, which "
                 "overstates it. Here both sides use the same rows."]),
    "pricing.rate_adequacy_rbs_benchmark": Metric(
        "Rate Adequacy – RBS benchmark check", "A second opinion on Rate Adequacy, from RBS's own benchmark.",
        "Σ Mosaic 1609 premium ÷ Σ Mosaic 1609 benchmark premium, as a %.",
        "RBS rows with a benchmark premium above 0.",
        [(RBS, "mosaic_1609_premium"), (RBS, "mosaic_1609_benchmark")],
        "metrics/quality.py rate_adequacy_rbs_benchmark", workbook="Tab 5",
        catches=["Covers Mosaic 1609's share of each risk only, not all agency premium.",
                 "Uses the benchmark premium, not the \"Achieved Price (%)\" column, whose unit is "
                 "unclear - workbook tab 9."]),
    "pricing.rarc": Metric(
        "RARC", "On renewals, how much the price moved once the risk itself is allowed for.",
        "Σ(RARC × expiring premium) ÷ Σ expiring premium.",
        "RBS renewals (whatever the Business filter says) with an expiring premium that isn't "
        "blank or 0 and a RARC that isn't blank.",
        [(RBS, "rarc"), (RBS, "expired_premium"), (RBS, "business_type")], "metrics/quality.py rarc",
        catches=["Many RBS rows have no RARC, so this rests on part of the book - workbook tab 11 "
                 "shows how full the column is."]),
    # ---- What kind of book we write ---------------------------------------
    "composition.mosaic_as_lead": Metric(
        "Mosaic as lead", "How often we set the terms on a shared placement.",
        "Rows where the slip lead contains \"Mosaic\" ÷ all rows.", _all_rbs,
        [(RBS, "slip_lead")], "metrics/composition.py mosaic_as_lead", "Line (not premium)",
        catches=["Counts rows, so a small deal counts the same as a large one.",
                 "Includes \"Mosaic Asta Europe\" and \"Mosaic 5399\" as Mosaic - open question, "
                 "workbook tab 9.", "A blank slip lead counts as not Mosaic."]),
    "composition.primary_share": Metric(
        "Primary share", "How much of our book is first-layer cover.",
        "Primary rows ÷ all rows.", _all_rbs, [(RBS, "layer_type")],
        "metrics/composition.py primary_share", "Line (not premium)",
        catches=["Counts rows, not premium. Blank and Quota Share count as not Primary."]),
    "composition.average_agency_share": Metric(
        "Average agency share", "How big a slice of each placement we typically take.",
        "Σ(line share × premium) ÷ Σ premium.", "RBS rows with a line share.",
        [(RBS, "agency_share"), (RBS, P)], "metrics/composition.py average_agency_share",
        catches=["Rows with no line share are left out of both sides. Matt's build divides by all "
                 "premium instead, which understates it (workbook tab 12)."]),
    "composition.scm_share": Metric(
        "SCM share", "How much of our premium sits on third-party capital rather than Mosaic 1609.",
        "1 − (Σ Mosaic 1609 premium ÷ Σ premium).", _all_rbs,
        [(RBS, "mosaic_1609_premium"), (RBS, P)], "metrics/composition.py scm_share"),
    "composition.broker_concentration": Metric(
        "Broker concentration", "How much of our book sits with just a few brokers.",
        f"Premium of the {BROKER_CONCENTRATION_TOP_N} biggest brokers ÷ all premium.", _all_rbs,
        [(RBS, "broker"), (RBS, P)], "metrics/composition.py broker_concentration", workbook="Tab 5",
        catches=["Rows with no broker stay in the total but can't be a top broker."]),
    "composition.average_policy_length": Metric(
        "Average policy length", "How long our policies typically run.",
        "One length per policy (from its first line), then the average.",
        "RBS rows with a policy length.", [(RBS, "tenor_months"), (RBS, "policy_reference")],
        "metrics/composition.py average_policy_length", "Policy", workbook="Tab 5"),
    "composition.renewal_premium_growth": Metric(
        "Renewal premium growth", "Of the business that came up for renewal, how much premium came back.",
        "Σ renewal premium ÷ Σ expiring premium.",
        "RBS renewals (whatever the Business filter says) with an expiring premium above 0.",
        [(RBS, P), (RBS, "expired_premium"), (RBS, "business_type")],
        "metrics/composition.py renewal_premium_growth", workbook="Tab 5",
        catches=["NOT a true retention rate: renewals that didn't happen have no RBS row."]),
    "composition.new_vs_renewal_mix": Metric(
        "New vs. Renewal mix", "What share of premium is new business vs. repeat clients.",
        "Premium for each value ÷ all premium.", _all_rbs,
        [(RBS, "business_type"), (RBS, P)], "metrics/composition.py new_vs_renewal_mix", workbook="Tab 5",
        catches=["A blank value shows as its own \"(blank)\" slice rather than disappearing."]),
    "composition.placement_mix": Metric(
        "Placement mix", "What share of premium is Open Market vs. Facility vs. Agreement.",
        "Premium for each value ÷ all premium.", _all_rbs,
        [(RBS, "placement"), (RBS, P)], "metrics/composition.py placement_mix", workbook="Tab 5",
        catches=["A blank value shows as its own slice."]),
    # ---- Productivity (stand-in headcount) ----------------------------------
    "productivity_stand_in.active_underwriters_stand_in": Metric(
        "Active underwriters (stand-in)", "Underwriters who won at least one deal - a stand-in for headcount.",
        "Number of different underwriter names.", _all_rbs, [(RBS, "underwriter")],
        "metrics/headcount.py active_underwriters", "Person",
        catches=["Not true headcount: misses leaders who don't write, new joiners and people on leave.",
                 "Rows with no underwriter don't add a person."]),
    "productivity_stand_in.roster_underwriters_stand_in": Metric(
        "Roster underwriters (stand-in)", "Underwriters with at least one submission, won or not.",
        "Number of different underwriter names.", _all_dsr, [(DSR, "underwriter")],
        "metrics/headcount.py roster_underwriters", "Person",
        catches=["Not true headcount - same gaps as Active underwriters, but sees people who didn't win."]),
    "productivity_stand_in.premium_per_active_underwriter": Metric(
        "Premium / Active Underwriter", "The recommended productivity figure.",
        "Bound Premium ÷ Active underwriters.", _all_rbs, [(RBS, P), (RBS, "underwriter")],
        "metrics/headcount.py premium_per_active_underwriter", "Person",
        catches=["Reads a little better than true per-person productivity, because people who won "
                 "nothing aren't counted."]),
    "productivity_stand_in.premium_per_roster_underwriter": Metric(
        "Premium / Roster Underwriter", "A wider productivity view.",
        "Bound Premium (RBS) ÷ Roster underwriters (DSR).", "As the two figures it divides.",
        [(RBS, P), (DSR, "underwriter")], "metrics/headcount.py premium_per_roster_underwriter",
        "Person", workbook="Tab 4 note",
        catches=["The two sides don't cover quite the same people: a few underwriters have bound "
                 "premium in RBS but no DSR row at all, so they are in the premium and not in the "
                 "count. \"Roster\" is therefore wider than Active on the DSR side only "
                 "(open question 26)."]),
    "productivity_stand_in.uw_margin_per_active_underwriter": Metric(
        "UW Margin / Active Underwriter", "Productivity adjusted for how profitable the business was.",
        "Bound Premium × UW Margin % ÷ Active underwriters.", "As the three figures it uses.",
        [(RBS, P), (RBS, "gelr"), (RBS, "commission"), (RBS, "underwriter")],
        "metrics/headcount.py uw_margin_per_active_underwriter", "Person"),
    # ---- What drove the change -----------------------------------------------
    "drivers.premium_per_active_underwriter": Metric(
        "What drove Premium / Active Underwriter",
        "Splits the year-on-year change in premium per active underwriter into four drivers.",
        "Premium ÷ Underwriters = (Submissions ÷ Underwriters) × (Quotes ÷ Submissions) "
        "× (Binds ÷ Quotes) × (Premium ÷ Binds). Each driver's share of the total move = "
        "its log change ÷ the total log change × the total move, so the shares add up exactly.",
        "This period and the same months a year earlier, both after your filters.",
        [(DSR, "policy_reference"), (DSR, "status"), (RBS, "policy_reference"), (RBS, P),
         (RBS, "underwriter")],
        "metrics/drivers.py productivity_drivers", "Person", traced=False,
        check_note="Arithmetic on Submissions, Quotes, Binds, Bound Premium and Active underwriters - "
                   "each of those is checked against the raw columns.",
        catches=["Underwriters = Active underwriters (stand-in), not true headcount.",
                 "Same method as the log-share bridge in Matt's build, but the waterfall his page "
                 "draws allocates by Shapley value and carries a fifth margin term, so his "
                 "contributions won't match ours figure for figure (workbook tab 12).",
                 "Not shown when either year has no submissions, quotes, binds or premium, or on "
                 "Submission date basis (binds and premium need RBS)."]),
    # ---- Underwriter table columns ------------------------------------------
    "underwriters.submissions": Metric(
        "Submissions (per underwriter)", "How many risks came in for this underwriter.",
        "Number of different policies.", "Their DSR rows, ignoring the Underwriter filter.",
        [(DSR, "policy_reference"), (DSR, "underwriter")], "metrics/underwriters.py", "Policy"),
    "underwriters.quote_rate": Metric(
        "Q/S (per underwriter)", "The share of their submissions they priced.",
        "Their quotes ÷ their submissions.", "Their DSR rows.",
        [(DSR, "policy_reference"), (DSR, "status"), (DSR, "underwriter")], "metrics/underwriters.py",
        "Policy", catches=["Shown even on very few submissions - check the Submissions column."]),
    "underwriters.binds": Metric(
        "Binds (per underwriter)", "How many risks they won.",
        "Number of different policies in RBS.", "Their RBS rows.",
        [(RBS, "policy_reference"), (RBS, "underwriter")], "metrics/underwriters.py", "Policy"),
    "underwriters.bind_rate": Metric(
        "B/Q (per underwriter)", "The share of what they priced that they won.",
        "Their binds (RBS) ÷ their quotes (DSR).", "Their DSR and RBS rows.",
        [(RBS, "policy_reference"), (DSR, "policy_reference"), (DSR, "status"), (DSR, "underwriter"),
         (RBS, "underwriter")], "metrics/underwriters.py", "Policy"),
    "underwriters.premium": Metric(
        "Premium (per underwriter)", "Bound premium on their business.",
        "Sum of premium across every line.", "Their RBS rows.",
        [(RBS, P), (RBS, "underwriter")], "metrics/underwriters.py"),
    "underwriters.premium_vs_peer_median": Metric(
        "vs peer median", "How their premium compares with the middle underwriter.",
        "Their premium ÷ the median premium of the underwriters in the table.",
        "Underwriters in your other filters (the Underwriter filter is ignored)"
        + (", leaving out anyone with no premium." if PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM else "."),
        [(RBS, P), (RBS, "underwriter")], "metrics/underwriters.py", "Person",
        catches=["1.50× = 50% more premium than the middle underwriter.",
                 "A simpler comparison than Matt's: he medians annualised UW margin per underwriter "
                 "over the same product or line, leaves the person out of their own median, and "
                 "annualises by months employed (workbook tab 12)."]),
    "underwriters.uw_margin_pct": Metric(
        "UW Margin % (per underwriter)", "What's left of their premium after expected claims and commission.",
        "As UW Margin %, on their rows only.", "Their RBS rows with a usable GELR.",
        [(RBS, "gelr"), (RBS, "commission"), (RBS, P), (RBS, "underwriter")], "metrics/underwriters.py",
        catches=["Blank when they have no premium with a usable GELR."]),
}


def raw_columns(report):
    """Every original column name the lineage says the pipeline reads from one report."""
    return {name for column in COLUMNS.values() for name in column.raw(report)}
