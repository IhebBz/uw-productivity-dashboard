"""The parts of the page that help people read the figures rather than show
more of them:

- what a red "vs DSR" badge means, with both figures side by side,
- a "How to read this page" guide,
- "What drove the change" in Premium per Active Underwriter,
- a flag on any figure resting on too few deals,
- a warning when the period includes months that aren't complete yet.

The cards here open through the same (i) mechanism as the lineage help
(server/help.py): anything with data-help="<id>" opens <template id="help-<id>">.
"""
from html import escape

from config.settings import (LOW_MARGIN_COVER, RECONCILIATION_TOLERANCE_PCT, SMALL_SAMPLE_MIN,
                             SMALL_TEAM_MIN)
from metrics.drivers import describe
from scope.period import MONTH_NAMES, last_complete_month
from server.formatting import FORMATTERS, fmt_amount, fmt_money, fmt_pct, fmt_ratio_pct
from server.help import help_button


def _field(obj, name):
    """Read a field from a dataclass or a dict (results can be either)."""
    if obj is None:
        return None
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


# ---- Reconciliation badges ---------------------------------------------------

RECONCILED = {
    # card id: (result path, label, format, what RBS and DSR each count)
    "recon-premium": ("premium.reconciliation", "Bound Premium", "money",
                      "RBS: premium on every RBS row. DSR: the same premium column on DSR rows with a "
                      "bound status."),
    "recon-binds": ("funnel.binds_reconciliation", "Binds", "int",
                    "RBS: different policies in RBS. DSR: different policies with a bound status."),
}


def reconciliation_badge(recon, card_id) -> str:
    """The red badge next to a cross-checked figure - only when the two reports disagree.

    Clicking or hovering it explains the gap (reconciliation_cards).
    """
    if not recon:
        return ""
    if _field(recon, "is_undefined_gap"):
        text = "check vs DSR"
    elif _field(recon, "flagged"):
        text = f"{(_field(recon, 'gap_pct') or 0) * 100:.0f}% vs DSR"
    else:
        return ""
    return (f'<button type="button" class="flag bad" data-help="{card_id}" '
            f'aria-label="Why this figure is flagged">{text}</button>')


def reconciliation_cards(current) -> dict:
    """One explanation card per flagged cross-check, with this page's actual figures."""
    cards = {}
    for card_id, (path, label, kind, how) in RECONCILED.items():
        section, key = path.split(".")
        recon = (current.get(section) or {}).get(key)
        if not recon or not _field(recon, "flagged"):
            continue
        fmt = FORMATTERS[kind]
        rbs, dsr, gap = _field(recon, "rbs_value"), _field(recon, "dsr_value"), _field(recon, "gap_pct")
        gap_text = "can't be worked out (RBS is zero)" if gap is None else f"{gap * 100:.1f}%"
        # Most of the gap is usually policies DSR has no record of at all.
        missing = (current.get("funnel") or {}).get("binds_not_in_dsr") or {}
        cause = ""
        if missing.get("policies"):
            cause = (f"<li><b>Most of it is accounted for:</b> {missing['policies']:,} of the "
                     f"{missing['of_binds']:,} bound policies in this slice have no DSR row at all "
                     f"({fmt_ratio_pct(missing['premium_share'])} of the premium), so DSR could never "
                     f"have matched RBS here.</li>")
        cards[card_id] = f"""
      <div class="h-title">Why {escape(label)} has a red badge</div>
      <div class="h-meaning">DSR and RBS were each asked for {escape(label.lower())} on exactly the same
        filters, and they disagree by more than {RECONCILIATION_TOLERANCE_PCT:.0%}.</div>
      <dl>
        <dt>RBS says</dt><dd><b>{fmt(rbs)}</b> – this is the figure shown</dd>
        <dt>DSR says</dt><dd>{fmt(dsr)}</dd>
        <dt>Gap</dt><dd>{gap_text} (a gap up to {RECONCILIATION_TOLERANCE_PCT:.0%} is normal)</dd>
      </dl>
      <div class="h-label">What each report counts</div>
      <div>{escape(how)}</div>
      <div class="h-label">What it means</div>
      <ul class="catches">
        <li>RBS is the company's source of truth for bound business, so its figure is kept
          (workbook tab 3, Rule 6).</li>
        <li>A gap this size is a signal, not a bug in the dashboard: usually the two extracts
          record some policies differently (status, dates or premium). It's open question 3 in
          workbook tab 9, for the owners of the extracts.</li>
        {cause}
      </ul>"""
    return cards


# ---- How to read this page -----------------------------------------------------

