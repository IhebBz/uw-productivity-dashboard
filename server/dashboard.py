"""Builds the dashboard page: the header, the filter toolbar and its menus,
the help cards and the scripts, in the Mosaic palette and number formatting
from Mosaic_Dashboard_Standards.docx (section 6). Server-rendered on every
request for the filters in the page address - no client-side templating
needed for something this size.

Everything below the toolbar - the figures (SECTIONS, HERO), tabs, charts
and the underwriter table - lives in server/panels.py.
"""
import dataclasses
from html import escape

from scope.filter import INCEPTION, SUBMISSION
from scope.period import MONTH_NAMES, describe_period, last_complete_month
from server.charts import CHARTS_CSS, CHARTS_SCRIPT
from server.filters import PERIOD_NAMES, default_state
from server.help import HELP_CSS, HELP_SCRIPT, help_templates
from server.insights import GUIDE_CARD, INSIGHTS_CSS, reconciliation_cards
from server.panels import HERO, PANELS_CSS, PANELS_SCRIPT, SECTIONS, UNDERWRITER_COLUMNS  # noqa: F401
from server.panels import body as panel_body, page_title

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
  padding: 28px 40px 80px;
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
.flag.bad { background: var(--bad); color: #FFFFFF; }
.flag.ok { background: var(--good); color: #FFFFFF; }
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
.toolbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #FFFFFF;
  border-bottom: 1px solid #E4E7E9;
  box-shadow: 0 1px 3px rgba(49, 62, 72, 0.06);
  padding: 10px 40px;
}
.toolbar form {
  max-width: 1040px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
details.menu { position: relative; }
details.menu > summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-width: 120px;
  max-width: 260px;
  padding: 6px 30px 6px 12px;
  border: 1px solid #C9CFD4;
  border-radius: 8px;
  background: #FFFFFF;
  position: relative;
  line-height: 1.25;
  user-select: none;
}
details.menu > summary::-webkit-details-marker { display: none; }
details.menu > summary::after {
  content: "";
  position: absolute;
  right: 12px;
  top: 50%;
  width: 6px;
  height: 6px;
  margin-top: -5px;
  border-right: 1.5px solid var(--grey);
  border-bottom: 1.5px solid var(--grey);
  transform: rotate(45deg);
}
details.menu[open] > summary::after { transform: rotate(225deg); margin-top: -1px; }
details.menu > summary:hover { border-color: var(--grey); }
details.menu > summary:focus-visible { outline: 2px solid var(--turquoise); outline-offset: 2px; }
details.menu[open] > summary { border-color: var(--charcoal); }
details.menu.changed > summary { border-color: var(--orange); background: #FFF7F2; }
.menu-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--grey);
}
.menu-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--charcoal);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: 320px;
  max-height: min(70vh, 560px);
  overflow: auto;
  background: #FFFFFF;
  border: 1px solid #E4E7E9;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(49, 62, 72, 0.16);
  padding: 14px 14px 0;
}
.panel-title {
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  font-size: 17px;
  margin-bottom: 4px;
}
.panel-note { color: var(--grey); font-size: 12.5px; margin: 2px 0 10px; }
.panel-search {
  width: 100%;
  font: inherit;
  font-size: 14px;
  padding: 7px 10px;
  border: 1px solid #C9CFD4;
  border-radius: 6px;
  margin-bottom: 8px;
}
.panel-search:focus { outline: 2px solid var(--turquoise); border-color: transparent; }
.choices { display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }
.choice {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.choice:hover { background: #F4F5F6; }
.choice[hidden] { display: none; }
.choice input { margin-top: 3px; accent-color: var(--orange); }
.choice b { display: block; font-weight: 600; font-size: 14px; }
.choice small { display: block; color: var(--grey); font-size: 12.5px; line-height: 1.35; }
.group-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--grey);
  margin: 10px 0 6px 8px;
}
.panel.wide { width: 440px; }
.panel.flip { left: auto; right: 0; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.panel-head .panel-title { margin: 0; }
.year-field { font-size: 13px; font-weight: 600; color: var(--grey); }
.year-field select {
  font: inherit;
  font-size: 14px;
  color: var(--charcoal);
  margin-left: 6px;
  padding: 3px 6px;
  border: 1px solid #C9CFD4;
  border-radius: 6px;
}
.pill-grid { display: grid; gap: 6px; margin-bottom: 4px; }
.pill-grid.two { grid-template-columns: repeat(2, 1fr); }
.pill-grid.three { grid-template-columns: repeat(3, 1fr); }
.pill-grid.four { grid-template-columns: repeat(4, 1fr); }
.pill-grid.six { grid-template-columns: repeat(6, 1fr); }
.pill { cursor: pointer; position: relative; }
.pill input { position: absolute; opacity: 0; pointer-events: none; }
.pill span {
  display: block;
  height: 100%;
  text-align: center;
  font-size: 13.5px;
  font-weight: 600;
  padding: 6px 4px;
  border: 1px solid #C9CFD4;
  border-radius: 6px;
  line-height: 1.3;
}
.pill small { display: block; font-size: 11.5px; font-weight: normal; color: var(--grey); }
.pill:hover span { border-color: var(--grey); background: #F9FAFA; }
.pill input:checked + span { background: var(--charcoal); border-color: var(--charcoal); color: #FFFFFF; }
.pill input:checked + span small { color: #D5DADE; }
.pill input:focus-visible + span { outline: 2px solid var(--turquoise); outline-offset: 1px; }
.pill.soon span { color: #A9B0B6; border-style: dashed; font-weight: normal; }
.panel .group-label { margin-left: 0; }
.panel .panel-note { margin-top: 10px; }
.panel-actions {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  background: #FFFFFF;
  border-top: 1px solid #E4E7E9;
  margin: 8px -14px 0;
  padding: 10px 14px;
}
.btn {
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  padding: 7px 16px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.btn.primary { background: var(--orange); color: #FFFFFF; }
.btn.primary:hover { background: #E65100; }
.btn.quiet { background: #FFFFFF; color: var(--charcoal); border-color: #C9CFD4; }
.btn:focus-visible { outline: 2px solid var(--turquoise); outline-offset: 2px; }
.active-filters {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 10px 24px;
  margin-bottom: 28px;
  font-size: 13.5px;
}
.chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.chips .lead { color: var(--grey); margin-right: 4px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px 3px 11px;
  border-radius: 999px;
  background: #FFF1E8;
  border: 1px solid #FFD2B8;
  color: var(--charcoal);
  text-decoration: none;
  font-weight: 600;
}
.chip .x {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  color: var(--grey);
  font-size: 15px;
  line-height: 1;
}
.chip:hover .x { background: var(--orange); color: #FFFFFF; }
.clear { color: var(--orange); margin-left: 6px; font-weight: 600; text-decoration: none; }
.clear:hover { text-decoration: underline; }
.context { color: var(--grey); display: flex; gap: 18px; flex-wrap: wrap; }
.unavailable { border-bottom: 1px dotted #A9B0B6; cursor: help; }
body.loading main { opacity: 0.35; transition: opacity 0.15s; pointer-events: none; }
body.loading .toolbar::after {
  content: "Updating figures\2026";
  position: absolute;
  right: 40px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 13px;
  color: var(--grey);
}
@media (max-width: 700px) {
  .toolbar { padding: 8px 16px; }
  .panel.wide { width: auto; }
  .pill-grid.six { grid-template-columns: repeat(4, 1fr); }
  details.menu { flex: 1 1 calc(50% - 8px); position: static; }
  details.menu > summary { max-width: none; min-width: 0; }
  .toolbar form { position: relative; }
  .panel { left: 0; right: 0; width: auto; }
}
.notice {
  border-left: 3px solid var(--orange);
  background: #FFF4EE;
  padding: 10px 14px;
  font-size: 13.5px;
  margin-bottom: 24px;
}
.hero .stat .change { font-size: 13px; margin-top: 2px; }
table.figures, table.uw { width: 100%; border-collapse: collapse; font-size: 14.5px; }
/* Fixed column widths so every section's columns line up down the page. */
table.figures { table-layout: fixed; }
table.figures th:nth-child(1) { width: 49%; }
table.figures th:nth-child(n+2) { width: 17%; }
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
  header { padding-left: 16px; padding-right: 16px; }
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

# What each business-type and placement choice means, shown under it in the menu.
BUSINESS_HINTS = {
    "": "New and renewal business together",
    "New": "A brand-new client relationship",
    "Renewal": "A repeat of last year's policy (RBS's Renewal Status)",
}
PLACEMENT_HINTS = {
    "": "Every way business reaches us",
    "Open Market": "Brokered case by case",
    "Facility/DUA": "Pre-agreed delegated authority",
    "Agreement": "Written under an agreement",
}
# Menus with more choices than this get a search box.
SEARCH_FROM = 12


def _choice(name, value, title, hint="", checked=False, extra_class="") -> str:
    """One radio option in a menu: a bold title with an optional grey hint under it."""
    hint_html = f'<small>{escape(hint)}</small>' if hint else ""
    return (f'<label class="choice {extra_class}"><input type="radio" name="{name}" '
            f'value="{escape(str(value))}"{" checked" if checked else ""}>'
            f'<span><b>{escape(str(title))}</b>{hint_html}</span></label>')


def _menu(label, value_text, panel, changed, wide=False) -> str:
    """A toolbar button showing its current value, opening a panel with Cancel / Apply.

    changed marks a filter that's not on its default, so it stands out.
    """
    return f"""
        <details class="menu{" changed" if changed else ""}">
          <summary><span class="menu-label">{escape(label)}</span>
            <span class="menu-value">{escape(value_text)}</span></summary>
          <div class="panel{" wide" if wide else ""}" role="dialog" aria-label="{escape(label)}">
            {panel}
            <div class="panel-actions">
              <button type="button" class="btn quiet" data-cancel>Cancel</button>
              <button type="submit" class="btn primary">Apply</button>
            </div>
          </div>
        </details>"""


def _list_menu(name, label, all_label, noun, values, selected, default, labels=None) -> str:
    """A menu choosing one value from a list, with a search box on long lists."""
    labels = labels or {}
    search = ""
    if len(values) > SEARCH_FROM:
        search = (f'<input type="search" class="panel-search" data-search '
                  f'placeholder="Search {len(values)} {noun}" aria-label="Search {noun}">')
    choices = _choice(name, "", all_label, checked=not selected, extra_class="keep")
    choices += "".join(_choice(name, v, labels.get(v, v), checked=v == selected) for v in values)
    panel = (f'<div class="panel-title">{escape(label)}</div>'
             f'<div class="panel-note">{len(values)} available with your other filters</div>'
             f'{search}<div class="choices">{choices}</div>')
    shown = labels.get(selected, selected) if selected else all_label
    return _menu(label, shown, panel, changed=selected != default)


def _period_menu(view) -> str:
    """Period: presets, a quarter, or picked months; the year; and the date basis."""
    f, as_at = view["filters"], view["as_at"]
    _, last_month = last_complete_month(as_at)
    current = view["result"]["current"]

    def span(period):
        state = dataclasses.replace(f, period=period)
        return describe_period(state.to_scope(as_at))

    def pill(name, value, text, checked, sub="", kind="radio", css="", title="", data=""):
        sub_html = f"<small>{escape(sub)}</small>" if sub else ""
        title_attr = f' title="{escape(title)}"' if title else ""
        return (f'<label class="pill {css}"{title_attr}>'
                f'<input type="{kind}" name="{name}" value="{value}"{" checked" if checked else ""} {data}>'
                f'<span>{escape(text)}{sub_html}</span></label>')

    quick = "".join(pill("period", v, PERIOD_NAMES[v], f.period == v, span(v), data="data-preset")
                    for v in ("ytd", "ttm", "full"))
    quarters = "".join(pill("period", f"q{q}", f"Q{q}", f.period == f"q{q}", data="data-preset")
                       for q in range(1, 5))
    this_year = f.year == as_at.year
    months = "".join(
        pill("m", m, MONTH_NAMES[m - 1], f.period == "custom" and m in f.months, kind="checkbox",
             css="soon" if this_year and m > last_month else "",
             title="No complete data yet" if this_year and m > last_month else "", data="data-month")
        for m in range(1, 13))
    years = "".join(f'<option value="{y}"{" selected" if y == f.year else ""}>{y}</option>'
                    for y in reversed(view["choices"]["years"]))
    basis = (pill("basis", "inception", "Inception date", f.basis == INCEPTION, "When cover starts")
             + pill("basis", "submission", "Submission date", f.basis == SUBMISSION,
                    "DSR figures only"))
    panel = f"""
            <div class="panel-head">
              <div class="panel-title">Period</div>
              <label class="year-field">Year <select name="year">{years}</select></label>
            </div>
            <div class="pill-grid three">{quick}</div>
            <div class="group-label">A quarter</div>
            <div class="pill-grid four">{quarters}</div>
            <div class="group-label">Or pick months</div>
            <input type="radio" name="period" value="custom" data-custom hidden
              {" checked" if f.period == "custom" else ""}>
            <div class="pill-grid six">{months}</div>
            <div class="group-label">Count a policy in the month of its</div>
            <div class="pill-grid two">{basis}</div>
            <div class="panel-note">Every figure is compared with the same months a year earlier.
              Submission date works for DSR figures only - RBS has no submission date.</div>"""
    name = PERIOD_NAMES[f.period]
    value = current["period_label"] if f.period == "custom" else f"{name} · {current['period_label']}"
    if f.basis == SUBMISSION:
        value += " · by submission"
    changed = (f.period, f.basis) != ("ytd", INCEPTION) or f.year != as_at.year
    return _menu("Period", value, panel, changed, wide=True)


def _choice_menu(name, label, selected, default, choices, hints) -> str:
    """A menu for a short fixed list (Business, Placement), each choice explained."""
    options = "".join(_choice(name, value, value or "All", hints.get(value, ""), checked=value == selected)
                      for value in [""] + list(choices))
    panel = f'<div class="panel-title">{escape(label)}</div><div class="choices">{options}</div>'
    return _menu(label, selected or "All", panel, changed=selected != default)


def _toolbar(view) -> str:
    """The filter toolbar: one button per filter, each opening its own small menu."""
    f, options, choices = view["filters"], view["options"], view["choices"]
    default = default_state(view["as_at"])
    return f"""
    <div class="toolbar">
      <form method="get" action="/" id="filter-form">
        {_period_menu(view)}
        {_choice_menu("bt", "Business", f.bt, default.bt, choices["business_types"], BUSINESS_HINTS)}
        {_choice_menu("mop", "Placement", f.mop, default.mop, choices["placements"], PLACEMENT_HINTS)}
        {_list_menu("lob", "Line of business", "All lines", "lines", options["line_of_business"],
                    f.lob, default.lob)}
        {_list_menu("ent", "Entity", "All entities", "entities", options["entity"], f.ent, default.ent)}
        {_list_menu("uw", "Underwriter", "All underwriters", "underwriters", options["underwriter"],
                    f.uw, default.uw, view["underwriter_names"])}
        <noscript><button type="submit" class="btn primary">Apply</button></noscript>
      </form>
    </div>"""


TOOLBAR_SCRIPT = """
  <script>
  (function () {
    var form = document.getElementById('filter-form');
    if (!form) return;
    var menus = Array.prototype.slice.call(form.querySelectorAll('details.menu'));

    function closeAll(except) {
      menus.forEach(function (m) { if (m !== except) m.open = false; });
    }
    function discard() { form.reset(); filterAll(''); }

    // One menu open at a time; leaving a menu without Apply discards its changes,
    // so Apply only ever sends what's visible in the menu you're looking at.
    menus.forEach(function (menu) {
      menu.addEventListener('toggle', function () {
        if (menu.open) {
          if (menus.some(function (m) { return m !== menu && m.open; })) discard();
          closeAll(menu);
          // Near the right edge of the window, open the menu leftwards instead.
          var panel = menu.querySelector('.panel');
          panel.classList.remove('flip');
          if (panel.getBoundingClientRect().right > window.innerWidth - 8) panel.classList.add('flip');
          var search = menu.querySelector('[data-search]');
          if (search) search.focus();
        }
      });
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('details.menu') && menus.some(function (m) { return m.open; })) {
        discard(); closeAll();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menus.some(function (m) { return m.open; })) { discard(); closeAll(); }
    });
    form.querySelectorAll('[data-cancel]').forEach(function (b) {
      b.addEventListener('click', function () { discard(); closeAll(); });
    });

    // Search boxes narrow their own list; "All" and the current choice stay visible.
    function filterList(search) {
      var q = search.value.trim().toLowerCase();
      search.parentNode.querySelectorAll('.choice').forEach(function (c) {
        var keep = c.classList.contains('keep') || c.querySelector('input').checked;
        c.hidden = q && !keep && c.textContent.toLowerCase().indexOf(q) === -1;
      });
    }
    function filterAll(value) {
      form.querySelectorAll('[data-search]').forEach(function (s) { s.value = value; filterList(s); });
    }
    form.querySelectorAll('[data-search]').forEach(function (s) {
      s.addEventListener('input', function () { filterList(s); });
    });

    // Ticking a month switches the period to "Picked months"; choosing a quick
    // pick or a quarter clears the ticked months, so only one choice ever shows.
    var custom = form.querySelector('[data-custom]');
    form.querySelectorAll('[data-month]').forEach(function (box) {
      box.addEventListener('change', function () { custom.checked = true; });
    });
    form.querySelectorAll('[data-preset]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        form.querySelectorAll('[data-month]').forEach(function (box) { box.checked = false; });
      });
    });

    // Months only travel in the address when "Picked months" is the choice; then show progress.
    form.addEventListener('submit', function () {
      var custom = form.querySelector('[data-custom]').checked;
      form.querySelectorAll('[data-month]').forEach(function (box) { box.disabled = !custom; });
      document.body.classList.add('loading');
    });
    document.querySelectorAll('.chip, .clear').forEach(function (a) {
      a.addEventListener('click', function () { document.body.classList.add('loading'); });
    });
  })();
  </script>"""


def _page_cards(view) -> dict:
    """Help cards whose content depends on this page's figures."""
    return {"guide": GUIDE_CARD, **reconciliation_cards(view["result"]["current"])}


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
        filters = _toolbar(view)
        body = panel_body(view)

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
  <title>{escape(page_title(view)) if view else "UW Productivity Dashboard"}</title>
  <style>{CSS}{HELP_CSS}{INSIGHTS_CSS}{CHARTS_CSS}{PANELS_CSS}</style>
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
  {TOOLBAR_SCRIPT if view else ""}
  {help_templates(_page_cards(view)) + HELP_SCRIPT + CHARTS_SCRIPT + PANELS_SCRIPT if view else ""}
</body>
</html>"""
