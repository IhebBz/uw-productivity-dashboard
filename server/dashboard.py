"""Renders the computed metrics as the dashboard page, in the Mosaic
palette and number formatting from Mosaic_Dashboard_Standards.docx (section
6). Server-rendered on every request for the filters in the page address -
no client-side templating needed for something this size.

The page has three parts: the filter bar (see server/filters.py and the
metrics workbook, tab 7), every figure against the same period last year
(SECTIONS below), and the underwriter table.
"""
from html import escape

from scope.filter import SUBMISSION
from scope.period import MONTH_NAMES, last_complete_month
from server.formatting import (FORMATTERS, fmt_change, fmt_money, fmt_pct, fmt_int,
                               fmt_ratio_pct, fmt_multiple)

CSS = """
:root {
  --charcoal: #313E48;
  --grey: #5C6670;
  --orange: #FF5A00;
  --turquoise: #4DBCC6;
  --purple: #BB29BB;
  --good: #378F4A;
  --bad: #D02B2B;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #FFFFFF;
  color: var(--charcoal);
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.5;
}
header {
  background: var(--charcoal);
  color: #FFFFFF;
  padding: 20px 40px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
header .brand {
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  font-size: 20px;
  letter-spacing: 0.02em;
}
header .meta {
  color: #C7CDD2;
  font-size: 13px;
}
main {
  max-width: 1120px;
  margin: 0 auto;
  padding: 48px 40px 80px;
}
.hero {
  display: flex;
  gap: 64px;
  border-bottom: 3px solid var(--orange);
  padding-bottom: 28px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.hero .stat .value {
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  font-size: 42px;
  line-height: 1.1;
}
.hero .stat .label {
  color: var(--grey);
  font-size: 14px;
  margin-top: 4px;
}
section {
  margin-top: 44px;
}
section h2 {
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  font-weight: normal;
  font-size: 20px;
  margin: 0 0 4px;
}
section .subtitle {
  color: var(--grey);
  font-size: 13px;
  margin-bottom: 16px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 0;
  border-bottom: 1px solid #E4E7E9;
  gap: 24px;
}
.row .label { color: var(--charcoal); }
.row .value {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
}
.row .note {
  color: var(--grey);
  font-size: 12.5px;
  margin-top: 2px;
}
.flag {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 3px;
  margin-left: 8px;
  color: #FFFFFF;
  vertical-align: middle;
}
.flag.bad { background: var(--bad); }
.flag.ok { background: var(--good); }
.mix-bar {
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  margin-top: 8px;
  background: #E4E7E9;
}
.mix-bar span { display: block; height: 100%; }
.mix-legend {
  display: flex;
  gap: 18px;
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--grey);
  flex-wrap: wrap;
}
.mix-legend .dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
}
.empty {
  padding: 80px 0;
  text-align: center;
  color: var(--grey);
}
.empty .value {
  font-family: Georgia, serif;
  font-size: 22px;
  color: var(--charcoal);
  margin-bottom: 8px;
}
.filters {
  background: #F4F5F6;
  border-bottom: 1px solid #E4E7E9;
  padding: 16px 40px;
}
.filters form {
  max-width: 1120px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 14px 22px;
  align-items: flex-end;
}
.fg label.title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--grey);
  margin-bottom: 5px;
}
.fg .count { font-weight: normal; margin-left: 5px; color: #A9B0B6; }
.pills { display: flex; }
.pills label {
  border: 1px solid #C9CFD4;
  background: #FFFFFF;
  padding: 4px 10px;
  font-size: 13px;
  cursor: pointer;
  margin-left: -1px;
  white-space: nowrap;
}
.pills label:first-child { border-radius: 4px 0 0 4px; margin-left: 0; }
.pills label:last-child { border-radius: 0 4px 4px 0; }
.pills label.on { background: var(--charcoal); border-color: var(--charcoal); color: #FFFFFF; }
.pills label.off { cursor: default; opacity: 0.55; }
.pills input { display: none; }
.months label { padding: 4px 0; width: 28px; text-align: center; position: relative; }
.months label.dev::after {
  content: "";
  position: absolute;
  top: 3px;
  right: 3px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--orange);
}
.fg select {
  font: inherit;
  font-size: 13px;
  padding: 4px 6px;
  border: 1px solid #C9CFD4;
  border-radius: 4px;
  background: #FFFFFF;
  max-width: 210px;
}
.fg select:disabled { color: #A9B0B6; background: #F4F5F6; }
.reset { font-size: 13px; color: var(--orange); text-decoration: none; padding: 5px 0; }
.scope-line { color: var(--grey); font-size: 13px; margin-bottom: 28px; }
.notice {
  border-left: 3px solid var(--orange);
  background: #FFF4EE;
  padding: 10px 14px;
  font-size: 13.5px;
  margin-bottom: 24px;
}
.hero .stat .change { font-size: 13px; margin-top: 2px; }
table.figures, table.uw { width: 100%; border-collapse: collapse; font-size: 14.5px; }
table.figures th, table.uw th {
  text-align: right;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--grey);
  padding: 6px 0 6px 18px;
  border-bottom: 1px solid #C9CFD4;
  white-space: nowrap;
}
table.figures td, table.uw td {
  padding: 9px 0 9px 18px;
  border-bottom: 1px solid #E4E7E9;
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  vertical-align: baseline;
}
table.figures th:first-child, table.uw th:first-child,
table.figures td:first-child, table.uw td:first-child {
  text-align: left;
  padding-left: 0;
  white-space: normal;
}
table.figures td.now { font-weight: 600; }
table.figures td.was { color: var(--grey); }
table.figures .note { display: block; color: var(--grey); font-size: 12.5px; }
.good { color: var(--good); }
.bad { color: var(--bad); }
.neutral { color: var(--grey); }
.uw-wrap { max-height: 560px; overflow: auto; border-bottom: 1px solid #E4E7E9; }
table.uw thead th { position: sticky; top: 0; background: #FFFFFF; }
table.uw a { color: var(--charcoal); text-decoration: none; border-bottom: 1px dotted #A9B0B6; }
table.uw tr.picked td { background: #FFF4EE; }
@media (max-width: 700px) {
  header, .filters { padding-left: 16px; padding-right: 16px; }
  main { padding: 28px 16px 60px; }
  .hero { gap: 28px; }
  table.figures td.was, table.figures th:nth-child(3) { display: none; }
}
footer {
  color: var(--grey);
  font-size: 12px;
  text-align: center;
  padding: 24px 0 48px;
}
"""

