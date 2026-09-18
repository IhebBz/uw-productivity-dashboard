"""Everything on the dashboard below the filter toolbar: which figures are
shown and how (SECTIONS, HERO), the tabs they sit on, the headline figures
with sparklines, the biggest moves, premium mixes, trend charts and the
underwriter table, plus the copy-link / download / print actions.

server/dashboard.py builds the page around this: the header, the toolbar,
the help cards and the scripts.
"""
from html import escape

from config.settings import SMALL_SAMPLE_MIN
from scope.filter import INCEPTION, SUBMISSION
from server.charts import ACCENT, MUTED, line_chart, sparkline
from server.filters import default_state
from server.formatting import (FORMATTERS, change_value, fmt_change, fmt_int, fmt_money, fmt_multiple,
                               fmt_pct, fmt_ratio_pct)
from server.help import help_button
from server.insights import (RECONCILED, drivers_section, extra_note, few_tag, guide_button,
                             incomplete_period_notice, reconciliation_badge, thin_data)

MIX_COLORS = ["#FF5A00", "#4DBCC6", "#485CC7", "#BB29BB", "#5C6670"]

# Every figure on the page, in order: (result key, label, format, which way is
# good, note). "Which way is good" colours the change against last year:
# "higher", "lower", or "neutral" (a description of the book, not a score).
# To add a metric to the page, compute it in pipeline/build_dashboard_data.py
# and add one line here - then add its lineage to metrics/lineage.py (the (i) help
# reads it) and list it in the metrics workbook, tab 8.
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

