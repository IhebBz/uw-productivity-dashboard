"""Small server-drawn SVG charts: headline sparklines and the trend charts.

One visual rule throughout (emphasis form): the months in the selected
period are drawn in the accent (orange), every other month in a recessive
grey, so the eye goes to "now" and reads the rest as context. Checked with
the dataviz palette validator: orange #FF5A00 and grey #838D96 separate for
colour-blind readers and both clear 3:1 against the white page.

Every chart has:
- a hover / keyboard readout (month and value) via a crosshair,
- a "Show as table" twin, so no value is only reachable by hovering.
"""
import json
import math
from html import escape

ACCENT = "#FF5A00"
MUTED = "#838D96"
GRID = "#E4E7E9"


def nice_ticks(low, high, count=4, include_zero=True):
    """Round axis ticks (0, 25, 50...) covering low..high.

    Amounts and counts start at zero, so a bar-like reading isn't exaggerated;
    rates (include_zero=False) zoom to their own range so a real move is visible.
    """
    if low is None or high is None:
        return [0, 1]
    if include_zero:
        low, high = min(low, 0), max(high, 0)
    if high == low:
        high = low + 1
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start = math.floor(low / step) * step
    ticks, value = [], start
    while value < high + step * 0.999:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _segments(points):
    """Split (x, y or None, selected) points into runs: [(selected, [(x, y), ...]), ...].

    A missing value breaks the line. A run changes colour where the selection
    changes, sharing the boundary point so the line stays continuous.
    """
    runs, current, current_sel = [], [], None
    for x, y, sel in points:
        if y is None:
            if current:
                runs.append((current_sel, current))
            current, current_sel = [], None
            continue
        if current and sel != current_sel:
            runs.append((current_sel, current))
            current = [current[-1]]
        current_sel = sel
        current.append((x, y))
    if current:
        runs.append((current_sel, current))
    return runs


def _path(run):
    return " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(run))


def sparkline(values, selected, label, width=132, height=30):
    """A tiny trend line for a headline figure, the selected months in the accent."""
    real = [v for v in values if v is not None]
    if len(real) < 2:
        return ""
    lo, hi = min(real), max(real)
    span = (hi - lo) or 1
    step = (width - 8) / (len(values) - 1)
    points = [(4 + i * step, None if v is None else 4 + (height - 8) * (1 - (v - lo) / span), s)
              for i, (v, s) in enumerate(zip(values, selected))]
    lines = "".join(
        f'<path d="{_path(run)}" fill="none" stroke="{ACCENT if sel else MUTED}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        for sel, run in _segments(points) if len(run) > 1)
    last = next(((x, y) for x, y, _ in reversed(points) if y is not None), None)
    dot = (f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="4" fill="{ACCENT}" stroke="#FFFFFF" '
           f'stroke-width="2"/>') if last else ""
    return (f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)} - months in your period in '
            f'orange; full detail on the Trends tab</title>{lines}{dot}</svg>')


def line_chart(chart_id, title, months, values, fmt, note="", help_html="", counts=None, few_min=None,
               include_zero=True):
    """One trend chart: monthly values, selected months in the accent, hover readout, table twin.

    months:  [{"label", "short", "selected"}] from metrics/trends.py
    values:  one value (or None) per month
    fmt:     formats a value for axis, readout and table
    counts:  optional (name, [count per month]) - months below few_min are marked "few"
    """
    width, height = 520, 210
    left, right, top, bottom = 58, 14, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    real = [v for v in values if v is not None]
    if not real:
        return (f'<figure class="trend"><figcaption><b>{escape(title)}</b>{help_html}</figcaption>'
                f'<div class="trend-empty">No figures for these months.</div></figure>')

    ticks = nice_ticks(min(real), max(real), include_zero=include_zero)
    lo, hi = ticks[0], ticks[-1]
    span = (hi - lo) or 1
    step = plot_w / (len(values) - 1)
    xs = [left + i * step for i in range(len(values))]

    def y_of(v):
        return top + plot_h * (1 - (v - lo) / span)

    grid = "".join(
        f'<line x1="{left}" x2="{width - right}" y1="{y_of(t):.1f}" y2="{y_of(t):.1f}" stroke="{GRID}" '
        f'stroke-width="1"/><text x="{left - 8}" y="{y_of(t) + 4:.1f}" class="tick" text-anchor="end">'
        f'{escape(fmt(t))}</text>' for t in ticks)
    x_labels = "".join(
        f'<text x="{xs[i]:.1f}" y="{height - 8}" class="tick" text-anchor="middle">{escape(m["short"])}</text>'
        for i, m in enumerate(months) if i % 3 == (len(months) - 1) % 3)
    points = [(xs[i], None if v is None else y_of(v), months[i]["selected"]) for i, v in enumerate(values)]
    lines = "".join(
        f'<path d="{_path(run)}" fill="none" stroke="{ACCENT if sel else MUTED}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        for sel, run in _segments(points) if len(run) > 1)
    def needs_dot(i):
        """The latest month, and any month with no neighbour to draw a line to."""
        if points[i][1] is None:
            return False
        alone = (i == 0 or points[i - 1][1] is None) and (i + 1 == len(points) or points[i + 1][1] is None)
        return i == len(points) - 1 or alone

    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{ACCENT if sel else MUTED}" stroke="#FFFFFF" '
        f'stroke-width="2"/>'
        for i, (x, y, sel) in enumerate(points) if needs_dot(i))

    few = []
    if counts and few_min:
        few = [c is not None and c < few_min for c in counts[1]]
    readout = [{"x": round(xs[i], 1), "month": m["label"], "value": "-" if v is None else fmt(v),
                "y": None if v is None else round(y_of(v), 1),
                "note": f"few {counts[0]}" if few and few[i] and v is not None else ""}
               for i, (m, v) in enumerate(zip(months, values))]

    rows = ""
    for i, (m, v) in enumerate(zip(months, values)):
        shown = "—" if v is None else escape(fmt(v))
        if few and few[i] and v is not None:
            shown += f" (few {escape(counts[0])})"
        rows += f'<tr class="{"sel" if m["selected"] else ""}"><td>{escape(m["label"])}</td><td>{shown}</td></tr>'
    return f"""
        <figure class="trend" id="{chart_id}">
          <figcaption><b>{escape(title)}</b>{help_html}<span class="note">{escape(note)}</span></figcaption>
          <div class="trend-plot">
            <svg viewBox="0 0 {width} {height}" class="trend-svg" tabindex="0" role="img"
                 aria-label="{escape(title)}, monthly. Use left and right arrow keys to read each month."
                 data-points='{escape(json.dumps(readout))}' data-top="{top}" data-bottom="{height - bottom}">
              {grid}{x_labels}
              <line class="crosshair" x1="0" x2="0" y1="{top}" y2="{height - bottom}" stroke="#313E48"
                    stroke-width="1" visibility="hidden"/>
              {lines}{dots}
              <circle class="hover-dot" r="4" fill="{ACCENT}" stroke="#FFFFFF" stroke-width="2" visibility="hidden"/>
            </svg>
            <div class="trend-tip" hidden><b></b><span></span><em></em></div>
          </div>
          <details class="table-view"><summary>Show as table</summary>
            <table><thead><tr><th>Month</th><th>{escape(title)}</th></tr></thead><tbody>{rows}</tbody></table>
          </details>
        </figure>"""