MIX_COLORS = ["#FF5A00", "#4DBCC6", "#485CC7", "#BB29BB", "#5C6670"]

# Every figure on the page, in order: (result key, label, format, which way is
# good, note). "Which way is good" colours the change against last year:
# "higher", "lower", or "neutral" (a description of the book, not a score).
# To add a metric to the page, compute it in pipeline/build_dashboard_data.py
# and add one line here - then list it in the metrics workbook, tab 8.
SECTIONS = [
    ("The funnel", "From DSR – every risk that came in, won or not. Binds come from RBS.", [
        ("funnel.submissions", "Submissions", "int", "higher", None),
        ("funnel.quotes", "Quotes", "int", "higher", None),
        ("funnel.binds", "Binds", "int", "higher", "RBS, cross-checked against DSR"),
        ("funnel.quote_rate", "Quote rate (Q/S)", "ratio", "higher", None),
        ("funnel.bind_rate", "Win rate (B/Q)", "ratio", "higher", "Binds (RBS) ÷ Quotes (DSR)"),
        ("funnel.end_to_end_win_rate", "End-to-end win rate (B/S)", "ratio", "higher", None),
    ]),
    ("How much we wrote", "From RBS, the source of truth for bound business", [
        ("premium.bound_premium", "Bound Premium", "money", "higher", "RBS, cross-checked against DSR"),
        ("premium.average_deal_size", "Average Deal Size", "amount", "higher", "Bound Premium ÷ Binds"),
    ]),
    ("How good the business is",
     "From RBS. Book version = every row; margin version = only rows with a usable GELR", [
        ("quality.uw_margin_pct", "UW Margin %", "pct", "higher",
         "Margin versions of GELR and Commission. Mosaic's internal commission is not "
         "subtracted (open question)"),
        ("quality.gelr_book_basis", "GELR – book version", "pct", "lower", "Blank GELR counts as 0"),
        ("quality.gelr_margin_basis", "GELR – margin version", "pct", "lower", None),
        ("quality.commission_book_basis", "Commission – book version", "pct", "lower", None),
        ("quality.commission_margin_basis", "Commission – margin version", "pct", "lower", None),
        ("quality.margin_cover", "Margin cover", "ratio", "higher", "Share of premium with a usable GELR"),
        ("quality.commission_cover", "Commission cover", "ratio", "neutral",
         "Share of margin premium with commission above 0"),
        ("quality.attachment_point_excess", "Median attachment point – Excess", "amount", "neutral", None),
        ("quality.attachment_point_primary", "Median attachment point – Primary", "amount", "neutral",
         "Blank deductible counts as 0, so often understated"),
        ("quality.median_limit", "Median limit", "amount", "neutral",
         "Agency Exposure (USD). Matt's build calls this “Average”"),
    ]),
    ("Pricing", "From RBS", [
        ("pricing.rate_adequacy", "Rate Adequacy", "pct", "higher",
         "Premium ÷ plan benchmark, same rows on both sides"),
        ("pricing.rate_adequacy_rbs_benchmark", "Rate Adequacy – RBS benchmark check", "pct", "higher",
         "Mosaic 1609 premium ÷ RBS's own 1609 benchmark premium"),
        ("pricing.rarc", "RARC", "pct", "higher", "Renewals only, whatever the Business filter"),
    ]),
    ("What kind of book we write", "From RBS", [
        ("composition.mosaic_as_lead", "Mosaic as lead", "ratio", "neutral", "Share of rows, not premium"),
        ("composition.primary_share", "Primary share", "ratio", "neutral", "Share of rows, not premium"),
        ("composition.average_agency_share", "Average agency share", "pct", "neutral",
         "Premium-weighted line size"),
        ("composition.scm_share", "SCM share", "ratio", "neutral",
         "Premium on third-party capital, not Mosaic 1609"),
        ("composition.broker_concentration", "Broker concentration", "ratio", "neutral",
         "Top 5 brokers' share of premium"),
        ("composition.average_policy_length", "Average policy length", "months", "neutral",
         "Counted once per policy"),
        ("composition.renewal_premium_growth", "Renewal premium growth", "ratio", "higher",
         "Renewal premium ÷ expiring premium. Not a true retention rate"),
    ]),
    ("Productivity (stand-in headcount)", None, [
        ("productivity_stand_in.active_underwriters_stand_in", "Active underwriters (stand-in)", "int",
         "neutral", "Won at least one deal"),
        ("productivity_stand_in.roster_underwriters_stand_in", "Roster underwriters (stand-in)", "int",
         "neutral", "At least one submission"),
        ("productivity_stand_in.premium_per_active_underwriter", "Premium / Active Underwriter", "money",
         "higher", "Recommended default"),
        ("productivity_stand_in.premium_per_roster_underwriter", "Premium / Roster Underwriter", "money",
         "higher", "Wider view"),
        ("productivity_stand_in.uw_margin_per_active_underwriter", "UW Margin / Active Underwriter",
         "money", "higher", None),
    ]),
]

