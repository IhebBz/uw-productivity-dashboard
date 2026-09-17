"""Renders the computed metrics as an actual dashboard page, in the Mosaic
palette and number formatting from Mosaic_Dashboard_Standards.docx (section
6). Server-rendered on every request from whatever the background thread
last computed - no client-side templating needed for something this size.
"""
from server.formatting import fmt_money, fmt_pct, fmt_int, fmt_ratio_pct

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
  max-width: 900px;
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
footer {
  color: var(--grey);
  font-size: 12px;
  text-align: center;
  padding: 24px 0 48px;
}
"""

MIX_COLORS = ["#FF5A00", "#4DBCC6", "#485CC7", "#BB29BB", "#5C6670"]


def _reconciliation_flag(recon: dict) -> str:
    """A small badge next to a figure that's been cross-checked - only
    shown when it's actually flagged, since a badge on every row would
    just be noise (per the design principle of not decorating everything).
    """
    if not recon:
        return ""
    if recon.get("is_undefined_gap"):
        return '<span class="flag bad">check vs DSR</span>'
    if recon.get("flagged"):
        gap = recon.get("gap_pct") or 0
        return f'<span class="flag bad">{gap * 100:.0f}% vs DSR</span>'
    return ""


def _mix_bar(mix: dict, key: str = None) -> str:
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
        f'{label} {fmt_pct(share * 100)}</span>'
        for i, (label, share) in enumerate(items)
    )
    return f'<div class="mix-bar">{bar}</div><div class="mix-legend">{legend}</div>'


def render_dashboard(result: dict, last_run: str, error: str) -> str:
    """Build the full HTML page from one computed result dict."""
    if error:
        body = f"""
        <div class="empty">
          <div class="value">Last run failed</div>
          <div>{error}</div>
        </div>"""
    elif not result:
        body = """
        <div class="empty">
          <div class="value">Computing your first result&hellip;</div>
          <div>Reading a full DSR/RBS extract can take a few minutes the first
          time. After that, an unchanged file is cached and reloads almost
          instantly - this page checks again automatically, no need to
          refresh by hand.</div>
        </div>"""
    else:
        f = result["funnel"]
        p = result["premium"]
        q = result["quality"]
        c = result["composition"]
        h = result["headcount"]

        body = f"""
        <div class="hero">
          <div class="stat">
            <div class="value">{fmt_money(p['bound_premium'])}</div>
            <div class="label">Bound Premium{_reconciliation_flag(p.get('reconciliation'))}</div>
          </div>
          <div class="stat">
            <div class="value">{fmt_pct(q['uw_margin_pct'])}</div>
            <div class="label">UW Margin %</div>
          </div>
          <div class="stat">
            <div class="value">{fmt_int(f['binds'])}</div>
            <div class="label">Binds{_reconciliation_flag(f.get('binds_reconciliation'))}</div>
          </div>
        </div>

        <section>
          <h2>The funnel</h2>
          <div class="subtitle">From DSR - every risk that came in, won or not</div>
          <div class="row"><span class="label">Submissions</span>
            <span class="value">{fmt_int(f['submissions'])}</span></div>
          <div class="row"><span class="label">Quotes</span>
            <span class="value">{fmt_int(f['quotes'])}</span></div>
          <div class="row"><span class="label">Quote rate (Q/S)</span>
            <span class="value">{fmt_ratio_pct(f['quote_rate'])}</span></div>
          <div class="row"><span class="label">Win rate (B/Q)</span>
            <span class="value">{fmt_ratio_pct(f['bind_rate'])}</span></div>
          <div class="row"><span class="label">End-to-end win rate (B/S)</span>
            <span class="value">{fmt_ratio_pct(f['end_to_end_win_rate'])}</span></div>
        </section>

        <section>
          <h2>Book quality and pricing</h2>
          <div class="subtitle">From RBS - the source of truth for bound business</div>
          <div class="row"><span class="label">GELR</span>
            <span class="value">{fmt_pct(q['gelr_margin_basis'])}</span></div>
          <div class="row"><span class="label">Commission</span>
            <span class="value">{fmt_pct(q['commission_margin_basis'])}</span></div>
          <div class="row"><span class="label">Margin cover</span>
            <span class="value">{fmt_ratio_pct(q['margin_cover'])}</span></div>
          <div class="row"><span class="label">Rate Adequacy</span>
            <span class="value">{fmt_pct(q['rate_adequacy'])}</span></div>
          <div class="row"><span class="label">RARC (renewals)</span>
            <span class="value">{fmt_pct(q['rarc'])}</span></div>
        </section>

        <section>
          <h2>What kind of book we write</h2>
          <div class="row"><span class="label">Mosaic as lead</span>
            <span class="value">{fmt_ratio_pct(c['mosaic_as_lead'])}</span></div>
          <div class="row"><span class="label">Primary share</span>
            <span class="value">{fmt_ratio_pct(c['primary_share'])}</span></div>
          <div style="margin-top:18px">
            <div class="row" style="border:none;padding-bottom:0"><span class="label">New vs. Renewal mix</span></div>
            {_mix_bar(c['new_vs_renewal_mix'])}
          </div>
          <div style="margin-top:18px">
            <div class="row" style="border:none;padding-bottom:0"><span class="label">Placement mix</span></div>
            {_mix_bar(c['placement_mix'])}
          </div>
        </section>

        <section>
          <h2>Productivity (stand-in headcount)</h2>
          <div class="subtitle">No HR file available - see the metrics workbook for why</div>
          <div class="row"><span class="label">Active underwriters</span>
            <span class="value">{fmt_int(h['active_underwriters'])}</span></div>
          <div class="row"><span class="label">Roster underwriters</span>
            <span class="value">{fmt_int(h['roster_underwriters'])}</span></div>
          <div class="row"><span class="label">Premium / Active Underwriter</span>
            <span class="value">{fmt_money(h['premium_per_active_underwriter'])}</span></div>
          <div class="row"><span class="label">UW Margin / Active Underwriter</span>
            <span class="value">{fmt_money(h['uw_margin_per_active_underwriter'])}</span></div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>UW Productivity Dashboard</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <div class="brand">Mosaic &middot; UW Productivity</div>
    <div class="meta">{"Last run " + last_run if last_run else "Not yet run"}</div>
  </header>
  <main>
    {body}
  </main>
  <footer>Confidential &middot; internal use only</footer>
</body>
</html>"""