CHARTS_CSS = """
.spark { display: block; margin-top: 6px; }
.trend-legend { display: flex; gap: 18px; font-size: 12.5px; color: var(--grey); margin: 0 0 14px; }
.trend-legend i { display: inline-block; width: 16px; height: 2px; vertical-align: middle; margin-right: 6px; }
.trend-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 36px; }
figure.trend { margin: 0; }
figure.trend figcaption { font-size: 14px; margin-bottom: 4px; }
figure.trend figcaption .note { display: block; color: var(--grey); font-size: 12.5px; }
.trend-plot { position: relative; }
.trend-svg { width: 100%; height: auto; display: block; overflow: visible; }
.trend-svg:focus-visible { outline: 2px solid var(--turquoise); outline-offset: 4px; border-radius: 4px; }
.trend-svg .tick { font-size: 11px; fill: #5C6670; font-variant-numeric: tabular-nums; }
.trend-tip {
  position: absolute;
  top: 0;
  pointer-events: none;
  background: #FFFFFF;
  border: 1px solid #E4E7E9;
  border-radius: 6px;
  box-shadow: 0 4px 14px rgba(49, 62, 72, 0.14);
  padding: 5px 9px;
  font-size: 12.5px;
  white-space: nowrap;
  transform: translateX(-50%);
}
.trend-tip b { display: block; font-size: 14px; color: var(--charcoal); }
.trend-tip span { color: var(--grey); }
.trend-tip em { display: block; font-style: normal; color: #B45309; font-size: 11.5px; }
.trend-tip em:empty { display: none; }
.trend-empty { color: var(--grey); padding: 40px 0; text-align: center; }
.table-view { margin-top: 6px; font-size: 12.5px; }
.table-view summary { cursor: pointer; color: var(--grey); }
.table-view table { border-collapse: collapse; margin-top: 6px; }
.table-view td, .table-view th { padding: 2px 16px 2px 0; text-align: left; font-variant-numeric: tabular-nums; }
.table-view tr.sel td { font-weight: 600; }
@media (max-width: 800px) { .trend-grid { grid-template-columns: 1fr; } }
"""

CHARTS_SCRIPT = """
  <script>
  (function () {
    document.querySelectorAll('.trend-svg').forEach(function (svg) {
      var points = JSON.parse(svg.dataset.points), tip = svg.parentNode.querySelector('.trend-tip');
      var cross = svg.querySelector('.crosshair'), dot = svg.querySelector('.hover-dot');
      var current = points.length - 1;

      function show(i) {
        current = Math.max(0, Math.min(points.length - 1, i));
        var p = points[current], box = svg.getBoundingClientRect(), scale = box.width / svg.viewBox.baseVal.width;
        cross.setAttribute('x1', p.x); cross.setAttribute('x2', p.x); cross.setAttribute('visibility', 'visible');
        if (p.y === null) { dot.setAttribute('visibility', 'hidden'); }
        else { dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y); dot.setAttribute('visibility', 'visible'); }
        tip.querySelector('b').textContent = p.value;
        tip.querySelector('span').textContent = p.month;
        tip.querySelector('em').textContent = p.note;
        tip.hidden = false;
        var left = p.x * scale, half = tip.offsetWidth / 2;
        tip.style.left = Math.max(half, Math.min(box.width - half, left)) + 'px';
      }
      function hide() {
        cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true;
      }
      svg.addEventListener('pointermove', function (e) {
        var box = svg.getBoundingClientRect(), x = (e.clientX - box.left) / (box.width / svg.viewBox.baseVal.width);
        var best = 0;
        points.forEach(function (p, i) { if (Math.abs(p.x - x) < Math.abs(points[best].x - x)) best = i; });
        show(best);
      });
      svg.addEventListener('pointerleave', hide);
      svg.addEventListener('focus', function () { show(current); });
      svg.addEventListener('blur', hide);
      svg.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') { show(current - 1); e.preventDefault(); }
        if (e.key === 'ArrowRight') { show(current + 1); e.preventDefault(); }
      });
    });
  })();
  </script>"""