HERO = [
    ("premium.bound_premium", "Bound Premium", "money", "higher", "premium.reconciliation"),
    ("quality.uw_margin_pct", "UW Margin %", "pct", "higher", None),
    ("funnel.binds", "Binds", "int", "higher", "funnel.binds_reconciliation"),
    ("productivity_stand_in.premium_per_active_underwriter", "Premium / Active UW (stand-in)", "money",
     "higher", None),
]


def _get(result: dict, path: str):
    """Read "section.key" from a result dict; None if either level is missing."""
    if result is None:
        return None
    section, key = path.split(".")
    return (result.get(section) or {}).get(key)


def _field(obj, name):
    """Read a field from a dataclass or a dict (results can be either)."""
    if obj is None:
        return None
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _reconciliation_flag(recon) -> str:
    """A small badge next to a figure that's been cross-checked - only
    shown when it's actually flagged, since a badge on every row would
    just be noise (per the design principle of not decorating everything).
    """
    if not recon:
        return ""
    if _field(recon, "is_undefined_gap"):
        return '<span class="flag bad">check vs DSR</span>'
    if _field(recon, "flagged"):
        gap = _field(recon, "gap_pct") or 0
        return f'<span class="flag bad">{gap * 100:.0f}% vs DSR</span>'
    return ""