# The underwriter table's columns: (key in metrics/lineage.py after "underwriters.", header).
UNDERWRITER_COLUMNS = [
    ("submissions", "Submissions"), ("quote_rate", "Q/S"), ("binds", "Binds"), ("bind_rate", "B/Q"),
    ("premium", "Premium"), ("premium_vs_peer_median", "vs peer median"), ("uw_margin_pct", "UW Margin %"),
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


def _change_html(current, prior, kind, good) -> str:
    """The move against last year, coloured by whether it's good news."""
    text, move = fmt_change(current, prior, kind)
    if move in (None, "flat") or good == "neutral":
        css = "neutral"
    else:
        css = "good" if (move == "up") == (good == "higher") else "bad"
    return f'<span class="{css}">{text}</span>'


def _active_filters(view) -> str:
    """What the figures are for: one removable chip per filter that's on, and the comparison."""
    f = view["filters"]
    default = default_state(view["as_at"])
    names = view["underwriter_names"]
    chips = []
    for attr, text in (("bt", f.bt), ("mop", f.mop), ("lob", f.lob), ("ent", f.ent),
                       ("uw", names.get(f.uw, f.uw))):
        if getattr(f, attr) and getattr(f, attr) != getattr(default, attr):
            chips.append((f.query(**{attr: ""}), text))
    if f.basis == SUBMISSION:
        chips.append((f.query(basis=INCEPTION), "By submission date"))

    chip_html = "".join(
        f'<a class="chip" href="{escape(href)}" title="Remove this filter">{escape(str(text))}'
        f'<span class="x" aria-label="remove">×</span></a>'
        for href, text in chips)
    if chip_html:
        chip_html = f'<span class="lead">Filtered to</span>{chip_html}<a class="clear" href="/">Clear all</a>'
    else:
        chip_html = '<span class="lead">Whole book – no filters on</span>'

    prior = view["result"]["prior"]
    compare = f'Compared with {escape(prior["period_label"])}' if prior else ""
    unavailable = ('<span class="unavailable" title="Product needs Matt\'s product mapping. Role and '
                   'Tenure need the HR file. See workbook tab 7.">Not available yet: Product, Role, '
                   'Tenure</span>')
    return f"""
        <div class="active-filters">
          <div class="chips">{chip_html}</div>
          <div class="context">{compare}{unavailable}{guide_button()}</div>
        </div>"""


def _section(title, subtitle, rows, current, prior) -> str:
    """One block of figures: this period, the same period last year, and the change."""
    now_label = escape(current["period_label"])
    was_label = escape(prior["period_label"]) if prior else "Prior year"
    body = ""
    for path, label, kind, good, note in rows:
        now, was = _get(current, path), _get(prior, path)
        note_html = f'<span class="note">{escape(note)}</span>' if note else ""
        note_html += extra_note(current, path)
        thin_now, thin_was = thin_data(current, path), thin_data(prior, path)
        body += (f'<tr><td>{escape(label)}{help_button(path)}{note_html}</td>'
                 f'<td class="now{" thin" if thin_now else ""}">{FORMATTERS[kind](now)}'
                 f'{few_tag(*thin_now) if thin_now else ""}</td>'
                 f'<td class="was{" thin" if thin_was else ""}">{FORMATTERS[kind](was)}</td>'
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


# ---- Tabs ------------------------------------------------------------------------

TABS = [
    ("overview", "Overview"),
    ("funnel", "Funnel"),
    ("quality", "Book quality"),
    ("book", "What we write"),
    ("productivity", "Productivity"),
    ("underwriters", "Underwriters"),
    ("trends", "Trends"),
]
# Which tab each block of figures in SECTIONS lives on.
SECTION_TAB = {
    "The funnel": "funnel",
    "How much we wrote": "quality",
    "How good the business is": "quality",
    "Pricing": "quality",
    "What kind of book we write": "book",
    "Productivity (stand-in headcount)": "productivity",
}
# Tab for a figure path, e.g. "funnel.quote_rate" -> "funnel" (for links from the Overview).
FIGURE_TAB = {path: SECTION_TAB[title] for title, _, rows in SECTIONS for path, *_ in rows}


def _tab_bar() -> str:
    links = "".join(f'<a href="#{key}" class="tab" role="tab" data-tab="{key}">{escape(label)}</a>'
                    for key, label in TABS)
    return f'<nav class="tabs" role="tablist" aria-label="Sections">{links}</nav>'


def _panel(key, content) -> str:
    return f'<div class="tab-panel" id="panel-{key}" data-panel="{key}" role="tabpanel">{content}</div>'


# ---- Page actions ----------------------------------------------------------------

def _page_actions(view) -> str:
    """Copy link, downloads for these filters, and print."""
    query = escape(view["filters"].query())
    return f"""
        <div class="page-actions">
          <button type="button" class="action" data-copy-link>Copy link</button>
          <a class="action" href="/export/figures.csv{query}" download>Download figures (CSV)</a>
          <button type="button" class="action" data-print>Print</button>
        </div>"""


# ---- Headline figures --------------------------------------------------------------

# Headline figure -> its monthly series in metrics/trends.py (for the sparkline).
HERO_TRENDS = {
    "premium.bound_premium": "bound_premium",
    "quality.uw_margin_pct": "uw_margin_pct",
    "funnel.binds": "binds",
}


def _hero(current, prior, trends) -> str:
    """The four headline figures across the top, each with its last 12 months."""
    card_for = {path: card_id for card_id, (path, *_) in RECONCILED.items()}
    months = trends["months"][-12:]
    stats = ""
    for path, label, kind, good, recon_path in HERO:
        now, was = _get(current, path), _get(prior, path)
        flag = reconciliation_badge(_get(current, recon_path), card_for[recon_path]) if recon_path else ""
        thin = thin_data(current, path)
        spark = ""
        series = trends["series"].get(HERO_TRENDS.get(path))
        if series:
            spark = sparkline(series[-12:], [m["selected"] for m in months],
                              f"{label}, last 12 months: {months[0]['label']} to {months[-1]['label']}")
        was_text = f'vs {FORMATTERS[kind](was)} a year earlier' if prior else ""
        stats += f"""
          <div class="stat{" thin" if thin else ""}">
            <div class="value">{FORMATTERS[kind](now)}</div>
            <div class="label">{label}{help_button(path)}{flag}{few_tag(*thin) if thin else ""}</div>
            <div class="change">{_change_html(now, was, kind, good)} <span class="neutral">{was_text}</span></div>
            {spark}
          </div>"""
    return f'<div class="hero">{stats}</div>'


# ---- Biggest movers ----------------------------------------------------------------

MOVERS_PER_LIST = 3


def _biggest_movers(current, prior) -> str:
    """The figures that moved most against a year earlier: rates in pts, amounts in %.

    Skips figures resting on too few deals in either year - a big swing off two
    binds isn't news.
    """
    if not prior:
        return ""
    rates, amounts = [], []
    for title, _, rows in SECTIONS:
        for path, label, kind, good, _ in rows:
            now, was = _get(current, path), _get(prior, path)
            move, _unit = change_value(now, was, kind)
            if not move or thin_data(current, path) or thin_data(prior, path):
                continue
            (rates if kind in ("pct", "ratio") else amounts).append((abs(move), path, label, kind, good, now, was))

    def listing(items, heading):
        if not items:
            return ""
        rows = "".join(
            f'<li><a href="#{FIGURE_TAB[path]}" data-tab-link="{FIGURE_TAB[path]}">{escape(label)}</a>'
            f'<span class="move">{_change_html(now, was, kind, good)}</span>'
            f'<span class="neutral">{FORMATTERS[kind](was)} → {FORMATTERS[kind](now)}</span></li>'
            for _, path, label, kind, good, now, was in sorted(items, reverse=True)[:MOVERS_PER_LIST])
        return f'<div><div class="movers-head">{heading}</div><ol class="movers">{rows}</ol></div>'

    lists = listing(rates, "Rates – in percentage points") + listing(amounts, "Amounts and counts – in %")
    if not lists:
        return ""
    return f"""
        <section class="movers-section">
          <h2>Biggest moves against a year earlier</h2>
          <div class="subtitle">Figures resting on too few deals are left out. Click one to see it in context.</div>
          <div class="movers-grid">{lists}</div>
        </section>"""


# ---- Mixes ------------------------------------------------------------------------

def _shares(mix):
    out = {}
    for label, val in (mix or {}).items():
        share = val.get("premium_share") if isinstance(val, dict) else val
        if share:
            out[label] = share
    return out


def _mix_compare(title, help_key, current, prior, key) -> str:
    """This period's premium mix above a year earlier's, same colour per value in both bars."""
    now = _shares(current["composition"].get(key))
    was = _shares(prior["composition"].get(key)) if prior else {}
    if not now:
        return ""
    # Colour follows the value (e.g. Open Market is always orange), never its size.
    colour = {label: MIX_COLORS[i % len(MIX_COLORS)] for i, label in enumerate(sorted(set(now) | set(was)))}

    def bar(shares, period):
        if not shares:
            return f'<div class="mix-row"><span class="mix-period">{escape(period)}</span><span class="neutral">no premium</span></div>'
        segments = "".join(
            f'<span style="width:{share * 100:.2f}%;background:{colour[label]}" '
            f'title="{escape(str(label))}: {fmt_pct(share * 100)}"></span>'
            for label, share in shares.items())
        return (f'<div class="mix-row"><span class="mix-period">{escape(period)}</span>'
                f'<div class="mix-bar">{segments}</div></div>')

    legend = "".join(
        f'<span><span class="dot" style="background:{colour[label]}"></span>{escape(str(label))} '
        f'<b>{fmt_pct(now.get(label, 0) * 100)}</b>'
        + (f' <span class="neutral">({fmt_pct(was.get(label, 0) * 100)} a year earlier)</span>' if prior else "")
        + '</span>'
        for label in sorted(colour, key=lambda l: -now.get(l, 0)))
    return f"""
        <div class="mix-block">
          <div class="mix-title">{escape(title)}{help_button(help_key)}</div>
          {bar(now, current["period_label"])}
          {bar(was, prior["period_label"]) if prior else ""}
          <div class="mix-legend">{legend}</div>
        </div>"""


# ---- Trends -------------------------------------------------------------------------

# (series in metrics/trends.py, title, format, lineage key, zero baseline?, (count series, noun) for few-deals)
TREND_CHARTS = [
    ("bound_premium", "Bound Premium", "money", "premium.bound_premium", True, None),
    ("binds", "Binds", "int", "funnel.binds", True, None),
    ("submissions", "Submissions", "int", "funnel.submissions", True, None),
    ("quote_rate", "Quote rate (Q/S)", "ratio", "funnel.quote_rate", False, ("submissions", "submissions")),
    ("bind_rate", "Win rate (B/Q)", "ratio", "funnel.bind_rate", False, ("quotes", "quotes")),
    ("uw_margin_pct", "UW Margin %", "pct", "quality.uw_margin_pct", False, ("binds", "binds")),
]


def _trends_panel(view) -> str:
    trends = view["result"]["trends"]
    months = trends["months"]
    selected = [m for m in months if m["selected"]]
    scope = view["filters"].to_scope(view["as_at"])
    wanted = len(scope.months or range(1, 13)) if scope.ttm_end_month is None else 12
    if not selected:
        # e.g. Q4 of this year, where the whole period is past the last complete month.
        return f"""
        <section class="trends-section">
          <h2>Month by month</h2>
          <div class="subtitle">Nothing to chart for {escape(view["result"]["current"]["period_label"])}:
            the whole period is past {escape(months[-1]["label"])}, the last month with complete data.
            The charts stop there; the figures on the other tabs still cover your period.</div>
        </section>"""
    short = (f'<div class="notice">Your period runs past {escape(months[-1]["label"])}, the last month '
             f'with complete data, so the charts show {len(selected)} of its {wanted} months in orange. '
             f'The figures on the other tabs cover the whole period.</div>'
             if len(selected) < wanted else "")
    charts = ""
    for series, title, kind, help_key, zero, few in TREND_CHARTS:
        values = trends["series"].get(series)
        if values is None:
            continue
        counts = (few[1], trends["series"].get(few[0])) if few else None
        charts += line_chart(f"trend-{series}", title, months, values, FORMATTERS[kind],
                             help_html=help_button(help_key), counts=counts,
                             few_min=SMALL_SAMPLE_MIN if few else None, include_zero=zero)
    basis_note = ('<div class="notice">On Submission date basis only DSR trends are shown - RBS has no '
                  'submission date.</div>') if view["result"]["current"]["basis_note"] else ""
    return f"""
        <section class="trends-section">
          <h2>Month by month</h2>
          <div class="subtitle">{escape(months[0]["label"])} to {escape(months[-1]["label"])}, with every
            filter except the period applied. Each month is worked out exactly like the figure on the
            other tabs. Hover or use the arrow keys on a chart to read a month.</div>
          <div class="notice">The latest months are still filling in: quotes and binds arrive weeks after a
            submission, so a dip at the right-hand end of Binds, Quote rate or Win rate is usually timing,
            not a real fall.</div>
          <div class="trend-legend"><span><i style="background:{ACCENT}"></i>Months in your period</span>
            <span><i style="background:{MUTED}"></i>Other months</span></div>
          {basis_note}{short}
          <div class="trend-grid">{charts}</div>
        </section>"""


# ---- Underwriter table ---------------------------------------------------------------

def _num(value):
    """A sortable number for data-sort; blanks sort last."""
    return "" if value is None else f"{value:.6g}"


def _underwriter_section(view) -> str:
    """Every underwriter in the other filters: sortable, searchable, with peer comparison."""
    table = view["result"]["current"]["underwriters"]
    f = view["filters"]
    duplicates = view.get("possible_duplicates") or {}

    def cell(text, sort, count=None, impossible=False):
        thin = count is not None and count < SMALL_SAMPLE_MIN and sort != ""
        title = f' title="Rests on {count} - too few to read much into"' if thin else ""
        if impossible:
            text += ('<span class="few" title="More binds than quotes: some of their bound policies '
                     'have no DSR row, so this cannot be read as a win rate">over 100%</span>')
        return f'<td data-sort="{sort}"{" class=thin" if thin else ""}{title}>{text}</td>'

    def peer_cell(ratio):
        if ratio is None:
            return '<td data-sort="">—</td>'
        css, arrow = ("good", "▲ ") if ratio >= 1.25 else ("bad", "▼ ") if ratio <= 0.75 else ("neutral", "")
        return f'<td data-sort="{ratio:.6g}"><span class="{css}">{arrow}{fmt_multiple(ratio)}</span></td>'

    rows = ""
    for r in table["rows"]:
        picked = " picked" if r["underwriter"] == f.uw else ""
        link = escape(f.query(uw=r["underwriter"]))
        dup = duplicates.get(r["underwriter"])
        dup_tag = (f'<span class="dup" title="Possibly the same person as {escape(", ".join(dup))} - '
                   f'names typed two ways count separately (workbook tab 3, Rule 5)">possible duplicate</span>'
                   if dup else "")
        rows += (f'<tr class="uw-row{picked}" data-name="{escape(str(r["name"]).lower())}" '
                 f'data-submissions="{r["submissions"]}">'
                 f'<td data-sort="{escape(str(r["name"]).lower())}"><a href="{link}">{escape(str(r["name"]))}</a>{dup_tag}</td>'
                 + cell(fmt_int(r["submissions"]), r["submissions"])
                 + cell(fmt_ratio_pct(r["quote_rate"]), _num(r["quote_rate"]), r["submissions"])
                 + cell(fmt_int(r["binds"]), _num(r["binds"]))
                 + cell(fmt_ratio_pct(r["bind_rate"]), _num(r["bind_rate"]), r["quotes"],
                        impossible=(r["bind_rate"] or 0) > 1)
                 + cell(fmt_money(r["premium"]), _num(r["premium"]))
                 + peer_cell(r["premium_vs_peer_median"])
                 + cell(fmt_pct(r["uw_margin_pct"]), _num(r["uw_margin_pct"]), r["binds"])
                 + "</tr>")
    headers = "".join(
        f'<th aria-sort="{"descending" if key == "premium" else "none"}">'
        f'<button type="button" class="sort" data-col="{i + 1}">{escape(label)}</button>'
        f'{help_button("underwriters." + key)}</th>'
        for i, (key, label) in enumerate(UNDERWRITER_COLUMNS))
    total = len(table["rows"])
    n_dup = sum(1 for r in table["rows"] if r["underwriter"] in duplicates)
    query = escape(f.query())
    return f"""
        <section>
          <h2>Underwriters</h2>
          <div class="subtitle">Everyone in your other filters (the Underwriter filter is ignored here, so you
            can see a person among their peers). Peer median premium {fmt_money(table["peer_median_premium"])}:
            ▲ at least 25% above it, ▼ at least 25% below. Greyed rates rest on fewer than
            {SMALL_SAMPLE_MIN} policies. Click a name to filter the whole page to them.
            {f'{n_dup} names are flagged as possible duplicates of another name.' if n_dup else ''}</div>
          <div class="uw-controls">
            <input type="search" class="uw-search" placeholder="Find an underwriter" aria-label="Find an underwriter">
            <label class="uw-small"><input type="checkbox" data-hide-small> Hide fewer than {SMALL_SAMPLE_MIN} submissions</label>
            <span class="uw-count" aria-live="polite">{total} underwriters</span>
            <a class="action" href="/export/underwriters.csv{query}" download>Download table (CSV)</a>
          </div>
          <div class="uw-wrap">
          <table class="uw" data-total="{total}" data-small="{SMALL_SAMPLE_MIN}">
            <thead><tr><th aria-sort="none"><button type="button" class="sort" data-col="0">Underwriter</button></th>{headers}</tr></thead>
            <tbody>{rows}</tbody>
          </table>
          </div>
        </section>"""


# ---- The page body -------------------------------------------------------------------

def _is_empty(current) -> bool:
    return not current["funnel"]["submissions"] and not current["funnel"]["binds"]


def page_title(view) -> str:
    """Browser tab title: the period and any filters, so several open tabs can be told apart."""
    f = view["filters"]
    names = view["underwriter_names"]
    parts = [view["result"]["current"]["period_label"]]
    parts += [p for p in (f.bt, f.mop, f.lob, f.ent, names.get(f.uw, f.uw) if f.uw else "") if p]
    return "UW Productivity · " + " · ".join(parts)


def body(view) -> str:
    """Everything below the filter toolbar."""
    comparison = view["result"]
    current, prior = comparison["current"], comparison["prior"]
    notices = ""
    if _is_empty(current):
        notices += (f'<div class="notice empty-notice"><b>Nothing matches these filters in '
                    f'{escape(current["period_label"])}.</b> Try a wider period, or '
                    f'<a href="/">Clear all</a>.</div>')
    if view["filters"].cleared:
        cleared = ", ".join(escape(str(view["underwriter_names"].get(v, v))) for v in view["filters"].cleared)
        notices += f'<div class="notice">Cleared {cleared}: not available with the other filters picked.</div>'
    if current["basis_note"]:
        notices += f'<div class="notice">{escape(current["basis_note"])}</div>'
    if comparison.get("missing_prior_year"):
        notices += (f'<div class="notice">This extract has no {comparison["missing_prior_year"]} data, so '
                    f'there is nothing to compare {escape(current["period_label"])} with. The "a year '
                    f'earlier" column and the change are left blank rather than shown as zero.</div>')
    if prior:
        notices += incomplete_period_notice(view["filters"].to_scope(view["as_at"]), view["as_at"],
                                            prior["period_label"])

    by_tab = {key: "" for key, _ in TABS}
    for title, subtitle, rows in SECTIONS:
        if title.startswith("Productivity"):
            subtitle = current["productivity_stand_in"]["note"]
        by_tab[SECTION_TAB[title]] += _section(title, subtitle, rows, current, prior)
        if title == "What kind of book we write" and not current["basis_note"]:
            by_tab["book"] += f"""
        <section class="mixes">
          <h2>Mix of premium</h2>
          <div class="subtitle">Share of bound premium, {escape(current["period_label"])} against a year earlier.</div>
          {_mix_compare("New vs. Renewal", "composition.new_vs_renewal_mix", current, prior, "new_vs_renewal_mix")}
          {_mix_compare("Placement", "composition.placement_mix", current, prior, "placement_mix")}
        </section>"""

    by_tab["overview"] = (_hero(current, prior, comparison["trends"]) + _biggest_movers(current, prior)
                          + drivers_section(comparison))
    by_tab["underwriters"] = _underwriter_section(view)
    by_tab["trends"] = _trends_panel(view)

    panels = "".join(_panel(key, by_tab[key]) for key, _ in TABS)
    return f"""
        {_active_filters(view)}
        {notices}
        <div class="tab-row">{_tab_bar()}{_page_actions(view)}</div>
        {panels}"""


PANELS_CSS = """
.tab-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 10px 20px;
  border-bottom: 1px solid #E4E7E9;
  margin: 8px 0 28px;
}
.tabs { display: flex; flex-wrap: wrap; gap: 2px; }
.tab {
  padding: 8px 12px 9px;
  color: var(--grey);
  text-decoration: none;
  font-size: 14.5px;
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;
}
.tab:hover { color: var(--charcoal); }
.tab.active { color: var(--charcoal); font-weight: 600; border-bottom-color: var(--orange); }
.tab:focus-visible { outline: 2px solid var(--turquoise); outline-offset: -2px; }
.js-tabs .tab-panel { display: none; }
.js-tabs .tab-panel.active { display: block; }
.tab-panel > section:first-child, .tab-panel > .hero:first-child { margin-top: 0; }
.page-actions { display: flex; gap: 8px; padding-bottom: 8px; flex-wrap: wrap; }
.action {
  font: inherit;
  font-size: 13px;
  color: var(--charcoal);
  background: #FFFFFF;
  border: 1px solid #C9CFD4;
  border-radius: 6px;
  padding: 4px 10px;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
}
.action:hover { border-color: var(--grey); }
.action:focus-visible { outline: 2px solid var(--turquoise); outline-offset: 2px; }
.action.done { border-color: var(--good); color: var(--good); }
.hero .stat .change { white-space: nowrap; }
.movers-section { margin-top: 36px; }
.movers-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 36px; }
.movers-head { font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--grey); margin-bottom: 4px; }
ol.movers { list-style: none; margin: 0; padding: 0; }
ol.movers li {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0 12px;
  padding: 8px 0;
  border-bottom: 1px solid #E4E7E9;
}
ol.movers li a { color: var(--charcoal); text-decoration: none; border-bottom: 1px dotted #A9B0B6; justify-self: start; }
ol.movers li .move { font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
ol.movers li > .neutral { grid-column: 1 / -1; font-size: 12.5px; }
.mix-block { margin-top: 18px; }
.mix-title { font-weight: 600; margin-bottom: 6px; }
.mix-row { display: grid; grid-template-columns: 150px 1fr; align-items: center; gap: 12px; margin-top: 6px; }
.mix-period { font-size: 12.5px; color: var(--grey); }
.mix-row .mix-bar { margin-top: 0; gap: 2px; background: none; }
.mix-row .mix-bar span { border-radius: 2px; }
.uw-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px; margin: 4px 0 12px; }
.uw-search {
  font: inherit;
  font-size: 14px;
  padding: 5px 10px;
  border: 1px solid #C9CFD4;
  border-radius: 6px;
  min-width: 220px;
}
.uw-search:focus { outline: 2px solid var(--turquoise); border-color: transparent; }
.uw-small { font-size: 13.5px; }
.uw-count { font-size: 13px; color: var(--grey); }
.uw-controls .action { margin-left: auto; }
table.uw th { padding: 0; }
table.uw th .sort {
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--grey);
  background: none;
  border: 0;
  padding: 6px 0 6px 18px;
  cursor: pointer;
}
table.uw th:first-child .sort { padding-left: 0; }
table.uw th .sort::after { content: " \\2195"; color: #C9CFD4; }
table.uw th[aria-sort="ascending"] .sort::after { content: " \\25B2"; color: var(--charcoal); }
table.uw th[aria-sort="descending"] .sort::after { content: " \\25BC"; color: var(--charcoal); }
table.uw th .sort:focus-visible { outline: 2px solid var(--turquoise); }
.dup {
  margin-left: 8px;
  font-size: 11px;
  color: #B45309;
  border: 1px solid #F3D9B1;
  background: #FFF8EC;
  border-radius: 999px;
  padding: 0 6px;
  cursor: help;
  white-space: nowrap;
}
.empty-notice a { color: var(--orange); }
@media (max-width: 700px) {
  .movers-grid { grid-template-columns: 1fr; }
  .mix-row { grid-template-columns: 1fr; gap: 2px; }
  .uw-controls .action { margin-left: 0; }
}
@media print {
  .toolbar, .tab-row, .page-actions, .help, .uw-controls, .table-view, .link-button, footer { display: none !important; }
  .js-tabs .tab-panel { display: block !important; }
  header { background: none; color: var(--charcoal); padding: 0 0 12px; border-bottom: 2px solid var(--orange); }
  header .meta { color: var(--grey); }
  main { padding: 16px 0; max-width: none; }
  section, figure.trend, .hero { break-inside: avoid; }
  .uw-wrap { max-height: none; overflow: visible; }
}
"""

PANELS_SCRIPT = """
  <script>
  (function () {
    // ---- Tabs: the address #hash says which tab is open, so links and reloads keep it.
    var tabs = document.querySelectorAll('[data-tab]'), panels = document.querySelectorAll('[data-panel]');
    if (tabs.length) {
      document.body.classList.add('js-tabs');
      function openTab(key) {
        var known = Array.prototype.some.call(tabs, function (t) { return t.dataset.tab === key; });
        key = known ? key : 'overview';
        tabs.forEach(function (t) {
          var on = t.dataset.tab === key;
          t.classList.toggle('active', on);
          t.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        panels.forEach(function (p) { p.classList.toggle('active', p.dataset.panel === key); });
      }
      window.addEventListener('hashchange', function () { openTab(location.hash.slice(1)); });
      openTab(location.hash.slice(1));
      // Changing a filter keeps you on the same tab.
      var form = document.getElementById('filter-form');
      if (form) form.addEventListener('submit', function () {
        if (location.hash) form.action = '/' + location.hash;
      });
      document.querySelectorAll('.chip, .clear').forEach(function (a) {
        a.addEventListener('click', function () { if (location.hash) a.href = a.getAttribute('href') + location.hash; });
      });
    }

    // ---- Copy link and print.
    document.querySelectorAll('[data-copy-link]').forEach(function (b) {
      b.addEventListener('click', function () {
        var done = function () { b.textContent = 'Link copied'; b.classList.add('done');
          setTimeout(function () { b.textContent = 'Copy link'; b.classList.remove('done'); }, 2000); };
        if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, function () {
          window.prompt('Copy this link:', location.href); });
        else window.prompt('Copy this link:', location.href);
      });
    });
    document.querySelectorAll('[data-print]').forEach(function (b) {
      b.addEventListener('click', function () { window.print(); });
    });

    // ---- Underwriter table: sort, search, hide small books.
    var table = document.querySelector('table.uw');
    if (!table) return;
    var body = table.tBodies[0], rows = Array.prototype.slice.call(body.rows);
    var search = document.querySelector('.uw-search'), small = document.querySelector('[data-hide-small]');
    var count = document.querySelector('.uw-count'), minimum = +table.dataset.small;

    table.querySelectorAll('th .sort').forEach(function (button) {
      button.addEventListener('click', function () {
        var th = button.parentNode, col = +button.dataset.col;
        var dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
        if (col === 0 && th.getAttribute('aria-sort') === 'none') dir = 'ascending';
        table.querySelectorAll('th').forEach(function (h) { h.setAttribute('aria-sort', 'none'); });
        th.setAttribute('aria-sort', dir);
        rows.sort(function (a, b) {
          var x = a.cells[col].dataset.sort, y = b.cells[col].dataset.sort;
          if (x === '' && y === '') return 0;
          if (x === '') return 1;            // blanks always last
          if (y === '') return -1;
          var nx = parseFloat(x), ny = parseFloat(y);
          var cmp = (isNaN(nx) || isNaN(ny)) ? x.localeCompare(y) : nx - ny;
          return dir === 'ascending' ? cmp : -cmp;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });

    function applyFilters() {
      var q = (search.value || '').trim().toLowerCase(), shown = 0;
      rows.forEach(function (r) {
        var hide = (q && r.dataset.name.indexOf(q) === -1) || (small.checked && +r.dataset.submissions < minimum);
        r.hidden = hide;
        if (!hide) shown++;
      });
      count.textContent = shown === rows.length ? rows.length + ' underwriters'
        : 'Showing ' + shown + ' of ' + rows.length + ' underwriters';
    }
    search.addEventListener('input', applyFilters);
    small.addEventListener('change', applyFilters);
  })();
  </script>"""