GUIDE_CARD = f"""
      <div class="h-title">How to read this page</div>
      <div class="h-meaning">Every figure is for the filters in the toolbar, next to the same months one
        year earlier.</div>
      <div class="h-label">The columns</div>
      <ul class="catches">
        <li><b>This period</b> in bold, <b>last year</b> in grey, then the <b>change</b>.</li>
        <li>Percentages change in <b>pts</b> (percentage points): 42.0% to 44.0% is +2.0 pts.
          Money and counts change in %.</li>
        <li><span class="good">Green</span> = good news, <span class="bad">red</span> = bad news, grey =
          neither (a description of the book, not a score) or no real change.</li>
      </ul>
      <div class="h-label">The marks</div>
      <ul class="catches">
        <li><b>▲ / ▼</b> next to a change: up or down, so direction never depends on colour.</li>
        <li><b>Small line under a headline figure</b>: its last 12 months, your period in orange. The
          <b>Trends</b> tab has the full charts.</li>
        <li><b>(i)</b> next to a figure: exactly how it's worked out, from which DSR / RBS columns, and
          what the pipeline did to them. Click it to keep it open.</li>
        <li><b>Red “vs DSR” badge</b>: RBS and DSR disagree on that figure by more than
          {RECONCILIATION_TOLERANCE_PCT:.0%}. Click it to see both.</li>
        <li><b>Greyed figure marked “few …”</b>: it rests on fewer than {SMALL_SAMPLE_MIN}
          policies (or, for per-person figures, fewer than {SMALL_TEAM_MIN} underwriters), so don't
          read much into it.</li>
        <li><b>—</b> (a dash): nothing to work it out from, e.g. a rate with nothing to divide by,
          or a figure that needs RBS on Submission date basis.</li>
      </ul>
      <div class="h-label">Worth knowing</div>
      <ul class="catches">
        <li><b>Underwriter counts are stand-ins</b>, not true headcount (there's no HR file): Active =
          won at least one deal; Roster = at least one submission.</li>
        <li>Everything the page says is written up in plain English in the metrics workbook
          (UW_Dashboard_Metrics_Inventory.xlsx).</li>
      </ul>"""


def guide_button() -> str:
    return ('<button type="button" class="link-button" data-help="guide">'
            'How to read this page</button>')


# ---- Thin data -----------------------------------------------------------------

# Figure -> the counts it rests on: [(count path, what it's called, minimum), ...].
# Flagged when any of them is below its minimum.
_BINDS = ("funnel.binds", "binds", SMALL_SAMPLE_MIN)
_ACTIVE = ("productivity_stand_in.active_underwriters_stand_in", "underwriters", SMALL_TEAM_MIN)
_ROSTER = ("productivity_stand_in.roster_underwriters_stand_in", "underwriters", SMALL_TEAM_MIN)
SAMPLE_BASIS = {
    "funnel.quote_rate": [("funnel.submissions", "submissions", SMALL_SAMPLE_MIN)],
    "funnel.end_to_end_win_rate": [("funnel.submissions", "submissions", SMALL_SAMPLE_MIN)],
    "funnel.bind_rate": [("funnel.quotes", "quotes", SMALL_SAMPLE_MIN)],
    "productivity_stand_in.premium_per_active_underwriter": [_ACTIVE, _BINDS],
    "productivity_stand_in.uw_margin_per_active_underwriter": [_ACTIVE, _BINDS],
    "productivity_stand_in.premium_per_roster_underwriter": [_ROSTER, _BINDS],
}
for _path in ("premium.average_deal_size", "quality.uw_margin_pct", "quality.gelr_book_basis",
              "quality.gelr_margin_basis", "quality.commission_book_basis", "quality.commission_margin_basis",
              "quality.margin_cover", "quality.commission_cover", "quality.attachment_point_excess",
              "quality.attachment_point_primary", "quality.median_limit", "pricing.rate_adequacy",
              "pricing.rate_adequacy_rbs_benchmark", "composition.mosaic_as_lead",
              "composition.primary_share", "composition.average_agency_share", "composition.scm_share",
              "composition.broker_concentration", "composition.average_policy_length"):
    SAMPLE_BASIS[_path] = [_BINDS]


def thin_data(result, path):
    """(count, noun, minimum) for the first count a figure rests on that's too small, else None."""
    if not result:
        return None
    for count_path, noun, minimum in SAMPLE_BASIS.get(path, []):
        section, key = count_path.split(".")
        count = (result.get(section) or {}).get(key)
        if count is not None and count < minimum:
            return count, noun, minimum
    return None


def few_tag(count, noun, minimum) -> str:
    """The small "few binds" tag shown next to a greyed-out figure."""
    return (f'<span class="few" title="Rests on {count} {noun} - fewer than {minimum}, '
            f'so don\'t read much into it">few {noun}</span>')


def _warn(text) -> str:
    return f'<span class="note warn">{text}</span>'