def _change_html(current, prior, kind, good) -> str:
    """The move against last year, coloured by whether it's good news."""
    text, move = fmt_change(current, prior, kind)
    if move in (None, "flat") or good == "neutral":
        css = "neutral"
    else:
        css = "good" if (move == "up") == (good == "higher") else "bad"
    return f'<span class="{css}">{text}</span>'


def _mix_bar(mix: dict) -> str:
    """A thin horizontal proportion bar for a premium mix dict."""
    if not mix:
        return ""
    items = []
    for label, val in mix.items():
        share = val.get("premium_share") if isinstance(val, dict) else val
        if share:
            items.append((label, share))
    if not items:
        return ""
    bar = "".join(
        f'<span style="width:{share * 100:.2f}%;background:{MIX_COLORS[i % len(MIX_COLORS)]}"></span>'
        for i, (label, share) in enumerate(items)
    )
    legend = "".join(
        f'<span><span class="dot" style="background:{MIX_COLORS[i % len(MIX_COLORS)]}"></span>'
        f'{escape(str(label))} {fmt_pct(share * 100)}</span>'
        for i, (label, share) in enumerate(items)
    )
    return f'<div class="mix-bar">{bar}</div><div class="mix-legend">{legend}</div>'


def _pills(name, title, choices, selected) -> str:
    """A row of single-choice buttons. choices = [(value, label), ...]."""
    buttons = ""
    for value, label in choices:
        on = str(value) == str(selected)
        buttons += (f'<label class="{"on" if on else ""}"><input type="radio" name="{name}" '
                    f'value="{escape(str(value))}"{" checked" if on else ""}>{escape(label)}</label>')
    return f'<div class="fg"><label class="title">{title}</label><div class="pills">{buttons}</div></div>'


def _select(name, title, values, selected, all_label, labels=None) -> str:
    """A dropdown with an "All" choice. Shows how many choices are left."""
    labels = labels or {}
    opts = f'<option value="">{all_label}</option>' + "".join(
        f'<option value="{escape(str(v))}"{" selected" if v == selected else ""}>'
        f'{escape(str(labels.get(v, v)))}</option>'
        for v in values)
    return (f'<div class="fg"><label class="title">{title}<span class="count">{len(values)}</span></label>'
            f'<select name="{name}">{opts}</select></div>')


def _unavailable(title, reason) -> str:
    """A filter Matt's build has that we can't offer yet, greyed out with the reason."""
    return (f'<div class="fg"><label class="title">{title}</label>'
            f'<select disabled title="{escape(reason)}"><option>{escape(reason)}</option></select></div>')


