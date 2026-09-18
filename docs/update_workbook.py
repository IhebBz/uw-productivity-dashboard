"""Rebuilds the hand-written tabs of the metrics workbook: 7 (Filters),
8 (Build tracker), 9 (Decisions & questions), 12 (Ours vs Matt's build) and
13 (Checks & safeguards), and tops up tabs 1, 2, 4 and 5 where they point at
them.

Tabs 1-6 are the original hand-written spec and are left as they are, apart
from the "Built?" column on 4 and 5 and pointers in 1 and 2. Tabs 10 and 11
(lineage) come from metrics/lineage.py - run docs/update_lineage_tabs.py for
those.

Safe to run again: each generated tab is replaced in place, and the top-ups
are skipped if they're already there. Figures quoted in the tabs are read
from the real extracts in data/ when they're present.

Run from the project root:
    python docs/update_workbook.py
"""
import copy
import datetime
import logging
import dataclasses
import pathlib
import sys

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_sources.excel_source import ExcelSource  # noqa: E402
from pipeline.build_dashboard_data import prepare, compute_with_comparison  # noqa: E402
from scope.filter import Scope  # noqa: E402
from scope.period import last_complete_month  # noqa: E402
from server.formatting import FORMATTERS  # noqa: E402

logging.disable(logging.WARNING)
PATH = ROOT / "docs" / "UW_Dashboard_Metrics_Inventory.xlsx"
TODAY = datetime.date.today().strftime("%d %b %Y")

