"""Every fixed choice the dashboard makes, gathered in one place.

If a threshold or a status list needs to change, it changes here once -
never as a hand-copied literal somewhere inside a metric function.
"""

# Which XFI Policy Status values count as "quoted" or "bound" (DSR side).
# RBS never needs this list - every RBS row is already bound.
# Tab 3, Rule 2: one agreed list of "won" statuses, matching what actually
# ends up in RBS. Checked against the real extracts: every DSR policy with a
# bound status appears in RBS, and almost no policy with any other does.
QUOTED_STATUSES = {
    "Bound", "Cancelled", "Firm Order Noted", "Live Policy",
    "Non Renewed", "Quote", "Quote NTU", "Renewed",
}
BIND_STATUSES = {
    "Bound", "Cancelled", "Firm Order Noted", "Live Policy",
    "Non Renewed", "Renewed",
}

# How big a gap between DSR and RBS, on the same scope, is worth flagging.
# Tab 3, Rule 6: "a small gap, a percent or two - expected and fine"
# (see reconcile/).
RECONCILIATION_TOLERANCE_PCT = 0.02

# Comparison window: current year vs. the prior year, same months.
COMPARISON_YEARS_BACK = 1

# What the dashboard opens on, and what "Clear all" goes back to (workbook tab 7).
# Matt's build opens on New + Open Market, because that's the slice his LOB
# workbook reconciles to. We don't have that workbook, and our stand-in
# headcount follows every filter anyway, so we open on the whole book. Set
# these to "New" / "Open Market" to open the way Matt's does.
DEFAULT_PERIOD = "ytd"             # "ytd", "ttm", "full", "q1".."q4" - see PERIODS in server/filters.py
DEFAULT_BUSINESS_TYPE = None       # None (All), "New" or "Renewal"
DEFAULT_PLACEMENT = None           # None (All), "Open Market", "Facility/DUA" or "Agreement"
DEFAULT_DATE_BASIS = "inception"   # "inception" or "submission"

# Thin data (workbook tab 9, question 4). A rate or average built on fewer
# policies than this is still shown - the workbook says blank only when there
# is nothing to divide by - but greyed out with a "few deals" flag, so nobody
# reads 50% off two submissions as a finding.
SMALL_SAMPLE_MIN = 20

# The same idea for per-person figures (Premium / Active Underwriter...): with
# fewer underwriters than this, one person's year swings the whole figure.
SMALL_TEAM_MIN = 5

# UW Margin % is only worked out on premium with a usable GELR. Below this
# share of premium ("Margin cover"), the page warns that the margin rests on
# part of the book.
LOW_MARGIN_COVER = 0.90

# Trend charts: how many months each chart shows, ending with the selected
# period's last month (24 = the selected months, what came before, and the
# same months a year earlier).
TREND_MONTHS = 24

# Broker Concentration (workbook tab 5): share of premium with the top N brokers.
BROKER_CONCENTRATION_TOP_N = 5

# Peer comparison (workbook tab 4): leave underwriters who wrote no premium
# out of the peer median, so a zero doesn't drag the middle figure down. The
# workbook asks for this to be a deliberate choice - it's a setting so the
# choice is visible and one line to change.
#
# Matt's build does something related but not the same, and ours is the
# simpler stand-in (workbook tab 12): he medians ANNUALISED UW margin per
# underwriter (not premium), leaves the person themselves out of their own
# median, keeps zero-premium colleagues in the peer COUNT, and takes peers
# from the same product or line rather than from whatever is filtered.
PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM = True

# Not usable without the HR file, kept here so the moment HR access exists,
# this is the only place that needs filling in.
TENURE_BANDS = ["0-1", "1-2", "2+"]
HR_AVAILABLE = False
