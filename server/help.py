"""The "how is this worked out?" help next to every figure on the dashboard.

Hovering (or tapping, or tabbing to) the small (i) next to a figure opens a
card with its full lineage: the original DSR / RBS columns, what the pipeline
did to each of them, which rows count, the formula, and any catches. Clicking
the (i) pins the card open so it can be read or copied.

Everything in the card comes from metrics/lineage.py - nothing is written
here - so the card, workbook tabs 10-11 and the tests always agree.
"""
from html import escape

from metrics.lineage import COLUMNS, FILTER_COLUMNS, METRICS


def help_button(key: str) -> str:
    """The (i) placed next to a figure. Empty if the figure has no lineage entry."""
    metric = METRICS.get(key)
    if metric is None:
        return ""
    return (f'<button type="button" class="help" data-help="{escape(key)}" '
            f'aria-label="How {escape(metric.title)} is worked out">i</button>')


def _column_rows(metric) -> str:
    """One table row per (report, column): original name(s) and what the pipeline did."""
    rows, seen = "", set()
    for report, shared in metric.columns:
        if (report, shared) in seen:
            continue
        seen.add((report, shared))
        column = COLUMNS[shared]
        names = column.raw(report)
        original = "<br><span class='or'>then, where blank:</span> ".join(
            f"<code>{escape(name)}</code>" for name in names)
        steps = "".join(f"<li>{escape(step)}</li>" for step in column.steps_for(report))
        rows += (f"<tr><td class='report {report.lower()}'>{report}</td>"
                 f"<td>{original}<div class='concept'>{escape(column.label)}</div></td>"
                 f"<td><ul>{steps}</ul></td></tr>")
    return rows


def _filter_line(metric) -> str:
    """Which original columns the filters use, for the reports this figure touches."""
    parts = []
    for report in metric.reports():
        names = []
        for shared in FILTER_COLUMNS:
            raw = COLUMNS[shared].raw(report)
            if raw:
                names.append(raw[0])
        parts.append(f"<b>{report}</b>: " + ", ".join(f"<code>{escape(n)}</code>" for n in names))
    return "<br>".join(parts)


def help_card(key: str) -> str:
    """The full lineage card for one figure, as HTML."""
    m = METRICS[key]
    catches = "".join(f"<li>{escape(c)}</li>" for c in m.catches)
    catches_html = f"<div class='h-label'>Worth knowing</div><ul class='catches'>{catches}</ul>" \
        if catches else ""
    check = ("<span class='ok'>✓ Rebuilt straight from these raw columns by an automatic check, "
             "and matches</span>") if m.traced else         f"<span>{escape(m.check_note or 'Not yet checked against the raw columns')}</span>"
    return f"""
      <div class="h-title">{escape(m.title)}</div>
      <div class="h-meaning">{escape(m.meaning)}</div>
      <dl>
        <dt>Worked out as</dt><dd>{escape(m.formula)}</dd>
        <dt>Rows used</dt><dd>{escape(m.rows)}</dd>
        <dt>Counted per</dt><dd>{escape(m.counted_per)}</dd>
      </dl>
      <div class="h-label">From the original reports</div>
      <table class="h-cols">
        <thead><tr><th>Report</th><th>Original column</th><th>What the pipeline does to it</th></tr></thead>
        <tbody>{_column_rows(m)}</tbody>
      </table>
      <div class="h-label">Before this, your filters narrow the rows using</div>
      <div class="h-filters">{_filter_line(m)}</div>
      {catches_html}
      <div class="h-foot">{check}<br>Code: <code>{escape(m.code)}</code> · Workbook: tab 10</div>"""


def help_templates(extra: dict = None) -> str:
    """Every card, hidden until asked for. Rendered once per page.

    extra: {id: html} for cards that depend on the figures on this page (e.g.
    what a reconciliation badge means), opened by anything with data-help="id".
    """
    cards = {key: help_card(key) for key in METRICS}
    cards.update(extra or {})
    return "".join(f'<template id="help-{escape(key)}">{html}</template>' for key, html in cards.items())