def _filter_bar(view) -> str:
    """The filter bar: a plain form, re-submitted whenever a choice changes."""
    f, options, choices = view["filters"], view["options"], view["choices"]
    as_at = view["as_at"]
    ttm = f.tf == "ttm"

    months = ""
    for m in range(1, 13):
        picked = ttm or m in f.months
        dev = f.year == as_at.year and m == as_at.month and not as_at.is_month_end
        title = ("Fixed by the trailing-twelve window" if ttm
                 else "Part month – still in progress" if dev else MONTH_NAMES[m - 1])
        css = " ".join(c for c in ("on" if picked else "", "off" if ttm else "",
                                   "dev" if dev else "") if c)
        box = "" if ttm else f'<input type="checkbox" name="m" value="{m}"{" checked" if picked else ""}>'
        months += f'<label class="{css}" title="{title}">{box}{MONTH_NAMES[m - 1][0]}</label>'

    years = "".join(f'<option value="{y}"{" selected" if y == f.year else ""}>{y}</option>'
                    for y in reversed(choices["years"]))

    return f"""
    <div class="filters">
      <form method="get" action="/" id="filter-form">
        {_pills("tf", "Timeframe", [("ytd", "YTD"), ("ttm", "TTM")], f.tf)}
        <div class="fg"><label class="title">Year</label><select name="year">{years}</select></div>
        <div class="fg"><label class="title">Months{" (fixed)" if ttm else ""}</label>
          <div class="pills months">{months}</div></div>
        {_pills("bt", "Business", [("", "All")] + [(v, v) for v in choices["business_types"]], f.bt)}
        {_pills("mop", "Placement", [("", "All")] + [(v, v) for v in choices["placements"]], f.mop)}
        {_pills("basis", "Date basis", [("inception", "Inception"), ("submission", "Submission")], f.basis)}
        {_select("lob", "Line of business", options["line_of_business"], f.lob, "All LOBs")}
        {_select("ent", "Entity", options["entity"], f.ent, "All entities")}
        {_select("uw", "Underwriter", options["underwriter"], f.uw, "All underwriters",
                 view["underwriter_names"])}
        {_unavailable("Product", "Not available – needs Matt's product mapping")}
        {_unavailable("Role", "Needs the HR file")}
        {_unavailable("Tenure", "Needs the HR file")}
        <a class="reset" href="/">Reset</a>
        <noscript><button type="submit">Apply</button></noscript>
      </form>
    </div>
    <script>
      document.querySelectorAll('#filter-form input, #filter-form select').forEach(function (el) {{
        el.addEventListener('change', function () {{ el.form.submit(); }});
      }});
    </script>"""


def _scope_line(view) -> str:
    """One line saying exactly which slice every figure on the page is for."""
    f = view["filters"]
    current, prior = view["result"]["current"], view["result"]["prior"]
    parts = [f.lob or "All LOBs", f.ent or "All entities", f.bt or "All business",
             f.mop or "All placement"]
    if f.uw:
        parts.append(view["underwriter_names"].get(f.uw, f.uw))
    parts.append(current["period_label"] + (f" vs {prior['period_label']}" if prior else ""))
    parts.append(("Submission" if f.basis == SUBMISSION else "Inception") + " date basis")
    return " · ".join(escape(str(p)) for p in parts)


def _hero(current, prior) -> str:
    """The four headline figures across the top."""
    stats = ""
    for path, label, kind, good, recon_path in HERO:
        now, was = _get(current, path), _get(prior, path)
        flag = _reconciliation_flag(_get(current, recon_path)) if recon_path else ""
        stats += f"""
          <div class="stat">
            <div class="value">{FORMATTERS[kind](now)}</div>
            <div class="label">{label}{flag}</div>
            <div class="change">{_change_html(now, was, kind, good)}
              <span class="neutral">vs {FORMATTERS[kind](was)}</span></div>
          </div>"""
    return f'<div class="hero">{stats}</div>'


def _section(title, subtitle, rows, current, prior) -> str:
    """One block of figures: this period, the same period last year, and the change."""
    now_label = escape(current["period_label"])
    was_label = escape(prior["period_label"]) if prior else "Prior year"
    body = ""
    for path, label, kind, good, note in rows:
        now, was = _get(current, path), _get(prior, path)
        note_html = f'<span class="note">{escape(note)}</span>' if note else ""
        body += (f'<tr><td>{escape(label)}{note_html}</td>'
                 f'<td class="now">{FORMATTERS[kind](now)}</td>'
                 f'<td class="was">{FORMATTERS[kind](was)}</td>'
                 f'<td>{_change_html(now, was, kind, good)}</td></tr>')
    sub = f'<div class="subtitle">{escape(subtitle)}</div>' if subtitle else ""
    return f"""
        <section>
          <h2>{escape(title)}</h2>{sub}
          <table class="figures">
            <thead><tr><th>Figure</th><th>{now_label}</th><th>{was_label}</th><th>Change</th></tr></thead>
            <tbody>{body}</tbody>
          </table>
        </section>"""