def _margin_cover_note(current) -> str:
    """UW Margin % rests on the premium that carries a usable GELR."""
    cover = (current.get("quality") or {}).get("margin_cover")
    if cover is None or cover >= LOW_MARGIN_COVER:
        return ""
    return _warn(f"Based on only {fmt_ratio_pct(cover)} of premium - the rest has no usable GELR")


def _commission_note(current) -> str:
    """UW Margin % counts a blank or zero commission as no commission charged.

    A blank GELR is treated as unusable and left out, so the two halves of
    100 - GELR - Commission handle a missing value in opposite ways, and every
    row with no commission recorded pushes the margin up. This says by how
    much (workbook tab 9, question 25).
    """
    quality = current.get("quality") or {}
    cover, alternative = quality.get("commission_cover"), quality.get("uw_margin_pct_recorded_commission")
    margin = quality.get("uw_margin_pct")
    if None in (cover, alternative, margin) or cover >= 0.99:
        return ""
    return _warn(f"{fmt_ratio_pct(1 - cover)} of the margin premium records no commission, counted as "
                 f"none charged. Over the rows that do record one, margin reads "
                 f"{fmt_pct(alternative)}")


def _funnel_gap_note(current) -> str:
    """B/Q and B/S divide RBS binds by DSR quotes - not every bind is in DSR."""
    gap = (current.get("funnel") or {}).get("binds_not_in_dsr") or {}
    if not gap.get("policies"):
        return ""
    restricted = f", which would read {fmt_ratio_pct(gap['bind_rate'])}" if gap.get("bind_rate") else ""
    return _warn(f"{gap['policies']:,} of {gap['of_binds']:,} bound policies "
                 f"({fmt_ratio_pct(gap['premium_share'])} of premium) have no DSR row at all, so this is "
                 f"overstated against a funnel of only the binds DSR knows about{restricted}")


def _bind_rate_note(current) -> str:
    note = _funnel_gap_note(current)
    quotes, binds = (current.get("funnel") or {}).get("quotes"), (current.get("funnel") or {}).get("binds")
    if quotes and binds and binds > quotes:
        note = _warn(f"More binds ({binds:,}) than quotes ({quotes:,}) in this slice, so this rate is "
                     f"above 100% and can't be read as a win rate") + note
    return note


# Figure -> extra note under its label, worked out from this period's figures.
NOTE_BUILDERS = {
    "quality.uw_margin_pct": (_margin_cover_note, _commission_note),
    "productivity_stand_in.uw_margin_per_active_underwriter": (_margin_cover_note, _commission_note),
    "funnel.bind_rate": (_bind_rate_note,),
    "funnel.end_to_end_win_rate": (_funnel_gap_note,),
}


def extra_note(current, path) -> str:
    """Any warning notes this figure needs for the period on screen."""
    return "".join(build(current) for build in NOTE_BUILDERS.get(path, ()))


# ---- Incomplete months ---------------------------------------------------------

def incomplete_period_notice(scope, as_at, prior_label) -> str:
    """Warn when the period includes months with no complete data yet.

    E.g. "Full year 2026" in September compares 8 complete months with 12 -
    this year looks worse than it is.
    """
    if scope.year != as_at.year or scope.ttm_end_month is not None or not scope.months:
        return ""
    _, last_month = last_complete_month(as_at)
    late = [m for m in scope.months if m > last_month]
    if not late:
        return ""
    names = MONTH_NAMES[late[0] - 1] if len(late) == 1 else \
        f"{MONTH_NAMES[late[0] - 1]}–{MONTH_NAMES[late[-1] - 1]}"
    verb = "isn't" if len(late) == 1 else "aren't"
    return (f'<div class="notice">{names} {scope.year} {verb} complete yet (data as at '
            f'{as_at:%d %b %Y}), so this year\'s figures will look low next to {escape(prior_label)}. '
            f'Choose <b>This year so far</b> in Period to compare like with like.</div>')


# ---- What drove the change ------------------------------------------------------

_DRIVER_FORMAT = {
    "submissions_per_underwriter": lambda v: f"{v:,.1f}",
    "quote_rate": fmt_ratio_pct,
    "bind_rate": fmt_ratio_pct,
    "average_deal_size": fmt_amount,
}


