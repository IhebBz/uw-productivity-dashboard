"""Every fixed choice the dashboard makes, gathered in one place.

If a threshold or a status list needs to change, it changes here once -
never as a hand-copied literal somewhere inside a metric function.
"""

# Which XFI Policy Status values count as "quoted" or "bound" (DSR side).
# RBS never needs this list - every RBS row is already bound.
QUOTED_STATUSES = {
    "Bound", "Cancelled", "Firm Order Noted", "Live Policy",
    "Non Renewed", "Quote", "Quote NTU", "Renewed",
}
BIND_STATUSES = {
    "Bound", "Cancelled", "Firm Order Noted", "Live Policy",
    "Non Renewed", "Renewed",
}

# Below these sample sizes, a rate is withheld rather than shown - a rate
# built on a handful of deals is noise, not a finding.
MIN_SUBMISSIONS_FOR_RATE = 20
MIN_QUOTES_FOR_BIND_RATE = 20
MIN_BINDS_FOR_DEAL_SIZE = 5

# How big a gap between DSR and RBS, on the same scope, is worth flagging
# rather than treated as normal rounding/timing noise (see reconcile/).
RECONCILIATION_TOLERANCE_PCT = 0.02

# Comparison window: current year vs. the prior year, same months.
COMPARISON_YEARS_BACK = 1

# Not usable without the HR file, kept here so the moment HR access exists,
# this is the only place that needs filling in.
TENURE_BANDS = ["0-1", "1-2", "2+"]
HR_AVAILABLE = False
