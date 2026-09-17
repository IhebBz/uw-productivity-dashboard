# UW Productivity Dashboard (DSR funnel + RBS quality metrics)

Rebuild of Matt Radus's UW Productivity Dashboard prototype, scoped to what
the company's real data can actually support today. Full background and
every decision behind this scope lives in `UW_Dashboard_Metrics_Inventory.xlsx`
(the metrics workbook) - read that first if a rule in this code looks odd,
since the reason is almost always written down there, not here.

## The two source reports

- **DSR** - every risk that came in, won or not. Source of truth for the
  funnel (Submissions, Quotes, Q/S, B/Q, B/S).
- **RBS** - only risks we won. Source of truth for bound premium, binds, and
  every quality/pricing metric (GELR, Commission, UW Margin %, Rate Adequacy,
  RARC). See `reconcile/cross_check.py` - RBS wins whenever the two disagree.

Not used: the HR headcount file (not available; see `metrics/headcount.py`
for the two local stand-ins used instead) and Agency Revenue (the source
columns don't exist in the standard RBS export at all).

## Swapping Excel for Redshift

Today's data comes from Excel files (`data_sources/excel_source.py`). The
plan is a daily feed from Redshift, matching the report's refresh rate. When
that's ready:

1. Finish `data_sources/redshift_source.py` (the file already exists as a
   stub with the right method signatures).
2. Change one line wherever `ExcelSource(...)` is currently constructed to
   `RedshiftSource(...)` instead.

Nothing in `ingest/`, `reconcile/`, `metrics/`, or `pipeline/` needs to
change - they only ever depend on the `DataSource` interface in
`data_sources/base.py`, never on Excel or Redshift directly.

## How to run it

1. `pip install -r requirements.txt`
2. Put `DSR.xlsx` and `RBS.xlsx` in the `data/` folder (already there,
   holding the sample files used to build and test this).
3. Either:
   - **One-off check**: `python run_pipeline_once.py` - prints a summary
     and saves the full result to `outputs/latest_result.json`.
   - **Background mode** (mimics how this runs inside MosAIc Chat):
     `python run_server.py`, then open `http://localhost:8000`. A
     background thread re-reads the data every 5 minutes (see
     `REFRESH_SECONDS` in `server/app.py` - a stand-in for "daily"); the
     page works out the figures for whatever filters are picked. If port
     8000 is already taken (an older copy still running), stop that one
     first.

Watch the terminal output either way - reconciliation gaps and data
problems are logged as warnings, not hidden (see Audit notes below).

## Folder guide

| Folder | What's in it |
|---|---|
| `config/` | Every fixed threshold, status list, and the DSR<->RBS field name translation. |
| `data_sources/` | Where the data physically comes from. The swap point. |
| `scope/` | The single shared filter definition ("Scope"), time windows, and dropdown choices - applied the same way to both reports. |
| `ingest/` | Cleans each raw report into a usable shape. No metrics computed here. |
| `reconcile/` | Compares DSR and RBS on the same scope; RBS's figure wins. |
| `metrics/` | One file per category from the metrics workbook: funnel, premium, quality, composition, headcount, underwriters. |
| `pipeline/` | Ties everything together: `prepare()` (read and clean, once) and `compute()` (every metric for one set of filters). |
| `server/` | The dashboard page, its filter bar, and the background refresh. |
| `tests/` | One test file per module that has real logic worth checking. |

## Status

The metrics workbook is the tracker - **tab 8 (Build tracker)** lists every
rule and metric, its status, where it lives in the code, its test, and its
current value on real data. **Tab 9** lists every judgement call and open
question. Keep both up to date when something changes; this section is only a
summary.

- **Tab 3 (Making DSR + RBS agree):** all seven rules done. Rule 5
  (underwriter spelling) is a known partial fix.
- **Tab 4 (What we CAN build):** every metric built and on the dashboard.
- **Tab 5 (New ideas):** every idea built and on the dashboard.
- **Tab 6 (What we CAN'T build):** deliberately not in the code.
- **Tab 7 (Filters):** every filter from Matt's build except Product (needs
  his product mapping) and Role / Tenure (need the HR file) - those show
  greyed out with the reason.

Run `python -m pytest` from the project root - the tests cover the tab 3
rules, every metric, the filters, and that the page renders for every kind
of view.

## Dashboard filters

The filter bar mirrors Matt's build (workbook tab 7 has the full comparison):
Timeframe (YTD / TTM), Year, Months, Business, Placement, Date basis, Line of
business, Entity and Underwriter. Every figure is shown next to the same
period one year earlier, with the change.

How it's built:

| Piece | Where |
|---|---|
| One filter definition, applied to both reports | `Scope` and `apply_scope` in `scope/filter.py` |
| Time windows, last complete month, prior year, labels | `scope/period.py` |
| Dropdowns that only offer what's still possible | `scope/options.py` |
| Page address <-> filter choices, defaults, clearing a stranded choice | `server/filters.py` |
| What the page opens on | `DEFAULT_...` in `config/settings.py` |
| Every figure on the page, its label and note | `SECTIONS` in `server/dashboard.py` |

Filters live in the page address (e.g. `/?tf=ttm&bt=New&lob=Cyber`), so a
view can be bookmarked or shared. `/metrics` takes the same parameters and
returns JSON.

**Submission date basis** only shows DSR-only figures (Submissions, Quotes,
Quote rate, Roster underwriters). RBS has no submission date, so anything
needing RBS is blank with a note rather than quietly mixing two different
months (tab 3, Rule 3).

**Speed.** The server reads and cleans the data once per refresh
(`prepare()` in `pipeline/build_dashboard_data.py`), keeping only the
cleaned columns plus fast filter copies (`add_filter_columns` in
`scope/filter.py`). A new filter combination then takes about 1-2 seconds
on the full extract, and a repeat is instant.

**To add a metric:** write it in `metrics/` with a test, add it to
`compute()` in `pipeline/build_dashboard_data.py`, add one line to
`SECTIONS` in `server/dashboard.py`, then add a row to workbook tab 8.

## Verified against a real full extract

Ran end to end against a genuine full-scale DSR/RBS pull (144k DSR rows,
31k+ RBS rows) - not the small sample used to build this. Real numbers:

| Metric | Value |
|---|---|
| Submissions / Quotes / Binds | 144,347 / 56,063 / 26,119 |
| Q/S / B/Q / B/S | 38.8% / 46.6% / 18.1% |
| Bound Premium (RBS, kept) | $3.05B |
| UW Margin % | 42.6% |
| GELR book / margin version | 40.55% / 40.63% |
| Commission book / margin version | 16.7% / 16.7% |
| Rate Adequacy | 129.0% |
| RARC (renewals) | 98.0% |
| Active / Roster underwriters (stand-ins) | 167 / 180 |

Two reconciliation gaps were flagged (both logged as warnings, not hidden):
bound premium 11.9% apart, bind count 3.7% apart, DSR vs RBS - worth a
conversation with whoever owns the two extracts about why they disagree by
more than "a percent or two" (tab 3, Rule 6).

On this data, 271 DSR policies had a different New/Renewal value from RBS
and now follow RBS (tab 3, Rule 2), and two entity names differed between
the reports (`Mosaic Syndicate 2610` / `Mosaic 2610`, `Mosaic Syndicate
5431 (EEA)` / `Mosaic 5431`) and are now mapped onto RBS's spelling.

## Audit notes (things fixed after the first working version)

Worth reading before extending this further, since each one was a genuine
bug, not a style choice:

- **GELR book version aligned to the workbook.** An earlier rewrite made it
  identical to the margin version. Tab 4 defines it as an average "across
  all rows", so it now counts a blank GELR as 0 and differs from the margin
  version - see `metrics/quality.py`.
- **Rate Adequacy overstated the result.** It divided all premium by a
  benchmark built from only some rows - the exact issue tab 4 flags in
  Matt's version. Both sides now use the same rows.
- **Funnel rates were withheld below 20 submissions/quotes.** Tab 4 says
  blank only when there are none, so the thresholds were removed.
- **Binds could silently read 0.** `Policy Reference` is now a required RBS
  column.
- **DSR premium reconciliation summed every status, not just bound rows.**
  This inflated the DSR side of the premium cross-check by roughly 100x on
  the sample data. Fixed in `pipeline/build_dashboard_data.py`.
- **Percent-unit detection used to silently pick a majority vote** if the
  three percent columns disagreed on units. It now raises a clear error
  instead of guessing, and also sanity-checks the resulting GELR median -
  see `ingest/clean_rbs.py`.
- **A reconciliation gap against a zero RBS value used to show as a
  misleading "100%".** It now reports as `None` with `is_undefined_gap=True`
  instead of inventing a number - see `reconcile/cross_check.py`.
- **Premium and date parsing used to fail silently.** `pd.to_numeric(...,
  errors="coerce")` turns anything unparseable into a blank with no warning.
  `ingest/validation.py` now checks whether a conversion lost real values
  and logs a warning if so, used by both `clean_dsr.py` and `clean_rbs.py`.
- **`groupby()` on business_type/placement could silently drop a blank
  group.** Now uses `dropna=False` so a blank always shows up as its own
  labelled group instead of vanishing from the percentages.
- Every warning above actually gets logged now (see
  `pipeline/logging_setup.py`) - important since this is meant to run
  unattended in the background, where nobody is watching a terminal.