def drivers_section(comparison) -> str:
    """Premium per Active Underwriter this year vs last, split into its four drivers."""
    drivers = comparison.get("drivers")
    current, prior = comparison["current"], comparison["prior"]
    if prior is None or current.get("basis_note"):
        return ""
    title = f'What drove Premium / Active Underwriter{help_button("drivers.premium_per_active_underwriter")}'
    thin = thin_data(current, "premium.average_deal_size") or thin_data(prior, "premium.average_deal_size")
    if thin:
        return f"""
        <section class="drivers">
          <h2>{title}</h2>
          <div class="subtitle">Not split for these filters: one of the two periods rests on only
            {thin[0]} {thin[1]}, too few to read a driver story into.</div>
        </section>"""
    if not drivers:
        return f"""
        <section class="drivers">
          <h2>{title}</h2>
          <div class="subtitle">Can't be split for these filters: one of the two years has no
            submissions, quotes, binds or premium to work from.</div>
        </section>"""

    scale = max(abs(r["contribution"]) for r in drivers["rows"]) or 1
    rows = ""
    for r in drivers["rows"]:
        fmt = _DRIVER_FORMAT[r["key"]]
        width = abs(r["contribution"]) / scale * 50  # half the track each side of the middle
        side = "up" if r["contribution"] >= 0 else "down"
        bar_style = f"width:{width:.1f}%;" + ("left:50%" if side == "up" else f"left:{50 - width:.1f}%")
        rows += f"""
            <tr>
              <td class="d-label">{escape(r["label"])}<span class="note">{escape(r["meaning"])}</span></td>
              <td class="d-vals">{fmt(r["prior"])} → <b>{fmt(r["current"])}</b></td>
              <td class="d-change {side}">{r["change"] * 100:+.1f}%</td>
              <td class="d-bar"><div class="track"><span class="{side}" style="{bar_style}"></span></div></td>
              <td class="d-contrib {side}">{r["contribution"] * 100:+.1f} pts</td>
            </tr>"""
    total_side = "up" if drivers["total_change"] >= 0 else "down"
    return f"""
        <section class="drivers">
          <h2>{title}</h2>
          <div class="subtitle">{escape(describe(drivers))}</div>
          <table class="drivers-table">
            <thead><tr><th>Driver</th><th>Last year → this year</th><th>Change</th>
              <th>Share of the move</th><th></th></tr></thead>
            <tbody>{rows}
            <tr class="total">
              <td class="d-label">Premium / Active Underwriter</td>
              <td class="d-vals">{fmt_money(drivers["prior"])} → <b>{fmt_money(drivers["current"])}</b></td>
              <td class="d-change {total_side}">{drivers["total_change"] * 100:+.1f}%</td>
              <td class="d-bar"></td>
              <td class="d-contrib {total_side}">{drivers["total_change"] * 100:+.1f} pts</td>
            </tr>
            </tbody>
          </table>
        </section>"""


INSIGHTS_CSS = """
.flag { border: 0; font-family: inherit; cursor: help; }
.link-button {
  border: 0;
  background: none;
  padding: 0;
  font: inherit;
  color: var(--charcoal);
  border-bottom: 1px dotted #A9B0B6;
  cursor: help;
}
.link-button:hover, .link-button:focus-visible { color: var(--orange); border-color: var(--orange); outline: none; }
td.thin, .hero .stat.thin .value { color: #A9B0B6; }
.few {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 999px;
  background: #F4F5F6;
  border: 1px solid #E4E7E9;
  color: var(--grey);
  font-size: 11px;
  font-weight: 600;
  vertical-align: 1px;
  white-space: nowrap;
  cursor: help;
}
.note.warn { color: #B45309; }
section.drivers { margin-top: 36px; }
table.drivers-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
table.drivers-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--grey);
  padding: 6px 12px 6px 0;
  border-bottom: 1px solid #C9CFD4;
}
table.drivers-table th:nth-child(1) { width: 30%; }
table.drivers-table th:nth-child(2) { width: 22%; }
table.drivers-table th:nth-child(3) { width: 9%; }
table.drivers-table th:nth-child(5) { width: 10%; }
table.drivers-table td { padding: 9px 12px 9px 0; border-bottom: 1px solid #E4E7E9; vertical-align: middle; }
table.drivers-table .note { display: block; color: var(--grey); font-size: 12.5px; }
table.drivers-table .d-vals, table.drivers-table .d-change, table.drivers-table .d-contrib {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
table.drivers-table .d-contrib { text-align: right; font-weight: 600; padding-right: 0; }
table.drivers-table .up { color: var(--good); }
table.drivers-table .down { color: var(--bad); }
table.drivers-table tr.total td { border-top: 2px solid var(--charcoal); border-bottom: 0; font-weight: 600; }
.track { position: relative; height: 12px; background: #F4F5F6; border-radius: 3px; }
.track::after {
  content: "";
  position: absolute;
  left: 50%;
  top: -3px;
  bottom: -3px;
  border-left: 1px solid #A9B0B6;
}
.track span { position: absolute; top: 0; bottom: 0; border-radius: 2px; }
.track span.up { background: var(--good); }
.track span.down { background: var(--bad); }
@media (max-width: 700px) {
  table.drivers-table th:nth-child(4), table.drivers-table td.d-bar { display: none; }
  table.drivers-table th:nth-child(2) { width: 34%; }
}
"""
