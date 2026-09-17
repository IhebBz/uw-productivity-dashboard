# UW Productivity Dashboard (RBS-only quality metrics + DSR funnel)

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
     `uvicorn server.app:app --reload`, then open `http://localhost:8000`.
     A background thread reruns the pipeline every 5 minutes (see
     `REFRESH_SECONDS` in `server/app.py` - a stand-in for "daily"); the
     page and the `/metrics` endpoint always show the latest run without
     you doing anything.

Watch the terminal output either way - reconciliation gaps and data
problems are logged as warnings, not hidden (see Audit notes below).

## Folder guide

| Folder | What's in it |
|---|---|
| `config/` | Every fixed threshold, status list, and the DSR<->RBS field name translation. |
| `data_sources/` | Where the data physically comes from. The swap point. |
| `scope/` | The single shared filter definition ("Scope"), applied the same way to both reports. |
| `ingest/` | Cleans each raw report into a usable shape. No metrics computed here. |
| `reconcile/` | Compares DSR and RBS on the same scope; RBS's figure wins. |
| `metrics/` | One file per category from the metrics workbook: funnel, quality, composition, headcount. |
| `pipeline/` | Ties everything together into one runnable build. |
| `tests/` | One test file per module that has real logic worth checking. |

## Status

Core logic is implemented and tested against real sample data: ingest,
scope filtering, reconciliation, and most of `metrics/` (funnel, quality,
headcount, and the first two of `composition/`). `metrics/composition.py`
has three functions still stubbed (`broker_concentration`,
`average_policy_tenor`, `renewal_premium_growth`) - each needs one more raw
column added to `clean_rbs.py` first.

Run `python -m pytest` from the project root to check the reconciliation and
funnel logic still behaves as expected after any change.

## Verified against a real full extract

Ran end to end against a genuine full-scale DSR/RBS pull (144k DSR rows,
31k+ RBS rows) - not the small sample used to build this. Real numbers:

| Metric | Value |
|---|---|
| Submissions / Quotes / Binds | 144,347 / 56,063 / 26,119 |
| Bound Premium (RBS, kept) | $3.05B |
| UW Margin % | 42.6% |
| GELR / Commission | 40.6% / 16.7% |
| Rate Adequacy | 129.2% |
| RARC (renewals) | 98.0% |
| Active Underwriters / Roster Underwriters | 167 / 180 |

Two reconciliation gaps were flagged (both logged as warnings, not hidden):
bound premium 11.9% apart, bind count 3.7% apart, DSR vs RBS. Both are far
more reasonable than the earlier sample data's gaps (which ran into the
thousands of percent) - worth a conversation with whoever owns the two
extracts about why they disagree by double digits rather than a percent or
two, but this is a business question now, not a pipeline bug.

Found and fixed one real gap during this check: **RARC had been dropped
entirely** during the earlier audit rewrite of `metrics/quality.py` and was
never wired back into the pipeline output, despite being an approved
metric. Fixed and verified - it now returns a real value (98.0% on this
data) and is included in `pipeline/build_dashboard_data.py`'s output.

Also generalised the percent-unit-scaling fix: `clean_rbs.py` used to scale
a hand-picked list of 3 percent columns. It now detects and scales every
column whose name ends in "(%)" automatically (22 columns on the real
data) - so a percent column added to a future extract is covered without
anyone needing to remember to update a list here.

## Audit notes (things fixed after the first working version)

Worth reading before extending this further, since each one was a genuine
bug, not a style choice:

- **GELR "book basis" was wrong.** It treated a blank/zero GELR as 0 instead
  of excluding that row, which isn't what the source definition says.
  Fixed - see the docstring in `metrics/quality.py` for why "book basis" and
  "margin basis" GELR are now (correctly) identical.
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