def _underwriter_section(view) -> str:
    """Every underwriter in the other filters, with their funnel, book and peer comparison."""
    table = view["result"]["current"]["underwriters"]
    f = view["filters"]
    rows = ""
    for r in table["rows"]:
        picked = ' class="picked"' if r["underwriter"] == f.uw else ""
        link = escape(f.query(uw=r["underwriter"]))
        rows += (f'<tr{picked}><td><a href="{link}">{escape(str(r["name"]))}</a></td>'
                 f'<td>{fmt_int(r["submissions"])}</td><td>{fmt_ratio_pct(r["quote_rate"])}</td>'
                 f'<td>{fmt_int(r["binds"])}</td><td>{fmt_ratio_pct(r["bind_rate"])}</td>'
                 f'<td>{fmt_money(r["premium"])}</td><td>{fmt_multiple(r["premium_vs_peer_median"])}</td>'
                 f'<td>{fmt_pct(r["uw_margin_pct"])}</td></tr>')
    return f"""
        <section>
          <h2>Underwriters</h2>
          <div class="subtitle">{len(table["rows"])} underwriters in the other filters.
            Peer median premium {fmt_money(table["peer_median_premium"])}. Click a name to
            filter the whole page to them. Names are matched after tidying capitals,
            punctuation and spaces only, so one person typed two ways shows twice
            (workbook tab 3, Rule 5).</div>
          <div class="uw-wrap">
          <table class="uw">
            <thead><tr><th>Underwriter</th><th>Submissions</th><th>Q/S</th><th>Binds</th><th>B/Q</th>
              <th>Premium</th><th>vs peer median</th><th>UW Margin %</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
          </div>
        </section>"""


def _body(view) -> str:
    """Everything below the filter bar."""
    current, prior = view["result"]["current"], view["result"]["prior"]
    notices = ""
    if view["filters"].cleared:
        cleared = ", ".join(escape(str(view["underwriter_names"].get(v, v)))
                            for v in view["filters"].cleared)
        notices += (f'<div class="notice">Cleared {cleared}: not available with the other '
                    f'filters picked.</div>')
    if current["basis_note"]:
        notices += f'<div class="notice">{escape(current["basis_note"])}</div>'

    sections = ""
    for title, subtitle, rows in SECTIONS:
        if title.startswith("Productivity"):
            subtitle = current["productivity_stand_in"]["note"]
        sections += _section(title, subtitle, rows, current, prior)
        if title == "What kind of book we write" and current["composition"]["placement_mix"]:
            label = escape(current["period_label"])
            sections += f"""
        <section style="margin-top:20px">
          <div class="subtitle">New vs. Renewal mix, {label}, share of premium</div>
          {_mix_bar(current["composition"]["new_vs_renewal_mix"])}
          <div class="subtitle" style="margin-top:18px">Placement mix, {label}, share of premium</div>
          {_mix_bar(current["composition"]["placement_mix"])}
        </section>"""

    return f"""
        <div class="scope-line">{_scope_line(view)}</div>
        {notices}
        {_hero(current, prior)}
        {sections}
        {_underwriter_section(view)}"""


def render_dashboard(view: dict, last_run: str, error: str) -> str:
    """Build the full HTML page for one set of filters (see server/app.py)."""
    filters = ""
    if error:
        body = f"""
        <div class="empty">
          <div class="value">Last run failed</div>
          <div>{escape(error)}</div>
        </div>"""
    elif not view:
        body = """
        <div class="empty">
          <div class="value">Computing your first result&hellip;</div>
          <div>Reading a full DSR/RBS extract can take a few minutes the first
          time. After that, an unchanged file is cached and reloads almost
          instantly - this page checks again automatically, no need to
          refresh by hand.</div>
        </div>"""
    else:
        filters = _filter_bar(view)
        body = _body(view)

    as_at = f' &middot; data as at {view["as_at"]:%d %b %Y}' if view else ""
    # Refreshes quickly while waiting for the first result, then every few
    # minutes - the filters are in the address, so a refresh keeps them.
    refresh = 30 if not view else 300
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{refresh}">
  <title>UW Productivity Dashboard</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <div class="brand">Mosaic &middot; UW Productivity</div>
    <div class="meta">{"Last run " + last_run if last_run else "Not yet run"}{as_at}</div>
  </header>
  {filters}
  <main>
    {body}
  </main>
  <footer>Confidential &middot; internal use only</footer>
</body>
</html>"""