HELP_CSS = """
.help {
  display: inline-grid;
  place-items: center;
  width: 16px;
  height: 16px;
  margin-left: 6px;
  padding: 0;
  border: 1px solid #A9B0B6;
  border-radius: 50%;
  background: #FFFFFF;
  color: var(--grey);
  font: italic 600 10.5px Georgia, serif;
  line-height: 1;
  vertical-align: 1px;
  cursor: help;
}
.help:hover, .help:focus-visible, .help.pinned {
  border-color: var(--turquoise);
  background: var(--turquoise);
  color: #FFFFFF;
  outline: none;
}
th .help { vertical-align: 0; }
#help-pop {
  position: fixed;
  z-index: 50;
  width: min(520px, calc(100vw - 24px));
  max-height: 72vh;
  overflow: auto;
  background: #FFFFFF;
  border: 1px solid #E4E7E9;
  border-top: 3px solid var(--turquoise);
  border-radius: 10px;
  box-shadow: 0 14px 40px rgba(49, 62, 72, 0.22);
  padding: 14px 16px 12px;
  font-size: 13px;
  line-height: 1.45;
  text-align: left;
  white-space: normal;
  font-weight: normal;
  text-transform: none;
  letter-spacing: 0;
  color: var(--charcoal);
}
#help-pop[hidden] { display: none; }
#help-pop .h-title { font-family: Georgia, serif; font-size: 17px; }
#help-pop .h-meaning { color: var(--grey); margin-bottom: 10px; }
#help-pop dl { display: grid; grid-template-columns: 104px 1fr; gap: 4px 10px; margin: 0 0 10px; }
#help-pop dt { font-weight: 600; color: var(--grey); }
#help-pop dd { margin: 0; }
#help-pop .h-label {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--grey);
  margin: 12px 0 5px;
}
#help-pop table.h-cols { width: 100%; border-collapse: collapse; font-size: 12.5px; table-layout: fixed; }
#help-pop .h-cols th {
  text-align: left;
  font-size: 10.5px;
  color: var(--grey);
  font-weight: 600;
  padding: 3px 6px 3px 0;
  border-bottom: 1px solid #C9CFD4;
  text-transform: none;
  letter-spacing: 0;
}
#help-pop .h-cols th:nth-child(1) { width: 44px; }
#help-pop .h-cols th:nth-child(2) { width: 38%; }
#help-pop .h-cols td {
  padding: 6px 6px 6px 0;
  border-bottom: 1px solid #E4E7E9;
  vertical-align: top;
  text-align: left;
  white-space: normal;
}
#help-pop .h-cols ul, #help-pop .catches { margin: 0; padding-left: 16px; }
#help-pop .h-cols li + li, #help-pop .catches li + li { margin-top: 3px; }
#help-pop code {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  background: #F4F5F6;
  border-radius: 3px;
  padding: 0 3px;
  word-break: break-word;
}
#help-pop .report { font-weight: 700; font-size: 11px; }
#help-pop .report.dsr { color: #485CC7; }
#help-pop .report.rbs { color: var(--purple); }
#help-pop .concept { color: var(--grey); font-size: 11.5px; margin-top: 2px; }
#help-pop .or { color: var(--grey); font-size: 11px; }
#help-pop .h-filters { font-size: 12px; }
#help-pop .h-foot { margin-top: 12px; padding-top: 8px; border-top: 1px solid #E4E7E9; color: var(--grey); font-size: 12px; }
#help-pop .h-foot .ok { color: var(--good); font-weight: 600; }
#help-pop .h-close {
  position: sticky;
  top: 0;
  float: right;
  border: 0;
  background: #FFFFFF;
  color: var(--grey);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  padding: 0 0 4px 8px;
}
"""

HELP_SCRIPT = """
  <div id="help-pop" role="dialog" aria-live="polite" hidden></div>
  <script>
  (function () {
    var pop = document.getElementById('help-pop');
    var current = null, pinned = false, hideTimer = null;

    function place(button) {
      var r = button.getBoundingClientRect(), gap = 8;
      var below = window.innerHeight - r.bottom - gap - 12, above = r.top - gap - 12;
      pop.style.left = '0px'; pop.style.top = '0px'; pop.style.maxHeight = '';
      var natural = pop.offsetHeight;
      // Open below unless it fits better above; never taller than the room there is.
      var goBelow = natural <= below || below >= above;
      pop.style.maxHeight = Math.min(natural, Math.max(goBelow ? below : above, 160)) + 'px';
      var w = pop.offsetWidth, h = pop.offsetHeight;
      var left = Math.min(Math.max(12, r.left - 12), window.innerWidth - w - 12);
      var top = goBelow ? r.bottom + gap : Math.max(12, r.top - gap - h);
      pop.style.left = left + 'px'; pop.style.top = top + 'px';
    }
    function show(button, pin) {
      clearTimeout(hideTimer);
      var tpl = document.getElementById('help-' + button.dataset.help);
      if (!tpl) return;
      if (current && current !== button) current.classList.remove('pinned');
      current = button; pinned = !!pin;
      pop.innerHTML = (pinned ? '<button type="button" class="h-close" aria-label="Close">\\u00d7</button>' : '')
        + tpl.innerHTML;
      pop.hidden = false;
      button.classList.toggle('pinned', pinned);
      place(button);
    }
    function hide() {
      pop.hidden = true; pinned = false;
      if (current) current.classList.remove('pinned');
      current = null;
    }
    function hideSoon() { if (!pinned) hideTimer = setTimeout(hide, 180); }

    document.querySelectorAll('[data-help]').forEach(function (b) {
      b.addEventListener('mouseenter', function () { if (!pinned) show(b, false); });
      b.addEventListener('mouseleave', hideSoon);
      b.addEventListener('focus', function () { if (!pinned) show(b, false); });
      b.addEventListener('blur', hideSoon);
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        if (pinned && current === b) hide(); else show(b, true);
      });
    });
    pop.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    pop.addEventListener('mouseleave', hideSoon);
    pop.addEventListener('click', function (e) {
      e.stopPropagation();
      if (e.target.classList.contains('h-close')) hide();
    });
    document.addEventListener('click', function () { if (!pop.hidden) hide(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !pop.hidden) hide(); });
    window.addEventListener('scroll', function () {
      if (pop.hidden) return;
      if (pinned) place(current); else hide();
    }, true);
    window.addEventListener('resize', function () { if (current && !pop.hidden) place(current); });
  })();
  </script>"""