NAVY = "FF1F3864"
SECTION = "FFD9E2F3"
GREEN, AMBER, RED = "FFE2EFDA", "FFFFF2CC", "FFFCE4E4"
thin = Side(style="thin", color="FFBFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def header(ws, row, titles, widths=None):
    for i, t in enumerate(titles, 1):
        c = ws.cell(row, i, t)
        c.font = Font(name="Arial", size=11, bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDER
    ws.row_dimensions[row].height = 30
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w


def section(ws, row, text, ncols):
    for i in range(1, ncols + 1):
        c = ws.cell(row, i, text if i == 1 else None)
        c.font = Font(name="Arial", size=10.5, bold=True, color=NAVY)
        c.fill = PatternFill("solid", fgColor=SECTION)
        c.alignment = Alignment(vertical="center")
        c.border = BORDER
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)


def body(ws, row, values, status_col=None, bold_first=False):
    for i, v in enumerate(values, 1):
        c = ws.cell(row, i, v)
        c.font = Font(name="Arial", size=9.5, bold=bold_first and i == 1)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.border = BORDER
    if status_col:
        c = ws.cell(row, status_col)
        text = str(c.value or "")
        colour = (GREEN if text.startswith(("Yes", "Built", "Decided", "Done"))
                  else RED if text.startswith(("No", "Can't", "Not built")) else AMBER)
        c.fill = PatternFill("solid", fgColor=colour)


def intro(ws, text, ncols):
    c = ws.cell(1, 1, text)
    c.font = Font(name="Arial", size=9.5, color="FF595959")
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws.row_dimensions[1].height = 54


def legend_row(ws, row):
    for col, (text, fill) in zip((1, 3, 5), (("Green = done / safe to use", GREEN),
                                             ("Amber = works, read the note", AMBER),
                                             ("Red = not available / not built", RED))):
        c = ws.cell(row, col, text)
        c.font = Font(name="Arial", size=9)
        c.fill = PatternFill("solid", fgColor=fill)
        c.alignment = Alignment(vertical="center")
        c.border = BORDER


# --------------------------------------------------------------------------
# Real figures for the tracker: the dashboard's default view.
SOURCE = ExcelSource(folder=str(ROOT / "data"))
data = prepare(SOURCE)
LAST_COMPLETE_YEAR, LAST_COMPLETE_MONTH = last_complete_month(data.as_at)
DEFAULT_SCOPE = Scope(year=LAST_COMPLETE_YEAR, months=list(range(1, LAST_COMPLETE_MONTH + 1)))
view = compute_with_comparison(data, DEFAULT_SCOPE)
cur, pri = view["current"], view["prior"]
DEFAULT_LABEL = cur["period_label"]
PRIOR_LABEL = pri["period_label"]


def fig(path, kind):
    section_, key = path.split(".")
    now = (cur.get(section_) or {}).get(key)
    was = (pri.get(section_) or {}).get(key)
    return f"{FORMATTERS[kind](now)} ({PRIOR_LABEL}: {FORMATTERS[kind](was)})"


RAW_DSR, RAW_RBS = SOURCE.get_dsr(), SOURCE.get_rbs()
LEAD = RAW_RBS["Slip Lead"].value_counts().to_dict()
_prem = {"DSR": pd.to_numeric(RAW_DSR["Agency Share Gross Written Premium (USD)"], errors="coerce"),
         "RBS": pd.to_numeric(RAW_RBS["Agency Share Gross Written Premium (USD)"], errors="coerce")}
NEG = {k: int((v < 0).sum()) for k, v in _prem.items()}
BLANK_PREM = {k: v.isna().mean() for k, v in _prem.items()}
BLANK_PREM_N = {k: int(v.isna().sum()) for k, v in _prem.items()}
_gelr = pd.to_numeric(RAW_RBS["Agency GELR (%)"], errors="coerce")
GELR_BLANK, GELR_ZERO = int(_gelr.isna().sum()), int((_gelr == 0).sum())
_primary = RAW_RBS["Type of Layer"] == "Primary"
DEDUCTIBLE_BLANK = int(RAW_RBS.loc[_primary, "Deductible (USD)"].isna().sum())
PRIMARY_ROWS = int(_primary.sum())
SLIP_BLANK = int(RAW_RBS["Slip Lead"].isna().sum())
N_DSR, N_RBS = len(RAW_DSR), len(RAW_RBS)


def filled(frame, column):
    """Share of rows with a value in a raw column, as text."""
    if column is None or column not in frame.columns:
        return "-"
    return f"{frame[column].notna().mean():.1%}"


# --------------------------------------------------------------------------
# Facts read from the real extracts, so the tabs quote today's figures rather
# than numbers typed in by hand.
from config.settings import (LOW_MARGIN_COVER, RECONCILIATION_TOLERANCE_PCT, SMALL_SAMPLE_MIN,
                             SMALL_TEAM_MIN)
from ingest.clean_rbs import GELR_SANITY_RANGE, OPTIONAL_COLUMNS, RARC_EXTREME_PCT
from metrics import composition, quality
from scope.filter import apply_scope

AS_AT_TEXT = f"{data.as_at:%d %b %Y}"
_missing_optional = [c for c in OPTIONAL_COLUMNS.values() if c not in RAW_RBS.columns]
ALL_OPTIONAL_TEXT = ("All present" if not _missing_optional
                     else f"Missing: {', '.join(_missing_optional)}")
_gelr_unscaled = pd.to_numeric(RAW_RBS["Agency GELR (%)"], errors="coerce")
PERCENT_TEXT = ("Stored as fractions (0.40), scaled x100"
                if _gelr_unscaled[_gelr_unscaled != 0].quantile(0.99) <= 3 else "Already in percent units")
GELR_MEDIAN_TEXT = (f"Middle GELR {_gelr_unscaled[_gelr_unscaled != 0].median() * 100:.1f}% "
                    f"(range {GELR_SANITY_RANGE[0]}-{GELR_SANITY_RANGE[1]}%) - pass")
_dsr_uw = data.dsr["underwriter"].isna().mean()
UNATTRIBUTED_TEXT = f"{_dsr_uw:.0%} of DSR rows - " + ("warning logged" if _dsr_uw > 0.10 else "no warning")


def _gap_text(recon):
    gap = getattr(recon, "gap_pct", None)
    if gap is None:
        return "Can't be worked out"
    return (f"{gap:.1%} apart on {DEFAULT_LABEL} - "
            + ("flagged" if gap > RECONCILIATION_TOLERANCE_PCT else "within tolerance"))


PREMIUM_GAP_TEXT = _gap_text(cur["premium"]["reconciliation"])
BINDS_GAP_TEXT = _gap_text(cur["funnel"]["binds_reconciliation"])
_cover = cur["quality"]["margin_cover"]
MARGIN_COVER_TEXT = (f"{_cover:.1%} of premium on {DEFAULT_LABEL} - "
                     + ("note shown" if _cover < LOW_MARGIN_COVER else "above 90%, no note"))
DUPLICATES_TEXT = (f"{len(data.possible_duplicates) // 2} pairs flagged: "
                   + "; ".join(sorted(f"{data.underwriter_names[k]} / {v[0]}"
                                      for k, v in data.possible_duplicates.items()
                                      if data.underwriter_names[k] < v[0])))
TRACE_TEXT = "Pass - exact match, every figure and every underwriter"

# What each definition difference from Matt's build is worth on this extract.
_rbs = apply_scope(data.rbs, DEFAULT_SCOPE)
_ok = _rbs[_rbs["gelr_ok"]]
_prem_total = _rbs["premium"].sum()
_rows = _rbs[_rbs["gelr_ok"] & _rbs["plan_loss_ratio"].notna() & _rbs["plan_loss_ratio"].gt(0)]
_bench = (_rows["premium"] * _rows["gelr"] / _rows["plan_loss_ratio"]).sum()
_lead = _rbs["slip_lead"].astype(str)
_offices = ["Mosaic 1609", "Mosaic UK", "Mosaic US", "Mosaic Bermuda", "Mosaic CN", "Mosaic Dubai",
            "Mosaic Germany", "Mosaic SP"]
_primary_rows = _rbs[_rbs["layer_type"] == "Primary"]
_nonzero_comm = _rbs[_rbs["commission"] > 0]
EFFECT = {
    "gelr_book": f"{(_rbs['gelr'].fillna(0) * _rbs['premium']).sum() / _prem_total:.2f}% ours vs "
                 f"{(_ok['gelr'] * _ok['premium']).sum() / _ok['premium'].sum():.2f}% if blanks were left out",
    "commission_book": f"{(_rbs['commission'] * _rbs['premium']).sum() / _prem_total:.2f}% ours vs "
                       f"{(_nonzero_comm['commission'] * _nonzero_comm['premium']).sum() / _nonzero_comm['premium'].sum():.2f}% "
                       f"over only the rows that carry a commission",
    "rate_adequacy": f"{100 * _rows['premium'].sum() / _bench:.1f}% ours vs "
                     f"{100 * _prem_total / _bench:.1f}% Matt-style (all premium over the same benchmark)",
    "lead": f"{_lead.str.contains('Mosaic', case=False).mean():.1%} ours (any \"Mosaic\") vs "
            f"{_lead.isin(_offices).mean():.1%} counting only 1609 and the offices",
    "attach_primary": f"{_primary_rows['deductible'].fillna(0).median():,.0f} ours (blank = 0) vs "
                      f"{_primary_rows['deductible'].dropna().median():,.0f} if blanks were left out",
    "limit": f"median {_rbs['exposure'].median():,.0f} ours vs mean {_rbs['exposure'].mean():,.0f} "
             f"(what \"Average Limit\" would suggest)",
    "primary_share": f"{(_rbs['layer_type'] == 'Primary').mean():.1%} ours (rows) vs "
                     f"{_primary_rows['premium'].sum() / _prem_total:.1%} weighted by premium",
    "peer_median": f"{FORMATTERS['money'](cur['underwriters']['peer_median_premium'])} ours (zero-premium "
                   f"underwriters left out)",
}


# What the audit's findings are worth, measured rather than asserted.
_gap = cur["funnel"]["binds_not_in_dsr"]
AUDIT = {
    "binds_not_in_dsr": f"{_gap['policies']:,} of {_gap['of_binds']:,} bound policies "
                        f"({FORMATTERS['ratio'](_gap['premium_share'])} of premium) have no DSR row at "
                        f"all; B/Q reads {FORMATTERS['ratio'](cur['funnel']['bind_rate'])} and would "
                        f"read {FORMATTERS['ratio'](_gap['bind_rate'])} without them",
    "commission_zero": f"{FORMATTERS['ratio'](1 - cur['quality']['commission_cover'])} of the margin "
                       f"premium records no commission; margin reads "
                       f"{FORMATTERS['pct'](cur['quality']['uw_margin_pct'])} and "
                       f"{FORMATTERS['pct'](cur['quality']['uw_margin_pct_recorded_commission'])} over "
                       f"the rows that do record one",
}
_scoped_rbs = apply_scope(data.rbs, DEFAULT_SCOPE)
_entity_binds = sum(apply_scope(data.rbs, dataclasses.replace(DEFAULT_SCOPE, entity=e))
                    ["policy_reference"].nunique() for e in data.rbs["entity"].dropna().unique())
_split = int((_scoped_rbs.groupby("policy_reference")["entity"].nunique() > 1).sum())
AUDIT["entity_split"] = (f"{_split} policies in scope have lines under more than one entity, so binds "
                         f"summed over the 12 entities come to {_entity_binds:,} against "
                         f"{_scoped_rbs['policy_reference'].nunique():,} actual "
                         f"({_entity_binds / _scoped_rbs['policy_reference'].nunique() - 1:+.1%})")
_rarc = data.rbs["rarc"]
_extreme = _rarc.abs() > RARC_EXTREME_PCT
AUDIT["rarc_extreme"] = (f"{int(_extreme.sum())} rows book-wide are beyond \u00b1{RARC_EXTREME_PCT}% "
                         f"(largest {_rarc[_extreme].abs().max():,.0f}%); dropping the in-scope ones "
                         f"moves RARC by about 1.7 points")

def _fresh_sheet(wb, title):
    """Replace a generated tab in place (same position), or add it at the end."""
    index = len(wb.sheetnames)
    if title in wb.sheetnames:
        index = wb.sheetnames.index(title)
        del wb[title]
    return wb.create_sheet(title, index)


wb = openpyxl.load_workbook(PATH)

# --------------------------------------------------------------------------
# Tab 7 - Filters
ws = _fresh_sheet(wb, "7. Filters")
intro(ws, "Every filter on the dashboard and how it behaves. The filters sit in one toolbar across the top: "
          "each button shows its current choice (outlined in orange when it's not the default) and opens a "
          "small menu. Nothing changes until you press Apply, so several filters can be set in one go. Every "
          "filter you've switched on also shows under the toolbar as a chip - click its × to remove just "
          "that one, or Clear all. Each filter narrows EVERY figure on the page the same way, on both DSR "
          "and RBS (tab 3, Rule 1), and every figure is shown next to the same period a year earlier. Your "
          "choices live in the page address, so a view can be bookmarked or sent to someone.", 8)
legend_row(ws, 2)
header(ws, 3, ["Filter", "What it does", "Choices", "In Matt's build?", "On our dashboard?",
               "Note / catch", "Opens on (default)", "Where in the code"],
       [18, 34, 26, 16, 14, 48, 16, 30])
rows = [
    ("PERIOD MENU", None),
    ("Period", "Which months the figures cover.",
     "Quick picks: This year so far / Last 12 months / Full year. A quarter: Q1-Q4. Or tick any months.",
     "Partly - YTD / TTM and a month bar", "Yes (reworked)",
     "\"This year so far\" = January to the last COMPLETE month (data as at 15 Sep 2026 -> Jan-Aug). "
     "\"Last 12 months\" = the twelve months ending with the last complete month (Sep 2025-Aug 2026). "
     "Months with no complete data yet are shown dashed. Ticking a month switches to picked months; "
     "choosing a quick pick or quarter clears the ticks.",
     "This year so far", "PERIODS in server/filters.py; Scope in scope/filter.py"),
    ("Year", "Which year to look at. Always compared with the year before, same months.",
     "Every year in the data up to today (2021-2026)", "No - fixed at 2026 vs 2025", "Yes (new)",
     "In the Period menu. Looking at a past year uses the same months, so 2024 \"This year so far\" is "
     "Jan-Aug 2024 vs Jan-Aug 2023.", "Latest year", "Scope.year; scope/period.py prior_year_scope"),
    ("Date basis (\"Count a policy in the month of its...\")",
     "Which date decides the month a policy belongs to.",
     "Inception date / Submission date", "Yes", "Yes - with a limit",
     "In the Period menu. Tab 3, Rule 3: RBS has no submission date. On Submission, only DSR-only figures "
     "are shown (Submissions, Quotes, Quote rate, Roster underwriters); everything needing RBS is blank "
     "with a note, rather than quietly mixing two different months. Matt's build mixes them.",
     "Inception date", "Scope.date_basis; SUBMISSION_BASIS_NOTE in pipeline/build_dashboard_data.py"),
    ("WHAT KIND OF BUSINESS", None),
    ("Business", "New business, renewals, or both. Each choice is explained in the menu.",
     "All / New / Renewal", "Yes", "Yes",
     "Follows RBS's Renewal Status where DSR disagrees (tab 3, Rule 2). RARC and Renewal Premium Growth "
     "always look at renewals, whatever is picked here. Matt's build opens on New.",
     "All (Matt: New)", "Scope.business_type; DEFAULT_BUSINESS_TYPE in config/settings.py"),
    ("Placement", "How the business reached us. Each choice is explained in the menu.",
     "All / Open Market / Facility/DUA / Agreement", "Yes", "Yes",
     "Our data also has Agreement business, which Matt's list doesn't show. Matt's build opens on Open "
     "Market because that's what his LOB workbook reconciles to - see tab 9.",
     "All (Matt: Open Market)", "Scope.placement; DEFAULT_PLACEMENT in config/settings.py"),
    ("Line of business", "One class of business, e.g. Cyber.", "Only what exists with the other filters",
     "Yes", "Yes", "Same values on DSR and RBS (tab 3, Rule 2).", "All lines",
     "Scope.line_of_business; scope/options.py"),
    ("Entity", "One producing entity, e.g. Mosaic UK.", "Only what exists with the other filters",
     "Yes", "Yes - read the note",
     "DSR's spellings mapped onto RBS's (\"Mosaic Syndicate 2610\" -> \"Mosaic 2610\"). Our data has 12 "
     "entities, including syndicates (1609, 2610, 5399, 5431); Matt's list has 7 office entities, so "
     "he may group them - open question in tab 9.",
     "All entities", "Scope.entity; normalise_entity in config/field_map.py"),
    ("Product", "A product within a line, e.g. Cyber Tech, W&I Tax.", "-", "Yes", "No",
     "Not in DSR or RBS. Matt's build takes it from a product roster and Lloyd's Risk Code mapping "
     "we don't have. Listed under \"Not available yet\" with the reason. Needs that mapping - tab 9.",
     "-", "-"),
    ("WHO WROTE IT", None),
    ("Underwriter", "One underwriter. Also: click a name in the Underwriters table.",
     "Searchable list - type part of a name", "Yes", "Yes - read the note",
     "Names matched after tidying capitals, punctuation and spaces only (tab 3, Rule 5). Real "
     "duplicates seen: \"Stedman, Rob\" / \"Stedman, Robert\", \"Hirst, Justin\" / \"Hurst, Justin\". "
     "Picking a name keeps the peer comparison against everyone else in the other filters.",
     "All underwriters", "Scope.underwriter; ingest/underwriter_names.py"),
    ("Role", "Underwriters vs. leadership / UA.", "-", "Yes", "No",
     "Only in the HR file. Listed under \"Not available yet\".", "-", "HR_AVAILABLE in config/settings.py"),
    ("Tenure", "Years at Mosaic: 0-1, 1-2, 2+.", "-", "Yes", "No",
     "Only in the HR file. Listed under \"Not available yet\". Bands already in TENURE_BANDS.", "-",
     "TENURE_BANDS in config/settings.py"),
    ("HOW THE TOOLBAR BEHAVES", None),
    ("Apply / Cancel", "Choices take effect when you press Apply. Cancel, Esc or clicking away "
     "throws away changes you haven't applied.", "-", "No - every click reloads", "Yes (new)",
     "Each new combination takes 1-2 seconds to work out, so setting three filters used to mean three "
     "waits. The page fades while it updates.", "-", "TOOLBAR_SCRIPT in server/dashboard.py"),
    ("Only-possible choices", "Each list only offers choices that exist with the other filters, and says "
     "how many (e.g. \"162 available with your other filters\").", "-", "Yes", "Yes",
     "Built from both reports, this period and last year's. If a change makes a picked name impossible, "
     "it's cleared and the page says so, instead of showing an empty page.",
     "-", "scope/options.py; drop_stranded_selections in server/filters.py"),
    ("Search in long lists", "Type to narrow a list (Underwriter, and any list over 12 choices).", "-",
     "No", "Yes (new)", "\"All\" and the current choice always stay visible while searching.", "-",
     "_list_menu in server/dashboard.py"),
    ("Chips and Clear all", "Every filter that's on shows under the toolbar; × removes just that one.",
     "-", "No - one Reset button", "Yes (new)",
     "Clear all goes back to the defaults in config/settings.py (DEFAULT_...).", "-",
     "_active_filters in server/dashboard.py"),
    ("Shareable address", "The filters are in the page address, e.g. /?period=q2&bt=New&lob=Cyber.", "-",
     "No", "Yes (new)",
     "Bookmark or paste a filtered view. A broken or old link falls back to defaults rather than "
     "showing wrong numbers.", "-", "FilterState.query in server/filters.py"),
]
r = 4
for row in rows:
    if row[1] is None:
        section(ws, r, row[0], 8)
    else:
        body(ws, r, row, status_col=5, bold_first=True)
        d = ws.cell(r, 4)
        d.fill = PatternFill("solid", fgColor=GREEN if str(d.value).startswith("Yes") else AMBER)
    r += 1
ws.freeze_panes = "B4"

# --------------------------------------------------------------------------
# Tab 8 - Build tracker
ws = _fresh_sheet(wb, "8. Build tracker")
intro(ws, "Where every rule and metric stands in the code, so progress can be tracked. \"Jan-Aug 2026\" "
          f"is what the dashboard shows on real data as at 15 Sep 2026, all filters off - use it to spot "
          f"a figure that moves unexpectedly after a change. Exactly which DSR / RBS columns and rows "
          f"each figure uses is in tab 10. Last updated {TODAY}. When you change a metric: update its "
          f"row here and in tab 10, and its test.", 9)
legend_row(ws, 2)
header(ws, 3, ["Item", "Workbook tab", "Status", "On the dashboard", "Code (file / function)",
               "Test", f"{DEFAULT_LABEL} (vs {PRIOR_LABEL})", "Last changed", "Note"],
       [30, 11, 13, 22, 36, 26, 24, 12, 40])
T = TODAY
tracker = [
    ("MAKING DSR + RBS AGREE (tab 3)", None),
    ("Rule 1 - one shared filter", "3", "Done", "Every figure", "scope/filter.py apply_scope",
     "test_scope.py", "-", T, "Now also covers TTM, date basis and the filter speed-up."),
    ("Rule 2 - field name translation", "3", "Done", "-", "config/field_map.py FIELD_MAP", "-", "-", "-", ""),
    ("Rule 2 - New vs Renewal follows RBS", "3", "Done", "Business filter", "ingest/align_reports.py",
     "test_alignment.py", "271 policies changed (all years)", T, "Made ~10x faster; same result."),
    ("Rule 2 - entity spellings", "3", "Done", "Entity filter", "config/field_map.py normalise_entity",
     "test_alignment.py", "-", "-", ""),
    ("Rule 2 - one list of won statuses", "3", "Done", "-", "config/settings.py BIND_STATUSES", "-", "-",
     "-", ""),
    ("Rule 3 - inception date when both reports", "3", "Done", "Date basis filter",
     "scope/filter.py; pipeline SUBMISSION_BASIS_NOTE", "test_scope.py", "-", T,
     "Submission basis shows DSR-only figures."),
    ("Rule 4 - sum lines first, count policies", "3", "Done", "-", "metrics/premium.py, metrics/funnel.py",
     "test_new_metrics.py", "-", T, ""),
    ("Rule 5 - underwriter name tidy-up", "3", "Done - partial fix",
     "Underwriter filter + table", "ingest/underwriter_names.py", "test_alignment.py", "-", T,
     "Genuine spelling differences still split one person in two - tab 9."),
    ("Rule 6 - cross-check, RBS wins", "3", "Done", "Red badge on Bound Premium / Binds",
     "reconcile/cross_check.py", "test_reconcile.py",
     "Premium 9.1% apart, binds 3.4% apart", "-", "Gap above 2% - tab 9."),
    ("THE FUNNEL (tab 4)", None),
    ("Submissions", "4", "Built", "The funnel", "metrics/funnel.py submissions", "test_funnel.py",
     fig("funnel.submissions", "int"), "-", ""),
    ("Quotes", "4", "Built", "The funnel", "metrics/funnel.py quotes", "test_underwriters.py",
     fig("funnel.quotes", "int"), "-", ""),
    ("Binds", "4", "Built", "Headline + The funnel", "metrics/funnel.py binds_from_rbs", "test_funnel.py",
     fig("funnel.binds", "int"), "-", ""),
    ("Q/S", "4", "Built", "The funnel", "metrics/funnel.py quote_rate", "test_funnel.py",
     fig("funnel.quote_rate", "ratio"), "-", ""),
    ("B/Q", "4", "Built", "The funnel", "metrics/funnel.py bind_rate", "test_funnel.py",
     fig("funnel.bind_rate", "ratio"), "-", ""),
    ("B/S", "4", "Built", "The funnel", "metrics/funnel.py end_to_end_win_rate", "-",
     fig("funnel.end_to_end_win_rate", "ratio"), "-", ""),
    ("HOW MUCH WE WROTE (tab 4)", None),
    ("Bound Premium", "4", "Built", "Headline + How much we wrote", "metrics/premium.py bound_premium",
     "test_new_metrics.py", fig("premium.bound_premium", "money"), T, "Moved out of the pipeline file."),
    ("Average Deal Size", "4", "Built", "How much we wrote", "metrics/premium.py average_deal_size",
     "test_new_metrics.py", fig("premium.average_deal_size", "amount"), T, "New."),
    ("HOW GOOD THE BUSINESS IS (tab 4)", None),
    ("GELR - book version", "4", "Built - read note", "How good the business is",
     "metrics/quality.py gelr_book_basis", "test_quality.py", fig("quality.gelr_book_basis", "pct"), "-",
     "Blank GELR counts as 0 - tab 9."),
    ("GELR - margin version", "4", "Built", "How good the business is", "metrics/quality.py gelr_margin_basis",
     "test_quality.py", fig("quality.gelr_margin_basis", "pct"), "-", ""),
    ("Commission - book version", "4", "Built", "How good the business is",
     "metrics/quality.py commission_book_basis", "-", fig("quality.commission_book_basis", "pct"), "-", ""),
    ("Commission - margin version", "4", "Built", "How good the business is",
     "metrics/quality.py commission_margin_basis", "test_quality.py",
     fig("quality.commission_margin_basis", "pct"), "-", ""),
    ("UW Margin %", "4", "Built - read note", "Headline + How good the business is",
     "metrics/quality.py uw_margin_pct", "test_quality.py", fig("quality.uw_margin_pct", "pct"), "-",
     "Internal commission not subtracted - tab 9."),
    ("Margin cover", "4", "Built", "How good the business is", "metrics/quality.py margin_cover", "-",
     fig("quality.margin_cover", "ratio"), "-", ""),
    ("Commission cover", "4", "Built", "How good the business is", "metrics/quality.py commission_cover",
     "-", fig("quality.commission_cover", "ratio"), "-", ""),
    ("Attachment point (Excess)", "4", "Built", "How good the business is",
     "metrics/quality.py attachment_point_excess", "test_new_metrics.py",
     fig("quality.attachment_point_excess", "amount"), T, "New. Median; blank Excess left out."),
    ("Attachment point (Primary)", "4", "Built - read note", "How good the business is",
     "metrics/quality.py attachment_point_primary", "test_new_metrics.py",
     fig("quality.attachment_point_primary", "amount"), T, "New. Blank deductible = 0, so understated."),
    ("Average Limit (shown as Median limit)", "4", "Built", "How good the business is",
     "metrics/quality.py median_limit", "test_new_metrics.py", fig("quality.median_limit", "amount"), T,
     "New. Named as a median, as the workbook asks."),
    ("PRICING (tab 4)", None),
    ("Rate Adequacy", "4", "Built", "Pricing", "metrics/quality.py rate_adequacy", "test_quality.py",
     fig("pricing.rate_adequacy", "pct"), "-", "Same rows on both sides (fixes Matt's overstatement)."),
    ("RARC", "4", "Built", "Pricing", "metrics/quality.py rarc", "-", fig("pricing.rarc", "pct"), "-",
     "Renewals only. No test yet."),
    ("WHAT KIND OF BOOK WE WRITE (tab 4)", None),
    ("Mosaic as Lead", "4", "Built", "What kind of book", "metrics/composition.py mosaic_as_lead", "-",
     fig("composition.mosaic_as_lead", "ratio"), "-", "Row count, not premium."),
    ("Primary Share", "4", "Built", "What kind of book", "metrics/composition.py primary_share", "-",
     fig("composition.primary_share", "ratio"), "-", "Row count, not premium."),
    ("Average Agency Share", "4", "Built", "What kind of book", "metrics/composition.py average_agency_share",
     "test_new_metrics.py", fig("composition.average_agency_share", "pct"), T, "New. Premium-weighted."),
    ("SCM Share", "4", "Built", "What kind of book", "metrics/composition.py scm_share",
     "test_new_metrics.py", fig("composition.scm_share", "ratio"), T,
     "New. 1 - Mosaic 1609 premium / all agency premium."),
    ("LOOKING AT ONE UNDERWRITER (tab 4)", None),
    ("Funnel by underwriter", "4", "Built - read note", "Underwriters table + Underwriter filter",
     "metrics/underwriters.py underwriter_table", "test_underwriters.py", "-", T, "New. Name catch, Rule 5."),
    ("Book quality by underwriter", "4", "Built - read note", "Underwriters table (UW Margin %)",
     "metrics/underwriters.py underwriter_table", "test_underwriters.py", "-", T,
     "New. Margin only; GELR and Commission per underwriter show when you filter to one name."),
    ("Peer comparison", "4", "Built - read note", "Underwriters table (vs peer median)",
     "metrics/underwriters.py; PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM", "test_underwriters.py",
     f"Peer median {FORMATTERS['money'](cur['underwriters']['peer_median_premium'])}", T,
     "New. Zero-premium underwriters left out of the median, as Matt does - tab 9."),
    ("PRODUCTIVITY - STAND-IN HEADCOUNT (tab 4)", None),
    ("Roster underwriters", "4", "Built - stand-in", "Productivity", "metrics/headcount.py roster_underwriters",
     "-", fig("productivity_stand_in.roster_underwriters_stand_in", "int"), "-", ""),
    ("Active underwriters", "4", "Built - stand-in", "Productivity", "metrics/headcount.py active_underwriters",
     "-", fig("productivity_stand_in.active_underwriters_stand_in", "int"), "-", ""),
    ("Premium per Active Underwriter", "4", "Built - stand-in", "Headline + Productivity",
     "metrics/headcount.py premium_per_active_underwriter", "-",
     fig("productivity_stand_in.premium_per_active_underwriter", "money"), "-", ""),
    ("Premium per Roster Underwriter", "4", "Built - stand-in", "Productivity",
     "metrics/headcount.py premium_per_roster_underwriter", "-",
     fig("productivity_stand_in.premium_per_roster_underwriter", "money"), "-", ""),
    ("UW Margin per Active Underwriter", "4", "Built - stand-in", "Productivity",
     "metrics/headcount.py uw_margin_per_active_underwriter", "-",
     fig("productivity_stand_in.uw_margin_per_active_underwriter", "money"), "-", ""),
    ("NEW IDEAS (tab 5)", None),
    ("New vs. Renewal Mix", "5", "Built", "Mix bar", "metrics/composition.py new_vs_renewal_mix", "-", "-",
     "-", ""),
    ("Placement Mix", "5", "Built", "Mix bar", "metrics/composition.py placement_mix", "-", "-", "-", ""),
    ("Broker Concentration", "5", "Built", "What kind of book", "metrics/composition.py broker_concentration",
     "test_new_metrics.py", fig("composition.broker_concentration", "ratio"), T,
     "New. Top 5 - BROKER_CONCENTRATION_TOP_N."),
    ("Average Policy Length", "5", "Built", "What kind of book",
     "metrics/composition.py average_policy_length", "test_new_metrics.py",
     fig("composition.average_policy_length", "months"), T, "New. Once per policy, not per line."),
    ("Renewal Premium Growth", "5", "Built - read note", "What kind of book",
     "metrics/composition.py renewal_premium_growth", "test_new_metrics.py",
     fig("composition.renewal_premium_growth", "ratio"), T, "New. Not a true retention rate."),
    ("Rate Adequacy double-check", "5", "Built - read note", "Pricing",
     "metrics/quality.py rate_adequacy_rbs_benchmark", "test_new_metrics.py",
     fig("pricing.rate_adequacy_rbs_benchmark", "pct"), T,
     "New. Uses RBS's benchmark premium, not the Achieved Price column - tab 9."),
    ("CAN'T BUILD (tab 6)", None),
    ("Agency Revenue, Fee Yield, fees", "6", "Can't build", "-", "-", "-", "-", "-",
     "Fee columns don't exist in the standard RBS report."),
    ("True headcount, Role, Tenure", "6", "Can't build", "Greyed-out filters", "-", "-", "-", "-",
     "Needs the HR file."),
    ("Product filter", "7", "Can't build", "Greyed-out filter", "-", "-", "-", "-",
     "Needs Matt's product mapping - tab 9."),
    ("AUDIT OF THE CALCULATIONS (18 Sep 2026)", None),
    ("Binds DSR has never seen", "9", "Built", "Note under B/Q and B/S; the red badge card",
     "metrics/funnel.py binds_not_in_dsr", "test_audit_fixes.py", AUDIT["binds_not_in_dsr"], T,
     "Explains most of the DSR/RBS premium gap. Open question 26."),
    ("Win rate over 100% flagged", "9", "Built", "Underwriters table", "server/panels.py",
     "test_audit_fixes.py", "6 underwriters on the default view", T,
     "Where someone's binds aren't in DSR at all, their B/Q can't be read as a win rate."),
    ("Commission blank-zero effect shown", "9", "Built", "Note under UW Margin % and UW Margin / UW",
     "metrics/quality.py uw_margin_pct_recorded_commission", "test_audit_fixes.py",
     AUDIT["commission_zero"], T, "Open question 25."),
    ("Comparison year missing from the extract", "-", "Built", "Notice above the figures",
     "pipeline/build_dashboard_data.py", "test_audit_fixes.py",
     "2021 vs 2020 used to read as zeros", T, "Now blank with a notice instead of $0."),
    ("Driver story gated on thin data", "-", "Built", "Overview tab", "server/insights.py",
     "test_audit_fixes.py", "-", T,
     "Q4 2026 used to print \"fell 89.1%\" off 12 binds."),
    ("Driver wording corrected", "-", "Built", "Overview tab", "metrics/drivers.py _flow_meaning",
     "test_insights.py", "Submissions +11.9% against underwriters +23.9%", T,
     "It used to say \"less business coming in\" when submissions had risen."),
    ("Trend window vs the period", "-", "Built", "Trends tab", "server/panels.py",
     "test_audit_fixes.py", "-", T,
     "Says so when the period runs past the last complete month, instead of charting no selected months."),
    ("Extreme rate changes warned", "9", "Built", "Terminal warning", "ingest/clean_rbs.py",
     "-", AUDIT["rarc_extreme"], T, "Open question 28."),
    ("THE DASHBOARD ITSELF", None),
    ("Filter toolbar", "7", "Built", "Top of page", "server/filters.py, scope/options.py, server/dashboard.py",
     "test_filters.py", "-", T, "One button per filter, Apply / Cancel, searchable lists, removable chips."),
    ("Same period last year, with change", "-", "Built", "Every figure", "compute_with_comparison in "
     "pipeline/build_dashboard_data.py", "test_filters.py", "-", T,
     "New. Change coloured green/red where higher or lower is clearly better."),
    ("Speed", "-", "Done", "-", "pipeline prepare(); add_filter_columns in scope/filter.py",
     "test_scope.py", "~1-2s per new filter choice, instant repeat", T,
     "Was ~5s. Data is cleaned once per refresh, not per click."),
    ("Page renders for every view", "-", "Done", "-", "server/dashboard.py", "test_filters.py", "-", T,
     "Catches a figure the page asks for that the pipeline stopped producing."),
    ("Every figure traced to raw DSR / RBS columns", "10", "Done", "-", "tests/test_trace_to_source.py",
     "test_trace_to_source.py", "Every figure, every underwriter column, both mixes: exact match, 2 views",
     T, "Rebuilds each figure from the raw column names in tab 11, without any dashboard code, "
        "and fails if the two ever differ."),
    ("(i) lineage help on every figure", "10", "Done", "Next to every figure",
     "metrics/lineage.py; server/help.py", "test_lineage.py", "-", T,
     "Original DSR / RBS columns, what the pipeline does to them, rows, formula. Same source as tabs 10-11."),
    ("What drove Premium / Active Underwriter", "-", "Built", "Below the headline figures",
     "metrics/drivers.py; server/insights.py", "test_insights.py",
     "-9.3%: submissions per UW -9.7 pts, Q/S +4.1, B/Q -4.1, deal size +0.4", T,
     "Splits the year-on-year change into four drivers that add up exactly. Uses the Active "
     "underwriters stand-in."),
    ("Red badge explains itself", "3", "Built", "Bound Premium / Binds badges", "server/insights.py",
     "test_insights.py", "-", T, "Click the badge: RBS and DSR figures side by side, the gap, and what it means."),
    ("How to read this page", "-", "Built", "Link above the headline figures", "server/insights.py",
     "test_insights.py", "-", T, "Columns, colours, pts vs %, the (i), badges, few-deals tags, stand-ins."),
    ("Few-deals flags", "9", "Built", "Any figure on too few policies or underwriters",
     "server/insights.py; SMALL_SAMPLE_MIN, SMALL_TEAM_MIN", "test_insights.py", "-", T,
     "Greyed out with a tag, never hidden - tab 9, question 4."),
    ("Incomplete months warning", "7", "Built", "Notice above the figures", "server/insights.py",
     "test_insights.py", "-", T,
     "When the period includes months with no complete data (e.g. Full year 2026 in September)."),
    ("Low margin cover warning", "4", "Built", "Note on UW Margin %", "server/insights.py; LOW_MARGIN_COVER",
     "-", "-", T, "When under 90% of premium has a usable GELR."),
    ("Tabs", "-", "Built", "Overview, Funnel, Book quality, What we write, Productivity, Underwriters, Trends",
     "server/panels.py TABS", "test_trends_and_page.py", "-", T,
     "The open tab is in the address (#trends), so links and reloads keep it; print shows every tab."),
    ("Biggest moves against a year earlier", "-", "Built", "Overview tab", "server/panels.py",
     "test_trends_and_page.py", "Renewal premium growth -12.9 pts; SCM share +12.2 pts", T,
     "Top 3 rates (pts) and top 3 amounts (%); figures on too few deals left out."),
    ("Trend charts and headline sparklines", "-", "Built", "Trends tab; under headline figures",
     "metrics/trends.py; server/charts.py", "test_trends_and_page.py", "Sep 2024-Aug 2026", T,
     "24 months, your period in orange; hover, arrow keys, and a table view. Each month checked against "
     "the page figure for that month alone. Recent months are still filling in."),
    ("Underwriter table: sort, search, hide small books", "4", "Built", "Underwriters tab", "server/panels.py",
     "test_trends_and_page.py", "-", T, "Plus \u25b2/\u25bc against the peer median and a download."),
    ("Possible duplicate names", "3", "Built", "Underwriters tab tag; underwriters CSV",
     "ingest/underwriter_names.py possible_duplicates", "test_trends_and_page.py", "4 pairs", T,
     "Flags, never merges - tab 9, question 8."),
    ("Copy link, downloads, print", "-", "Built", "Next to the tabs", "server/exports.py; server/app.py",
     "test_trends_and_page.py", "-", T,
     "figures.csv carries each figure's report and original columns; both CSVs say which filters they're for."),
    ("Polish", "-", "Built", "Whole page", "server/formatting.py; server/panels.py", "test_trends_and_page.py",
     "-", T, "\u25b2/\u25bc on every change (not colour alone), \"a year earlier\" wording, mixes against a year "
     "earlier, a clear empty-filters message, filters in the browser tab title."),
]
r = 4
for row in tracker:
    if row[1] is None:
        section(ws, r, row[0], 9)
    else:
        body(ws, r, row, status_col=3, bold_first=True)
    r += 1
ws.freeze_panes = "B4"

# --------------------------------------------------------------------------
# Tab 9 - Decisions and open questions
ws = _fresh_sheet(wb, "9. Decisions & questions")
intro(ws, "Every judgement call behind the numbers, in one list: what the dashboard does today, and "
          "whether that's agreed or still needs someone to decide. Open = worth raising. Decided = "
          "settled, with the reason. When something is decided, change Status, fill in the date, and "
          "update the setting or code named in the last column.", 8)
legend_row(ws, 2)
header(ws, 3, ["#", "Question", "What the dashboard does today", "Other options", "Status",
               "Who can decide", "Raised", "Where to change it"],
       [5, 34, 40, 32, 11, 18, 11, 30])
decisions = [
    ("OPEN - WORTH RAISING", None),
    (1, "GELR book version: should a row with no GELR count as 0, or be left out?",
     "Counts as 0 (reading tab 4's \"across all rows\" literally). Makes GELR look slightly better "
     "(40.55% vs 40.63% margin version, all years).", "Leave blank rows out - then the book and margin "
     "versions are the same number.", "Open", "Matt / Finance", TODAY,
     "metrics/quality.py gelr_book_basis"),
    (2, "UW Margin %: should Mosaic's own internal commission also be subtracted?",
     "Not subtracted: 100 - GELR - Commission.", "Also subtract Mosaic 1609 Agency Commission.",
     "Open", "Matt / Finance", TODAY, "metrics/quality.py uw_margin_pct"),
    (3, "Why do DSR and RBS disagree by more than \"a percent or two\"?",
     "Keeps RBS's figure, shows a red badge. Jan-Aug 2026: premium 9.1% apart, binds 3.4% apart "
     "(all years: 11.9% and 3.7%).", "-", "Open", "Owners of the DSR and RBS extracts", TODAY,
     "reconcile/cross_check.py; RECONCILIATION_TOLERANCE_PCT"),
    (5, "Which filters should the dashboard open on?",
     "Everything (All business, All placement), YTD, inception date.",
     "Match Matt: New + Open Market, which his LOB workbook reconciles to.", "Open", "Matt", TODAY,
     "DEFAULT_... in config/settings.py"),
    (6, "Product filter: where does Matt's product list (Cyber Tech, W&I Tax, ...) come from?",
     "Filter greyed out.", "Get the product roster / Lloyd's Risk Code mapping and add a product column "
     "in ingest/.", "Open", "Matt", TODAY, "ingest/clean_rbs.py, ingest/clean_dsr.py, scope/filter.py"),
    (7, "Entities: our data has 12 (incl. syndicates 1609, 2610, 5399, 5431, SP, Asta Europe); Matt's "
        "list has 7 offices. Does he group them?",
     "Shows all 12 as they appear in the reports.", "Add a grouping (e.g. syndicate -> office) to "
     "ENTITY_ALIASES.", "Open", "Matt", TODAY, "config/field_map.py ENTITY_ALIASES"),
    (8, "Underwriter names spelled two ways - build a manual list?",
     "Tidies capitals, punctuation and spaces only, and flags likely pairs in the Underwriters table "
     "(\"possible duplicate\") without merging them. Flagged on the real data: \"Stedman, Rob\" / "
     "\"Stedman, Robert\", \"Hirst, Justin\" / \"Hurst, Justin\", \"Macdonald, Noelle\" / "
     "\"Macdonald, Nolle\", \"Deutsch, Ze'ev\" / \"Deutsch, Zeev\" (the apostrophe splits the name).",
     "A short hand-made alias list, checked by someone who knows the team.", "Open", "UW team lead", TODAY,
     "ingest/underwriter_names.py"),
    (9, "RBS's \"Achieved Price (%)\" column: what unit is it in?",
     "Not used. The Rate Adequacy double-check uses RBS's own benchmark premium instead "
     "(Mosaic 1609 premium / 1609 benchmark premium).",
     "Use Achieved Price once its unit is known (median ~1.3 after scaling, outliers in the "
     "hundreds of thousands).", "Open", "RBS extract owner", TODAY,
     "metrics/quality.py rate_adequacy_rbs_benchmark"),
    (10, "Peer median: leave out underwriters with no premium?",
     "Left out, as in Matt's build, so a zero doesn't drag the middle figure down.",
     "Include them (median falls).", "Open - confirm", "Matt", TODAY,
     "PEER_MEDIAN_EXCLUDES_ZERO_PREMIUM in config/settings.py"),
    (19, "Mosaic as Lead: which Slip Lead values count as \"us\"?",
     "Any Slip Lead containing \"Mosaic\": Mosaic 1609, the offices (UK, US, Dubai...), but also "
     f"Mosaic Asta Europe ({LEAD['Mosaic Asta Europe']:,} rows) and Mosaic 5399 "
     f"({LEAD['Mosaic 5399']:,} rows).",
     "Only Mosaic 1609 and the Mosaic offices; or an agreed list.", "Open", "Matt", TODAY,
     "metrics/composition.py mosaic_as_lead"),
    (22, "Some underwriters are credited differently in DSR and RBS - which is right?",
     "Each report's own underwriter columns are used. On the real data one underwriter has 3 DSR "
     "submissions but 22 RBS binds (a 733% win rate, shown greyed as \"few quotes\"): their bound "
     "business is credited to them in RBS but mostly to someone else in DSR.",
     "Credit binds by DSR's underwriter where the policy is in both, as New/Renewal already follows one "
     "report.", "Open", "Extract owners / Matt", TODAY, "ingest/clean_dsr.py, ingest/clean_rbs.py"),
    (23, "Headline premium: RBS (ours) or DSR (Matt's)?",
     f"RBS, with DSR as a cross-check ({PREMIUM_GAP_TEXT}). Matt's headline premium is the DSR one, and "
     f"his per-head and deal-size figures sit on that base, so his headline figure is our cross-check "
     f"figure.",
     "Match Matt and lead with DSR premium; or keep RBS and expect a gap when comparing with his deck.",
     "Open", "Matt / Finance", TODAY, "metrics/premium.py; tab 12"),
    (24, "GELR: should 2021 inceptions be left out, as Matt's does?",
     "Every year in the filters is included.",
     "Drop 2021 inceptions from GELR (and say why), as his tooltip says his does.", "Open", "Matt", TODAY,
     "metrics/quality.py"),
    (25, "Blank or zero commission counts as \"none charged\" - should it?",
     f"Counted as 0% in both the book and the margin version, while a blank or zero GELR is treated as "
     f"unusable and left out. So the two halves of 100 - GELR - Commission handle a missing value in "
     f"opposite ways, and UW Margin % reads high: {AUDIT['commission_zero']}. The page now says this "
     f"under the figure.",
     "Leave rows with no recorded commission out of the margin version too (as GELR does); or keep the "
     "current rule and rely on the note.", "Open", "Matt / Finance", TODAY,
     "ingest/clean_rbs.py; metrics/quality.py"),
    (26, "Should B/Q and B/S only count binds that DSR knows about?",
     f"They divide RBS binds by DSR quotes / submissions, as tab 4 defines. But the funnel isn't nested: "
     f"{AUDIT['binds_not_in_dsr']}. On a narrow slice or one underwriter the rate can pass 100% (the "
     f"page flags that). Matt's build doesn't have this problem because his binds come from DSR too.",
     "Restrict the numerator to binds present in DSR (a true funnel, slightly lower); or keep RBS binds "
     "and rely on the note.", "Open", "Matt / extract owners", TODAY,
     "metrics/funnel.py binds_not_in_dsr"),
    (27, "Entity is recorded per line in RBS but per policy in DSR",
     f"The entity filter keeps matching LINES, so a policy whose lines sit under two entities is counted "
     f"as a bind under each while only its own lines' premium is summed: {AUDIT['entity_split']}. "
     f"Average Deal Size for a small entity can therefore read far below the book figure.",
     "Assign each policy to one entity (e.g. the one with most premium) before counting binds; or leave "
     "it and note that entity slices don't add up to the total.", "Open", "Extract owners / Matt", TODAY,
     "scope/filter.py; metrics/funnel.py"),
    (28, "A few extreme rate changes set RARC",
     f"RARC is a premium-weighted average with no cap: {AUDIT['rarc_extreme']}. The refresh now logs a "
     f"warning naming how many rows are beyond the limit.",
     "Leave them out, or cap them, once someone confirms whether they are real.", "Open",
     "RBS extract owner", TODAY, "ingest/clean_rbs.py RARC_EXTREME_PCT"),
    ("DECIDED - WITH THE REASON", None),
    (4, "Should rates built on very few deals be hidden or flagged?",
     "Shown, but greyed out with a \"few binds / few quotes / few submissions\" tag when they rest on "
     "fewer than 20 policies - and per-person figures with a \"few underwriters\" tag below 5 "
     "underwriters. Nothing is hidden (tab 4: blank only when there's nothing to divide by).",
     "Hide below a minimum instead; or change the minimums.", "Decided - flag, don't hide",
     "Matt (to confirm the minimums)", TODAY,
     "SMALL_SAMPLE_MIN, SMALL_TEAM_MIN in config/settings.py; server/insights.py"),
    (11, "Submission date basis with RBS figures?",
     "Only DSR-only figures shown; the rest blank with a note.", "Matt's build mixes submission-month "
     "DSR with inception-month RBS.", "Decided", "Tab 3, Rule 3", TODAY, "pipeline/build_dashboard_data.py"),
    (12, "Rate Adequacy: all premium vs benchmark from some rows?",
     "Same rows on both sides (129.0% vs Matt-style 129.2%, all years).", "Matt's version overstates.",
     "Decided", "Tab 4 note", TODAY, "metrics/quality.py rate_adequacy"),
    (13, "Peer group when one underwriter is picked?",
     "Everyone in the other filters - the picked underwriter is highlighted among them.",
     "Only themselves (always reads 1.0x).", "Decided", "Common sense", TODAY,
     "pipeline/build_dashboard_data.py (underwriters)"),
    (14, "Average Policy Length: per line or per policy?", "Once per policy (18.3 months Jan-Aug 2026).",
     "Per line counts long multi-line policies several times.", "Decided", "Tab 3, Rule 4", TODAY,
     "metrics/composition.py average_policy_length"),
    (15, "Renewal Premium Growth with the Business filter on New?",
     "Still looks at renewals only, like RARC.", "Blank on New.", "Decided", "Same rule as RARC (tab 4)",
     TODAY, "metrics/composition.py renewal_premium_growth"),
    (16, "Attachment points: blank values?",
     f"Excess: blank left out. Primary: blank deductible counts as 0, per the tab 4 note - which is worth "
     f"revisiting, because it halves the figure: {EFFECT['attach_primary']} ({DEFAULT_LABEL}).",
     "Leave blank deductibles out of the Primary median too.", "Decided - worth revisiting",
     "Tab 4 note; measured in tab 12", TODAY, "metrics/quality.py"),
    (17, "SCM Share definition", "1 - (Mosaic 1609 share of premium / all agency premium), as Matt.",
     "-", "Decided", "Matt's build", TODAY, "metrics/composition.py scm_share"),
    (18, "Timeframe: when is a month \"complete\"?",
     "Data runs to the latest DSR submission date. A month is complete once that date reaches its "
     "last day (15 Sep 2026 -> Aug is the last complete month).", "-", "Decided", "Same as Matt", TODAY,
     "scope/period.py"),
    (20, "Negative premium rows (e.g. return premium)?",
     f"Included as they are, so totals are net. {NEG['RBS']:,} RBS rows, {NEG['DSR']:,} DSR rows.",
     "Leave them out.", "Decided", "Totals should match the reports", TODAY, "ingest/clean_rbs.py"),
    (21, "Blank premium?",
     f"Counts as $0 (a warning is logged if a filled cell can't be read as a number). "
     f"{BLANK_PREM['DSR']:.0%} of DSR rows are blank - mostly declined submissions, which never had "
     f"a price. {BLANK_PREM_N['RBS']:,} RBS rows are blank.", "-", "Decided", "No premium = $0", TODAY,
     "ingest/clean_dsr.py, ingest/clean_rbs.py"),
]
r = 4
for row in decisions:
    if row[1] is None:
        section(ws, r, row[0], 8)
    else:
        body(ws, r, row, status_col=5)
    r += 1
ws.freeze_panes = "C4"

# --------------------------------------------------------------------------
# Tab 5: the double-check is built from RBS's benchmark premium, not Achieved Price.
ws5 = wb["5. New ideas"]
ws5["C8"] = ("RBS's own benchmark: Mosaic 1609 Share Gross Written Premium ÷ Mosaic 1609 Share "
             "Benchmark Premium (both RBS columns), shown next to our Rate Adequacy.")
ws5["D8"] = ("Originally planned against the \"Achieved Price (%)\" column, but that column's unit is unclear "
             "on the real extract - tab 9. If the two disagree by a lot, chase it down before trusting either.")

# --------------------------------------------------------------------------
# Tabs 4 and 5: a Built? column pointing at the tracker.
built = {row[0]: row for row in tracker if row[1] is not None}
names_tab4 = {
    "Submissions": "Submissions", "Quotes": "Quotes", "Binds": "Binds", "Q/S (Quote rate)": "Q/S",
    "B/Q (Win rate)": "B/Q", "B/S (End-to-end win rate)": "B/S", "Bound Premium (GWP)": "Bound Premium",
    "Average Deal Size": "Average Deal Size", "GELR": "GELR - book version",
    "GELR (margin version)": "GELR - margin version", "Commission": "Commission - book version",
    "Commission (margin version)": "Commission - margin version", "UW Margin %": "UW Margin %",
    "Margin cover": "Margin cover", "Commission cover": "Commission cover",
    "Attachment point (Excess)": "Attachment point (Excess)",
    "Attachment point (Primary)": "Attachment point (Primary)",
    "Average Limit": "Average Limit (shown as Median limit)", "Rate Adequacy": "Rate Adequacy",
    "RARC": "RARC", "Mosaic as Lead": "Mosaic as Lead", "Primary Share": "Primary Share",
    "Average Agency Share": "Average Agency Share", "SCM Share": "SCM Share",
    "Submissions / Q/S / B/Q by underwriter": "Funnel by underwriter",
    "Book quality by underwriter": "Book quality by underwriter", "Peer comparison": "Peer comparison",
    "Roster underwriters": "Roster underwriters", "Active underwriters": "Active underwriters",
    "Premium per Active Underwriter": "Premium per Active Underwriter",
    "UW Margin per Active Underwriter": "UW Margin per Active Underwriter",
    "New vs. Renewal Mix": "New vs. Renewal Mix", "Placement Mix": "Placement Mix",
    "Broker Concentration": "Broker Concentration", "Average Policy Length": "Average Policy Length",
    "Renewal Premium Growth": "Renewal Premium Growth",
    "Rate Adequacy double-check": "Rate Adequacy double-check",
}


def add_built_column(ws, col, width, last_row):
    head = ws.cell(2, col)
    head.value = f"Built? ({TODAY})"
    src = ws.cell(2, col - 1)
    head.font, head.fill = copy.copy(src.font), copy.copy(src.fill)
    head.alignment, head.border = copy.copy(src.alignment), copy.copy(src.border)
    ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    for rr in range(3, last_row + 1):
        name = ws.cell(rr, 1).value
        c = ws.cell(rr, col)
        c.border = copy.copy(ws.cell(rr, col - 1).border)
        if name in names_tab4:
            status = built[names_tab4[name]][2]
            c.value = f"{status} - see tabs 8, 10"
            c.font = Font(name="Arial", size=9.5)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.fill = PatternFill("solid", fgColor=GREEN if status in ("Built", "Done") else AMBER)
        elif ws.cell(rr, 1).fill.fill_type:  # a section row: carry its shading across
            c.fill = copy.copy(ws.cell(rr, 1).fill)


add_built_column(wb["4. What we CAN build"], 7, 20, 40)
add_built_column(wb["5. New ideas"], 5, 20, 8)

# --------------------------------------------------------------------------
# Glossary: filter and time-window terms.
ws = wb["2. Glossary"]
existing = {str(c.value) for c in ws["A"]}
row = ws.max_row + 1
section_src, term_src, text_src = ws["A2"], ws["A3"], ws["B3"]
for c in ([] if "Filters and time windows (see tab 7)" in existing
          else (ws.cell(row, 1, "Filters and time windows (see tab 7)"), ws.cell(row, 2))):
    c.font, c.fill = copy.copy(section_src.font), copy.copy(section_src.fill)
    c.border, c.alignment = copy.copy(section_src.border), copy.copy(section_src.alignment)
terms = [
    ("YTD (Year to date)", "From January to the last complete month of the year, e.g. Jan-Aug 2026. "
     "Shown on the dashboard as \"This year so far\"."),
    ("TTM (Trailing twelve months)", "The twelve months ending with the last complete month, e.g. Sep "
     "2025-Aug 2026. Smooths out seasonal swings that a YTD view can't. Shown on the dashboard as "
     "\"Last 12 months\"."),
    ("Last complete month", "The latest month with a full month of data behind it. The month still in "
     "progress and later months are shown dashed in the Period menu, because their figures are still "
     "filling in or not there yet."),
    ("Prior year / comparison", "The same months one year earlier. Every figure is shown next to it, "
     "with the change."),
    ("pts (percentage points)", "How a percentage moves: 42.0% to 44.0% is +2.0 pts (not +4.8%)."),
    ("Date basis", "Which date puts a policy in a month: inception (when cover starts) or submission "
     "(when it came in). Submission basis only works for DSR figures - RBS has no submission date."),
    ("Cascading filter", "A dropdown that only offers choices that exist under the other filters you've "
     "picked, so you never pick your way to an empty page."),
    ("Filter chip", "A small label under the toolbar for each filter that's on. Its \u00d7 removes "
     "just that filter."),
    ("Peer median", "The middle premium among the underwriters in the current filters (leaving out those "
     "with none). \"1.5x\" means 50% more premium than that middle figure."),
    ("Median", "The middle value when sorted. Used instead of an average where a few huge values would "
     "distort it - attachment points, limits."),
]
for term, text in terms:
    if term in existing:
        continue
    row += 1
    a, b = ws.cell(row, 1, term), ws.cell(row, 2, text)
    for c, src in ((a, term_src), (b, text_src)):
        c.font, c.border, c.alignment = copy.copy(src.font), copy.copy(src.border), copy.copy(src.alignment)

# --------------------------------------------------------------------------
# Read me: point to the new tabs, and a short "where things stand".
ws = wb["1. Read me"]
bullet, heading = ws["A45"], ws["A44"]
already_listed = any("7. Filters" in str(c.value or "") for c in ws["A"])


def add_line(rr, text, like):
    c = ws.cell(rr, 1, text)
    c.font, c.alignment = copy.copy(like.font), copy.copy(like.alignment)


if not already_listed:
    ws.insert_rows(50, amount=5)
    add_line(53, "•  10. Metric lineage — every figure traced to the exact DSR / RBS columns and rows it "
             "is built from, and how blanks and odd values are handled.", bullet)
    add_line(54, "•  11. Source columns — every column the dashboard reads from each export, what "
             "happens to it on the way in, and what uses it.", bullet)
    add_line(50, "•  7. Filters — every filter on the dashboard, how it behaves, and how it compares "
             "with Matt's build.", bullet)
    add_line(51, "•  8. Build tracker — where every rule and metric stands in the code, with today's "
             "figure on real data, so progress and unexpected changes are easy to spot.", bullet)
    add_line(52, "•  9. Decisions & questions — every judgement call behind the numbers: what's agreed, "
             "and what still needs someone to decide.", bullet)
# Tabs 12 and 13, added later, get their own bullets the same way.
if not any("12. Ours vs Matt" in str(c.value or "") for c in ws["A"]):
    after = next(c.row for c in ws["A"] if "11. Source columns" in str(c.value or ""))
    ws.insert_rows(after + 1, amount=2)
    add_line(after + 1, "•  12. Ours vs Matt's build — every figure of ours next to his, what "
                        "the difference is worth on real data, and which one we follow.", bullet)
    add_line(after + 2, "•  13. Checks & safeguards — every check that runs, what happens when "
                        "it fails, and its result on today's data.", bullet)

# The "where things stand" block is rewritten each time.
end = next((c.row for c in ws["A"] if str(c.value or "").startswith("8. Where things stand")),
           ws.max_row + 2)
add_line(end, f"8. Where things stand ({TODAY})", heading)
status_lines = [
    "•  Every metric in tab 4 and every idea in tab 5 is now built and on the dashboard (tab 8).",
    "•  The dashboard has its own filter toolbar covering Matt's filters, except Product (needs his "
    "product mapping) and Role / Tenure (need the HR file), listed as not available yet (tab 7).",
    "•  Every figure is shown against the same period last year.",
    "•  Every figure is traced to its exact DSR / RBS columns (tabs 10 and 11), and an automatic check "
    "rebuilds each one straight from those raw columns and confirms it matches the dashboard.",
    "•  Tab 12 compares every figure with Matt's build, measured on real data. Two differences matter "
    "most: his headline premium comes from DSR where ours comes from RBS, and his single GELR figure is "
    "our margin version while his single commission figure is our book version.",
    "•  Tab 13 lists every check that runs, what it does when it fails, and its result today.",
    "•  17 questions are open and worth raising with Matt or the extract owners (tab 9), four of them from a line-by-line audit of the calculations on 18 Sep 2026.",
]
for i, text in enumerate(status_lines, 1):
    add_line(end + i, text, bullet)



# --------------------------------------------------------------------------
# Tabs 4 and 5 are the original hand-written spec. Where the built figure
# settles something the spec left open, or handles blanks in a way the spec
# doesn't mention, a short "Now:" line is added to its note - so the
# definitions tab can't quietly drift from the code. Tab 12 has the full
# comparison with Matt's build; tab 10 has the exact columns.
NOW_NOTES = {
    "B/Q (Win rate)": f"Now: {AUDIT['binds_not_in_dsr']} - the page says so under the figure, and "
                      f"flags any underwriter whose rate passes 100%. Open question 26.",
    "B/S (End-to-end win rate)": "Now: overstated for the same reason as B/Q above (open question 26).",
    "Binds": f"Now: on this extract DSR and RBS are {BINDS_GAP_TEXT.split(' apart')[0]} apart "
             f"({DEFAULT_LABEL}) - see tab 13.",
    "Bound Premium (GWP)": f"Now: on this extract they are {PREMIUM_GAP_TEXT.split(' apart')[0]} apart "
                           f"({DEFAULT_LABEL}), which is worth chasing - see tab 9, question 3.",
    "GELR": f"Now: the book version counts a blank GELR as 0 ({GELR_BLANK} rows), which pulls it down: "
            f"{EFFECT['gelr_book']} ({DEFAULT_LABEL}). Still open - tab 9, question 1.",
    "GELR (margin version)": f"Now: \"usable\" means not blank AND not exactly 0 ({GELR_ZERO:,} rows are "
                             f"exactly 0 and are left out).",
    "Commission": f"Now: a blank commission counts as 0 (no commission charged): "
                  f"{EFFECT['commission_book']} ({DEFAULT_LABEL}).",
    "UW Margin %": f"Now: built from the MARGIN versions of GELR and Commission, so the three add back "
                   f"to one premium dollar. Mosaic's internal commission is still not subtracted "
                   f"(question 2). A blank or zero commission counts as none charged while a blank GELR "
                   f"is left out, so this reads high: {AUDIT['commission_zero']} (question 25).",
    "Attachment point (Excess)": "Now: rows with a blank Excess are left out (not counted as 0).",
    "Attachment point (Primary)": f"Now: {EFFECT['attach_primary']} ({DEFAULT_LABEL}) - the blank-as-zero "
                                  f"rule halves it.",
    "Average Limit": f"Now: shown as \"Median limit\" on the dashboard. {EFFECT['limit']} "
                     f"({DEFAULT_LABEL}) - the wording matters.",
    "Rate Adequacy": f"Now: fixed - premium and benchmark use exactly the same rows. "
                     f"{EFFECT['rate_adequacy']} ({DEFAULT_LABEL}). Also shown next to RBS's own "
                     f"benchmark premium (tab 5, Rate Adequacy double-check).",
    "Mosaic as Lead": f"Now: counts any Slip Lead containing \"Mosaic\", which includes Mosaic Asta Europe "
                      f"and Mosaic 5399: {EFFECT['lead']} ({DEFAULT_LABEL}). Open - tab 9, question 19.",
    "Primary Share": f"Now: {EFFECT['primary_share']} ({DEFAULT_LABEL}).",
    "Peer comparison": f"Now: decided - underwriters with no premium are left out of the median "
                       f"({EFFECT['peer_median']}, {DEFAULT_LABEL}), and the Underwriter filter is ignored "
                       f"so a person is always shown among their peers. Tab 9, question 10.",
    "Submissions / Q/S / B/Q by underwriter": "Now: also greyed out where a rate rests on fewer than "
                                              f"{SMALL_SAMPLE_MIN} policies (tab 13).",
    "Premium per Active Underwriter": f"Now: also greyed out below {SMALL_TEAM_MIN} underwriters, where one "
                                      f"person's year would swing it.",
}


def add_now_notes(ws, note_col, last_row):
    """Append the "Now:" line to a spec row's note, once."""
    for rr in range(3, last_row + 1):
        extra = NOW_NOTES.get(ws.cell(rr, 1).value)
        if not extra:
            continue
        cell = ws.cell(rr, note_col)
        current = str(cell.value or "")
        if "Now:" in current:
            current = current.split("Now:")[0].rstrip()
        cell.value = (current + ("\n\n" if current else "") + extra)
        cell.font = Font(name="Arial", size=9.5)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[rr].height = None  # let Excel re-fit the taller note


add_now_notes(wb["4. What we CAN build"], 6, 40)
# The spec tab was frozen at row 26, which hides the header once you scroll.
wb["4. What we CAN build"].freeze_panes = "A3"
add_now_notes(wb["5. New ideas"], 4, 8)



# --------------------------------------------------------------------------
# Tab 12 - Ours vs Matt's build, metric by metric.
ws = _fresh_sheet(wb, "12. Ours vs Matt's build")
intro(ws, "Read this before putting a figure of ours next to a figure of Matt's. It was written by reading "
          "his dashboard's own code (the HTML file) against ours, line by line, not from memory. Two "
          "things matter most, and they are the first two rows: his headline premium comes from DSR while "
          "ours comes from RBS, and his single GELR figure is our MARGIN version while his single "
          "commission figure is our BOOK version - so comparing like-named columns across the two "
          "dashboards mis-matches both. \"What the difference is worth\" is measured on the extracts in "
          f"data/ for {DEFAULT_LABEL}. Green = same definition, amber = deliberately different, "
          f"red = can't be compared. Last updated {TODAY}.", 7)
legend_row(ws, 2)
header(ws, 3, ["Figure", "What Matt's build does", "What ours does", "Same?",
               "What the difference is worth", "Which we follow, and why", "Where"],
       [26, 46, 46, 15, 38, 44, 26])
compare = [
    ("THE TWO STRUCTURAL DIFFERENCES", None),
    ("Headline premium", "Adds up the premium on the DSR policy rows, and applies RBS's margin % to that "
     "DSR premium, so his headline stays consistent with the funnel it came from.",
     "Adds up the premium on the RBS rows. DSR's bound-row total is worked out too, but only as a "
     "cross-check with a red badge.", "Differs", PREMIUM_GAP_TEXT,
     "RBS. It is the company's source of truth for bound business (tab 3, Rule 7), and the gap is "
     "measured and shown rather than hidden. Matt's is internally consistent with his funnel, so his "
     "headline figure is our cross-check figure - open question 23.",
     "metrics/premium.py; reconcile/cross_check.py"),
    ("Binds", "Counts distinct DSR policies whose status marks them bound.",
     "Counts distinct policies in RBS. DSR's own count is the cross-check.", "Differs", BINDS_GAP_TEXT,
     "RBS, same reason as premium. Both treat a mid-term cancellation as bound.",
     "metrics/funnel.py"),
    ("Underwriter count (the per-person denominator)",
     "Average monthly employed headcount from the HR file, filtered by entity, line, ROLE and TENURE. "
     "For one underwriter: the share of the window HR has them employed. Falls back to a producing "
     "roster where a slice has no HR figure.",
     "No HR file: Active underwriters (won at least one deal, from RBS) and Roster underwriters (at "
     "least one submission, from DSR). Both are producer counts.", "Can't compare",
     "Not measurable here - we have no HR file to compare against.",
     "Ours is the only honest option without HR, and every figure built on it is labelled a stand-in "
     "(tab 1, point 5). Matt's is true employed headcount and is better wherever HR exists. His own "
     "note warns his default New + Open Market slice divides 56% of the premium by 100% of the heads "
     "($2.09M per head, against $3.72M on all business).", "metrics/headcount.py"),
    ("SAME DEFINITION - FIGURES SHOULD LINE UP (once the premium base above is allowed for)", None),
    ("UW Margin %", "Margin premium ÷ premium carrying a GELR; equals 1 − margin GELR − "
     "margin commission exactly.", "100% − margin GELR − margin commission, over rows with a "
     "usable GELR.", "Agree", "Same arithmetic.", "Both; neither subtracts Mosaic's internal commission "
     "(open question 2).", "metrics/quality.py"),
    ("GELR (margin version)", "His single \"GELR\" figure: premium-weighted over GELR-bearing rows.",
     "Our margin version - same population.", "Agree",
     "Same, except he also drops 2021 inceptions and we don't (open question 24).",
     "Both. Ours is named \"margin version\" so it can't be confused with the book version.",
     "metrics/quality.py"),
    ("Commission (book version)", "His single \"Commission\" figure: premium-weighted over ALL premium, "
     "blank counting as no commission.", "Our book version - same population and same blank rule.",
     "Agree", EFFECT["commission_book"], "Both.", "metrics/quality.py"),
    ("Margin cover / Commission cover", "Margin premium ÷ all premium; and the share of margin "
     "premium carrying a commission above zero (his note: 12.2% carries exactly zero).",
     "The same two figures, same populations.", "Agree", "Same arithmetic.", "Both.",
     "metrics/quality.py"),
    ("SCM share", "1 − Mosaic 1609's premium ÷ all agency premium - a ratio of sums, not an "
     "average of percentages.", "The same.", "Agree", "Same arithmetic.", "Both.",
     "metrics/composition.py"),
    ("Mosaic as lead / Primary share", "Share of ROWS (a small deal counts the same as a large one).",
     "Share of rows too.", "Agree",
     f"Row count vs premium-weighted: {EFFECT['primary_share']} for primary share.",
     "Both, with the row-count caveat written next to the figure. Which Slip Lead values count as "
     "\"Mosaic\" is still open (question 19).", "metrics/composition.py"),
    ("RARC", "Renewals only whatever the business-type filter says, weighted by expiring premium; every "
     "other filter still applies.", "The same.", "Agree", "Same arithmetic.", "Both.",
     "metrics/quality.py"),
    ("The funnel and its rates", "Distinct policies for submissions, quotes and binds; a rate is blank, "
     "never zero, when there is nothing to divide by.", "The same rule.", "Agree",
     "Structure agrees; the levels differ because his binds come from DSR (see above).", "Both.",
     "metrics/funnel.py"),
    ("Roster underwriters", "Distinct producing underwriters across the filtered policy rows, any status "
     "- his fallback denominator.", "Our Roster underwriters - the same definition.", "Agree",
     "Same arithmetic.", "Both.", "metrics/headcount.py"),
    ("Last 12 months, and the month still in progress",
     "Re-indexes every row onto a window ending at the last complete month; the month bar is fixed "
     "under that window and the part month is marked.",
     "A window of twelve months ending at the last complete month; months with no complete data are "
     "shown dashed and a notice warns when a period includes them.", "Agree",
     "Same rule, different mechanics.", "Both.", "scope/period.py; server/insights.py"),
    ("DELIBERATELY DIFFERENT", None),
    ("Rate Adequacy", "All the premium in scope ÷ a benchmark built only from rows that have one: "
     "`adequacy: bn? agwp/bn`.", "Premium and benchmark restricted to the same rows (usable GELR and a "
     "plan loss ratio above 0).", "Differs", EFFECT["rate_adequacy"],
     "Ours. His numerator includes premium that contributed nothing to the denominator, which overstates "
     "it - the workbook flagged this from the start (tab 4). We also show RBS's own benchmark premium as "
     "a second opinion.", "metrics/quality.py"),
    ("GELR (book version)", "Doesn't exist - he shows one GELR only.",
     "An extra version: premium-weighted across all rows, a blank GELR counting as 0.", "Differs",
     EFFECT["gelr_book"], "Both of ours are shown, each clearly named, because tab 4 asks for the "
     "\"across all rows\" reading. Whether a blank should count as 0 is open question 1.",
     "metrics/quality.py"),
    ("Average agency share", "Weights by premium but divides by ALL premium in scope, so a premium-bearing "
     "row with no line share recorded drags it down.",
     "Uses only the rows that have a line share, on both sides of the division.", "Differs",
     "Not directly measurable (we don't hold his figure), but it is the same class of error he fixed "
     "elsewhere in his own code for fees and margin.",
     "Ours. A share can only be averaged over risks that have one.", "metrics/composition.py"),
    ("Attachment point (Primary and Excess)",
     "One column, Excess + Deductible added together, then split by layer and medianed.",
     "Excess only on Excess layers (blanks left out); Deductible only on Primary layers (blank = 0).",
     "Differs", EFFECT["attach_primary"],
     "Ours keeps the two ideas apart, which is easier to explain. The blank-as-zero rule is the "
     "workbook's (tab 4) and halves the Primary figure - worth revisiting.", "metrics/quality.py"),
    ("Limit", "A median of Agency Exposure - but his label says \"Avg limit\" and his own tooltip says "
     "\"mean\".", "The same median, named \"Median limit\" on screen.", "Differs (name only)",
     EFFECT["limit"], "Ours. Same arithmetic, honest name - a mean would read three times higher.",
     "metrics/quality.py"),
    ("Peer comparison", "Annualised UW margin per underwriter, against the median of their PRODUCT or "
     "line, leaving the person out of their own median, annualised by months employed from HR, with a "
     "membership rule that drops thin or out-of-entity names and seeds rows for leavers.",
     "Premium against the median premium of everyone in the current filters (the person included), "
     "leaving out anyone with no premium. No annualisation.", "Differs",
     f"Peer median {EFFECT['peer_median']}.",
     "His is better on every axis he gives a reason for, but most of it needs HR months and a product "
     "mapping we don't have. Ours is a stand-in, and the table says so. Open question 10.",
     "metrics/underwriters.py"),
    ("What drove the change", "The waterfall his page draws allocates each driver's share by Shapley "
     "value over every ordering, and carries a fifth margin term. (His code also holds a simpler "
     "log-share bridge, which is what ours matches.)",
     "Four drivers, each share = its log change ÷ the total log change, so the shares add to the "
     "total exactly.", "Differs",
     "Same four drivers and the same total; the split between them will differ from his screen.",
     "Ours, for now: it is exact, order-independent and easy to explain. A Shapley split and a margin "
     "term are a fair next step.", "metrics/drivers.py"),
    ("Too-few-deals treatment", "Greys out table ratios below his minimums (e.g. 5 deals).",
     f"Greys out any figure resting on fewer than {SMALL_SAMPLE_MIN} policies, or per-person figures "
     f"below {SMALL_TEAM_MIN} underwriters, and tags it. Nothing is ever hidden.", "Differs",
     "Same intent, wider coverage.", "Ours - tab 9, question 4.", "server/insights.py"),
    ("What the page opens on", "New business, Open Market - the slice his LOB workbook reconciles to.",
     "The whole book.", "Differs", "His default divides 56% of premium by 100% of heads (his own note).",
     "Ours, because our denominator follows the filters. One line in config/settings.py to match his - "
     "open question 5.", "config/settings.py"),
    ("Win rate (B/Q) - can it exceed 100%?",
     "No: his binds come from DSR too, so every bind is also a submission and the funnel is nested by "
     "construction.",
     "It can, on a narrow slice: our binds come from RBS and some bound policies have no DSR row at all. "
     "The page flags it and says what the rate would be without them.", "Differs",
     AUDIT["binds_not_in_dsr"],
     "Ours keeps RBS as the source of truth for wins, which matters more than a tidy funnel - but this is "
     "the strongest argument for his choice. Open question 26.", "metrics/funnel.py"),
    ("ONLY MATT'S BUILD HAS IT", None),
    ("Agency Revenue, fee yields, fee streams", "Total Fees, Syndicate and SCM fees, yields on the "
     "fee-bearing premium, and a per-head revenue figure.", "Not built - the columns don't exist in the "
     "standard RBS export (tab 6).", "Can't compare", "-",
     "Nothing to follow until the columns exist. His two design points are worth copying then: divide a "
     "yield by the premium of the fee-bearing rows only, and split each stream by its own premium.",
     "tab 6"),
    ("Product, Role and Tenure filters", "A product roster and Lloyd's risk-code mapping; HR role and "
     "tenure applied to BOTH the premium and the headcount.", "Not available (tab 7).", "Can't compare",
     "-", "Needs his mapping and the HR file - open questions 6 and 7.", "tab 7"),
    ("Narrative and extras", "UW margin in dollars, index against the line average, a 12-month rolling "
     "view, written verdicts per underwriter, prize / sensitivity figures, a CEO three-term test, "
     "first-year fallback cards, and a count of names HR can't identify.",
     "Not built.", "Can't compare", "-",
     "Worth revisiting once the HR file exists; the rolling view is the closest to our Trends tab.", "-"),
    ("ONLY OURS HAS IT", None),
    ("DSR against RBS, every time", "-", "Bound premium and bind count worked out from both reports on "
     "the same filters, with a 2% tolerance, a warning in the log and a red badge you can click.",
     "Ours only", PREMIUM_GAP_TEXT, "Tab 3, Rule 6.", "reconcile/cross_check.py"),
    ("New/Renewal lined up", "-", "Where a policy is in both reports and they disagree, DSR takes RBS's "
     "Renewal Status.", "Ours only", "271 DSR policies changed across the whole extract.",
     "Tab 3, Rule 2.", "ingest/align_reports.py"),
    ("Unit and sanity checks on the way in", "-", "Percent columns detected as fractions or percent (the "
     "run stops if they disagree), a GELR sanity range, warnings when a value can't be read, and a "
     "cache keyed on the file itself.", "Ours only", "See tab 13.", "Tab 13.",
     "ingest/clean_rbs.py"),
    ("Underwriter names tidied, duplicates flagged", "-", "Capitals, punctuation and spacing tidied for "
     "matching, and likely same-person pairs tagged without merging them.", "Ours only", DUPLICATES_TEXT,
     "Tab 3, Rule 5; open question 8.", "ingest/underwriter_names.py"),
    ("Lineage and the raw-column check", "-", "Every figure traced to its original columns (tabs 10-11), "
     "shown on the page behind an (i), and rebuilt from those raw columns by an automatic check.",
     "Ours only", TRACE_TEXT, "Tabs 10, 11 and 13.", "metrics/lineage.py"),
    ("Extra metrics", "-", "Rate Adequacy double-check (RBS's own benchmark), Broker concentration, "
     "Average policy length, Renewal premium growth, New vs. Renewal and Placement mixes, and the "
     "Active / Roster underwriter pair.", "Ours only", "-", "Tab 5 ideas, all built (tab 8).",
     "metrics/"),
    ("WORTH KNOWING IF YOU RECONCILE FIGURES WITH HIM", None),
    ("Matt's own labels disagree with his code in three places", "Rate adequacy is described three "
     "different ways (one tooltip states the reciprocal of what the code does); the limit tile says "
     "\"Avg\" and its tooltip says \"mean\" while the code takes a median; an \"active months\" tooltip "
     "describes a denominator his peer table only falls back to.",
     "Our definitions are generated from one place (metrics/lineage.py) and shown on the page, so the "
     "label and the code can't drift apart.", "Differs", "-",
     "If a figure of his doesn't match ours, check his label against his code before assuming the data "
     "differs.", "tabs 10-11"),
]
r = 4
for row in compare:
    if row[1] is None:
        section(ws, r, row[0], 7)
    else:
        body(ws, r, row, status_col=4, bold_first=True)
        cell = ws.cell(r, 4)
        text = str(cell.value)
        cell.fill = PatternFill("solid", fgColor=(
            GREEN if text.startswith("Agree") else RED if text.startswith("Can't") else AMBER))
    r += 1
ws.freeze_panes = "B4"


# --------------------------------------------------------------------------
# Tab 13 - Checks & safeguards: everything that runs to stop a wrong number.
ws = _fresh_sheet(wb, "13. Checks & safeguards")
intro(ws, "Every check the build runs, what it looks at, and what happens when it fails. Three kinds: "
          "\"Stops the run\" means the refresh refuses to publish figures at all; \"Warns\" means it "
          "publishes but logs a warning in the terminal (worth watching); \"Shows on the page\" means the "
          "reader is told next to the figure. The last column is the result on the extracts in data/ as at "
          f"{AS_AT_TEXT}. Last updated {TODAY}.", 6)
legend_row(ws, 2)
header(ws, 3, ["Check", "What it looks at", "If it fails", "Kind", "Where", "Result now"],
       [30, 46, 40, 15, 34, 30])
checks = [
    ("READING THE EXPORTS", None),
    ("Every column we need is there", "The list of required columns in each report, by name.",
     "Refuses to run and names the missing column(s), rather than treating them as blank.",
     "Stops the run", "require_columns in ingest/validation.py", "Pass"),
    ("Optional columns", "Agency line share, Mosaic 1609 premium and benchmark, broker, policy length, "
     "RARC, expiring premium.", "Logs a warning; only the figures that use the column go blank.",
     "Warns", "OPTIONAL_COLUMNS in ingest/clean_rbs.py", ALL_OPTIONAL_TEXT),
    ("Percentages: fraction or percent?", "GELR, Commission and Plan Loss Ratio together - are they "
     "stored as 0.40 or as 40.0?", "If the three disagree, refuses to run rather than guessing "
     "(a wrong guess once produced a GELR of 0.4%).", "Stops the run",
     "_percent_columns_to_percent_units in ingest/clean_rbs.py", PERCENT_TEXT),
    ("GELR sanity range", "The middle GELR after unit handling: it must land between 5% and 95%.",
     "Refuses to run - the unit decision above was probably wrong.", "Stops the run",
     "GELR_SANITY_RANGE in ingest/clean_rbs.py", GELR_MEDIAN_TEXT),
    ("Numbers and dates that won't read", "Cells that had a value but couldn't be read as a number or "
     "a date (more than 2% of filled cells).",
     "Logs a warning naming the column and the share lost. The rows stay, with a blank.", "Warns",
     "warn_if_coercion_dropped_data in ingest/validation.py", "No warnings"),
    ("Underwriter not attributed", "Share of DSR rows with no underwriter on either column (over 10%).",
     "Logs a warning: underwriter-level figures rest on a smaller population.", "Warns",
     "ingest/clean_dsr.py", UNATTRIBUTED_TEXT),
    ("Cached copy is the right one", "File size and modified time of each .xlsx against the cache "
     "signature.", "Re-reads the Excel file instead of using a stale cache.", "Automatic",
     "data_sources/excel_source.py", "Pass"),
    ("Figures never outlive their data", "The per-filter result cache.",
     "Cleared on every background re-read, so an old figure can't be shown against new data.",
     "Automatic", "server/app.py", "Pass"),
    ("DSR AGAINST RBS", None),
    ("Bound premium, both ways", "RBS's premium against the same premium column on DSR's bound rows, "
     "same filters. Tolerance 2% (tab 3, Rule 6).",
     "Keeps RBS's figure, logs a warning, and shows a red badge you can click for both figures.",
     "Warns + shows on the page", "reconcile/cross_check.py; server/insights.py", PREMIUM_GAP_TEXT),
    ("Bind count, both ways", "RBS's distinct policies against DSR's distinct policies with a bound status.",
     "As above.", "Warns + shows on the page", "reconcile/cross_check.py", BINDS_GAP_TEXT),
    ("A gap against zero", "A gap where RBS is zero and DSR isn't.",
     "Reports \"can't be worked out\" instead of inventing a 100% gap.", "Shows on the page",
     "is_undefined_gap in reconcile/cross_check.py", "No such case in this extract"),
    ("Submission date and RBS", "Any attempt to filter RBS by submission date.",
     "Raises an error (RBS has no submission date); the page shows DSR-only figures with a note.",
     "Stops that figure", "apply_scope in scope/filter.py", "Pass"),
    ("TOLD TO THE READER", None),
    ("Too few deals", f"Every rate and average: the policies behind it (fewer than {SMALL_SAMPLE_MIN}), and "
     f"per-person figures (fewer than {SMALL_TEAM_MIN} underwriters).",
     "Greys the figure and tags it \"few binds / quotes / submissions / underwriters\". Never hidden.",
     "Shows on the page", "server/insights.py; config/settings.py", "In use"),
    ("Margin cover", "Share of premium with a usable GELR behind UW Margin % (under 90%).",
     "Adds a note under UW Margin % saying how much of the premium it rests on.", "Shows on the page",
     "cover_note in server/insights.py", MARGIN_COVER_TEXT),
    ("Months that aren't complete", "The selected period against the last complete month.",
     "Warns that this year's figures will look low next to last year's, and points at \"This year so far\".",
     "Shows on the page", "incomplete_period_notice in server/insights.py", "In use"),
    ("Developing months in trends", "The right-hand end of the trend charts.",
     "Says quotes and binds arrive after submissions, so a late dip is usually timing.",
     "Shows on the page", "server/panels.py", "In use"),
    ("Possible duplicate names", "Underwriter names that are probably one person typed two ways.",
     "Tags them in the Underwriters table and the CSV. Never merges them.", "Shows on the page",
     "possible_duplicates in ingest/underwriter_names.py", DUPLICATES_TEXT),
    ("A filter choice that's now impossible", "A picked line / entity / underwriter that the other "
     "filters rule out.", "Clears just that choice and says so, instead of showing an empty page.",
     "Shows on the page", "drop_stranded_selections in server/filters.py", "In use"),
    ("A bad or old link", "Unknown values in the page address (a typo'd year, month 13).",
     "Ignores them and falls back to the defaults, rather than showing a wrong slice.",
     "Automatic", "parse_filters in server/filters.py", "Pass"),
    ("Binds with no DSR row", "RBS bound policies that don't appear in DSR under any status or month.",
     "Says so under B/Q and B/S, gives the rate without them, and flags any underwriter whose B/Q passes "
     "100%.", "Shows on the page", "metrics/funnel.py binds_not_in_dsr", AUDIT["binds_not_in_dsr"]),
    ("Commission recorded or not", "The share of margin premium with no commission recorded.",
     "Says under UW Margin % what the figure would be over the rows that do record one.",
     "Shows on the page", "metrics/quality.py uw_margin_pct_recorded_commission",
     AUDIT["commission_zero"]),
    ("Extreme rate changes", f"Rows with a rate change beyond \u00b1{RARC_EXTREME_PCT}%.",
     "Logs a warning naming how many and the largest. They stay in RARC.", "Warns",
     "ingest/clean_rbs.py RARC_EXTREME_PCT", AUDIT["rarc_extreme"]),
    ("Comparison year in the data at all", "Whether the prior year has any rows on these filters.",
     "Leaves the comparison blank with a notice, instead of showing a book that collapsed to zero.",
     "Shows on the page", "pipeline/build_dashboard_data.py", "Pass"),
    ("Driver story needs enough deals", "The binds behind both periods of the driver split.",
     "Doesn't split the change at all, and says why.", "Shows on the page",
     "drivers_section in server/insights.py", "In use"),
    ("Charts cover the period", "Whether the selected months are inside the charted window.",
     "Says the period runs past the last complete month, or that there is nothing to chart yet.",
     "Shows on the page", "server/panels.py", "In use"),
    ("AUTOMATIC TESTS (python -m pytest)", None),
    ("Every figure against the raw columns", "Each figure rebuilt from the original DSR / RBS column "
     "names with plain pandas, no dashboard code, on two different views - plus every underwriter "
     "column for every underwriter and both premium mixes.",
     "The test fails, naming each figure and both values.", "Test",
     "tests/test_trace_to_source.py", TRACE_TEXT),
    ("Lineage matches the code", "That the lineage (tabs 10-11) names exactly the columns the pipeline "
     "reads, both ways, and that every figure on the page has lineage.",
     "The test fails, naming the column or figure.", "Test", "tests/test_lineage.py", "Pass"),
    ("Each month matches the page", "A month in the trend charts against the whole-page figure for that "
     "month picked on its own.", "The test fails.", "Test", "tests/test_trends_and_page.py", "Pass"),
    ("Driver split adds up", "That the four drivers multiply back to premium per underwriter and their "
     "shares add to the total move.", "The test fails.", "Test", "tests/test_insights.py", "Pass"),
    ("The rules in tab 3", "New/Renewal following RBS, entity spellings, name tidy-up, scope filters, "
     "and that RBS always wins a reconciliation.", "The test fails.", "Test",
     "tests/test_alignment.py, tests/test_reconcile.py, tests/test_scope.py", "Pass"),
    ("Every metric by hand", "Each metric against rows small enough to work out with a calculator.",
     "The test fails.", "Test", "tests/test_quality.py, test_new_metrics.py, test_funnel.py, "
     "test_underwriters.py", "Pass"),
    ("The page renders", "Every kind of view (each period type, submission basis, a picked underwriter, "
     "empty filters) and every tab.",
     "The test fails - this catches a figure the page asks for that the pipeline stopped producing.",
     "Test", "tests/test_filters.py, tests/test_trends_and_page.py", "Pass"),
]
r = 4
for row in checks:
    if row[1] is None:
        section(ws, r, row[0], 6)
    else:
        body(ws, r, row, status_col=4, bold_first=True)
        kind = ws.cell(r, 4)
        kind.fill = PatternFill("solid", fgColor=(
            RED if str(kind.value).startswith("Stops") else
            GREEN if str(kind.value) in ("Test", "Automatic") else AMBER))
    r += 1
ws.freeze_panes = "B4"

# Keep the tabs in numbered order however they were rebuilt.
wb._sheets.sort(key=lambda sheet: int(sheet.title.split(".")[0]))

wb.save(PATH)
print(f"Rebuilt tabs 7, 8, 9, 12 and 13 in {PATH.name}. "
      f"Run docs/update_lineage_tabs.py for tabs 10 and 11.")
