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
| `server/` | The dashboard: toolbar (`dashboard.py`), tabs and figures (`panels.py`), charts, help cards, reading aids, downloads, and the background refresh (`app.py`). |
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

- **Tabs 10 and 11 (Metric lineage, Source columns):** every figure traced
  to the exact raw DSR / RBS column names and rows it uses, what the pipeline
  does to each column, and every raw column the code reads.
- **Tab 12 (Ours vs Matt's build):** every figure of ours against his, read
  off his own dashboard's code, with what each difference is worth on real
  data. Two differences matter most: **his headline premium comes from DSR
  where ours comes from RBS**, and **his single GELR figure is our margin
  version while his single commission figure is our book version** - so
  like-named columns across the two dashboards mis-match both.
- **Tab 13 (Checks & safeguards):** every check that runs, whether it stops
  the run, warns, or tells the reader, and its result on today's data.

Two more documents in `docs/` are for showing the dashboard to other people:

- **`UW_Dashboard_Presentation.docx`** - the pack to present from. What the
  dashboard is, where the numbers come from, how to read the page, then every
  metric with its formula, its exact DSR / RBS columns and its current value,
  the comparison with Matt's build, the open questions, and the checks.
- **`Metric_definitions.xlsx`** - one sheet, one row per figure: meaning,
  formula, report, the export columns, what the pipeline does to those columns
  first, which rows count, the current value, and what to watch out for.

Both are generated from `docs/doc_facts.json`, which is built from the code and
the workbook, so the three can't drift apart:

    python docs/export_doc_facts.py          # figures, columns, questions, checks -> JSON
    python docs/build_metric_definitions.py  # the one-sheet definitions file
    node docs/build_presentation_doc.js ".." # the Word pack (needs: npm install docx)

Two scripts regenerate the workbook, and both are safe to re-run:

    python docs/update_workbook.py        # tabs 7, 8, 9, 12, 13 (+ pointers on 1, 2, 4, 5)
    python docs/update_lineage_tabs.py    # tabs 10 and 11, from metrics/lineage.py

Tabs 1-6 are the original hand-written spec and are left alone, except that
a short "Now:" line is added to a tab 4 or 5 note wherever the built figure
settles something the spec left open (e.g. how blanks are handled), with the
effect on real data. So the definitions tab can't quietly drift from the code.

Run `python -m pytest` from the project root - the tests cover the tab 3
rules, every metric, the filters, and that the page renders for every kind
of view. `tests/test_trace_to_source.py` rebuilds every figure straight
from the raw export columns (no dashboard code) and checks it matches the
dashboard exactly - every headline figure, both premium mixes, and every
column of the underwriter table for every underwriter. It runs when the real
`DSR.xlsx` / `RBS.xlsx` are in `data/`. `tests/test_lineage.py` checks the
lineage (below) names exactly the columns the pipeline reads and covers every
figure on the page.

## Lineage: the (i) next to every figure

Every figure on the dashboard, including the underwriter table's columns and
the premium mixes, has a small (i). Hover, tap or tab to it for a card
showing:

- what the figure means, how it's worked out, which rows count, and whether
  it's counted per line, policy or person;
- **each original DSR / RBS column it uses, by its exact export name**, and
  what the pipeline does to that column on the way in (e.g. "stored as a
  fraction, multiplied by 100", "blank counts as $0", "DSR's value replaced
  by RBS's where they disagree");
- the original columns your filters use to narrow the rows first;
- catches worth knowing, where the code lives, and whether the raw-column
  check covers it.

Click the (i) to pin the card open. Everything in it comes from
`metrics/lineage.py` - the same source as workbook tabs 10 and 11 - with
column names taken from `config/field_map.py` and `ingest/` wherever the code
already names them. The card itself is built in `server/help.py`.

## The page

| Tab | What's on it |
|---|---|
| Overview | Headline figures with their last 12 months, the biggest moves against a year earlier, what drove Premium / Active Underwriter |
| Funnel | Submissions, quotes, binds and the rates between them |
| Book quality | Bound premium, deal size, GELR, commission, margin, attachment points, limit, pricing |
| What we write | Lead, primary and agency share, SCM share, brokers, policy length, renewal growth, premium mixes against a year earlier |
| Productivity | The stand-in underwriter counts and per-person figures |
| Underwriters | Sortable, searchable table with peer comparison, few-deals greying and possible duplicate names |
| Trends | 24 months of premium, binds, submissions, Q/S, B/Q and UW Margin %, your period in orange |

The open tab is in the address (`#trends`), so a link or a reload keeps it.
Next to the tabs: **Copy link**, **Download figures (CSV)** - every figure,
this period and a year earlier, with the report and original columns it
comes from - and **Print** (prints every tab). The Underwriters tab has its
own **Download table (CSV)**. Downloads are served at `/export/figures.csv`
and `/export/underwriters.csv` with the same parameters as the page.

Every change carries ▲ / ▼ as well as colour, and every chart has a
**Show as table** view, so nothing depends on colour or hovering alone.

| Piece | Where |
|---|---|
| What's on each tab, headline figures, movers, mixes, underwriter table | `server/panels.py` |
| Month-by-month figures (same definitions as the page, checked month by month) | `metrics/trends.py` |
| Sparklines and trend charts | `server/charts.py` |
| CSV downloads | `server/exports.py` |
| Possible duplicate names | `possible_duplicates` in `ingest/underwriter_names.py` |

## What the September 2026 audit changed

The calculations were audited line by line against the real extracts, and
Matt's own dashboard code was read against ours. Tab 9 of the workbook holds
the questions this raised (17 open), tab 12 the comparison with his build.
The fixes:

- **B/Q and B/S are overstated, and the page now says so.** They divide RBS
  binds by DSR quotes, but 169 of 5,034 bound policies (9.0% of premium) have
  no DSR row at all, so the funnel isn't nested. The note under each figure
  gives the rate without them, any underwriter whose B/Q passes 100% is
  flagged, and the red-badge card now points out that those policies explain
  most of the DSR/RBS premium gap. `metrics/funnel.py binds_not_in_dsr`.
- **UW Margin % reads high, and by how much.** A blank or zero commission
  counts as "none charged" while a blank or zero GELR is left out as
  unusable, so the two halves of `100 - GELR - Commission` treat a missing
  value in opposite ways. 11.5% of margin premium records no commission;
  over the rows that do, margin reads 43.0% against 44.4%.
  `quality.uw_margin_pct_recorded_commission`.
- **"Less business coming in" was the wrong story.** The driver panel called
  a fall in submissions-per-underwriter a fall in inbound flow, when
  submissions had risen 11.9% and the stand-in head count 23.9%. It now
  names both. `metrics/drivers.py _flow_meaning`.
- **A comparison year the extract doesn't cover** read as a book that
  collapsed to $0 (2021 against 2020). It's now blank, with a notice.
- **The driver split is no longer shown** for a period resting on too few
  deals (Q4 2026 printed "fell 89.1%" off 12 binds).
- **The trend charts** say when the period runs past the last complete month,
  instead of quietly charting none of the selected months.
- **Extreme rate changes** are warned about on load (48 rows beyond ±300%,
  largest 2,965%; dropping the in-scope ones moves RARC by ~1.7 points).

Still open in the workbook rather than changed here, because each is a
business decision: whether to restrict B/Q to binds DSR knows about
(question 26), whether a missing commission should be left out of the margin
(25), that entity is per line in RBS but per policy in DSR so entity slices
don't add up to the total (27), and the extreme rate changes (28).

## Reading aids

Built in `server/insights.py` (and `metrics/drivers.py`), so the page helps
people read the figures rather than just show them:

- **What drove Premium / Active Underwriter** - the year-on-year change split
  into submissions per underwriter, quote rate, win rate and average deal
  size, which multiply back to it exactly; each driver's share of the move
  adds up to the total. One sentence names the biggest drag and lift.
- **Red "vs DSR" badges explain themselves** - click for RBS's and DSR's
  figures side by side, the gap, and what it means.
- **How to read this page** - columns, colours, pts vs %, the marks.
- **Few-deals flags** - a figure resting on fewer than `SMALL_SAMPLE_MIN`
  policies (or, per person, `SMALL_TEAM_MIN` underwriters) is greyed out with
  a "few binds" style tag; nothing is hidden. Both live in
  `config/settings.py`.
- **Incomplete months** - a notice when the period includes months with no
  complete data yet (e.g. Full year in September), which would make this
  year look low against last.
- **Low margin cover** - a note on UW Margin % when under `LOW_MARGIN_COVER`
  of premium has a usable GELR.

**When you change how a column or metric is handled:** change the code, then
`metrics/lineage.py`, then run `python docs/update_lineage_tabs.py`. The
tests fail if the lineage and the pipeline disagree about which columns are
read, or if a figure on the page has no lineage.

## Dashboard filters

The filters sit in one toolbar across the top of the page: Period, Business,
Placement, Line of business, Entity and Underwriter. Each button shows its
current choice (outlined in orange when it's not the default) and opens a
small menu:

- **Period** - quick picks (This year so far, Last 12 months, Full year), a
  quarter, or any months; the year; and whether a policy counts in the month
  of its inception or submission date.
- **Business / Placement** - each choice explained in a line.
- **Line of business / Entity / Underwriter** - only the choices that exist
  with the other filters, with a search box on long lists.

Nothing changes until **Apply** (Cancel, Esc or clicking away discards), so
several filters cost one reload. Every filter that's on shows under the
toolbar as a chip whose × removes just that filter; **Clear all** goes back
to the defaults. Every figure is shown next to the same period one year
earlier, with the change. Workbook tab 7 compares each filter with Matt's.

How it's built:

| Piece | Where |
|---|---|
| One filter definition, applied to both reports | `Scope` and `apply_scope` in `scope/filter.py` |
| Time windows, last complete month, prior year, labels | `scope/period.py` |
| Lists that only offer what's still possible | `scope/options.py` |
| Page address <-> filter choices, period choices, defaults, clearing a stranded choice | `server/filters.py` |
| What the page opens on | `DEFAULT_...` in `config/settings.py` |
| The toolbar, its menus, chips and behaviour | `_toolbar`, `_active_filters`, `TOOLBAR_SCRIPT` in `server/dashboard.py` |
| Every figure on the page, its label and note | `SECTIONS` in `server/dashboard.py` |

Filters live in the page address (e.g. `/?period=q2&bt=New&lob=Cyber`), so a
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
`SECTIONS` in `server/dashboard.py`, add its lineage to `metrics/lineage.py`
(and to `tests/test_trace_to_source.py`), run
`python docs/update_lineage_tabs.py`, then add a row to workbook tab 8.

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

