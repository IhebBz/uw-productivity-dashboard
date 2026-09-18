"""Downloads of what's on the page, for the filters in the address:

- figures.csv: every figure, this period and a year earlier, the change, a
  few-deals flag, and where it comes from (report and original columns, from
  metrics/lineage.py) - so a download carries its own lineage.
- underwriters.csv: the underwriter table, with possible duplicate names.

CSV opens directly in Excel. A short header block says which filters and
period the numbers are for, so a saved file still makes sense next month.
"""
import csv
import io

from metrics.lineage import COLUMNS, METRICS
from server.panels import SECTIONS
from server.formatting import FORMATTERS, change_value
from server.insights import thin_data


def _filters_lines(view):
    f = view["filters"]
    names = view["underwriter_names"]
    current, prior = view["result"]["current"], view["result"]["prior"]
    return [
        ["UW Productivity Dashboard"],
        ["Data as at", f"{view['as_at']:%d %b %Y}"],
        ["Period", current["period_label"]],
        ["Compared with", prior["period_label"] if prior else "-"],
        ["Date basis", f.basis],
        ["Business", f.bt or "All"], ["Placement", f.mop or "All"],
        ["Line of business", f.lob or "All"], ["Entity", f.ent or "All"],
        ["Underwriter", names.get(f.uw, f.uw) if f.uw else "All"],
        [],
    ]


def _source(key):
    metric = METRICS.get(key)
    if not metric:
        return "", ""
    columns = sorted({f"{report}: {' / '.join(COLUMNS[shared].raw(report))}"
                      for report, shared in metric.columns})
    return " + ".join(metric.reports()), "; ".join(columns)


def _get(result, path):
    if result is None:
        return None
    section, key = path.split(".")
    return (result.get(section) or {}).get(key)


def figures_csv(view) -> str:
    current, prior = view["result"]["current"], view["result"]["prior"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(_filters_lines(view))
    writer.writerow(["Section", "Figure", current["period_label"], prior["period_label"] if prior else "Prior",
                     "Change", "Change unit", "Few deals?", "Value (unformatted)", "Prior (unformatted)",
                     "Report", "Original columns"])
    for title, _, rows in SECTIONS:
        for path, label, kind, _, _ in rows:
            now, was = _get(current, path), _get(prior, path)
            change, unit = change_value(now, was, kind)
            thin = thin_data(current, path)
            report, columns = _source(path)
            writer.writerow([title, label, FORMATTERS[kind](now), FORMATTERS[kind](was),
                             "" if change is None else change, unit.strip(),
                             f"yes - {thin[0]} {thin[1]}" if thin else "",
                             "" if now is None else now, "" if was is None else was, report, columns])
    return out.getvalue()


def underwriters_csv(view) -> str:
    table = view["result"]["current"]["underwriters"]
    duplicates = view.get("possible_duplicates") or {}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(_filters_lines(view))
    writer.writerow(["Underwriter", "Submissions", "Quotes", "Q/S", "Binds", "B/Q", "Premium (USD)",
                     "vs peer median", "UW Margin %", "Possible duplicate of"])
    for r in table["rows"]:
        writer.writerow([r["name"], r["submissions"], r["quotes"],
                         "" if r["quote_rate"] is None else round(r["quote_rate"], 4),
                         "" if r["binds"] is None else r["binds"],
                         "" if r["bind_rate"] is None else round(r["bind_rate"], 4),
                         "" if r["premium"] is None else round(r["premium"], 2),
                         "" if r["premium_vs_peer_median"] is None else round(r["premium_vs_peer_median"], 3),
                         "" if r["uw_margin_pct"] is None else round(r["uw_margin_pct"], 2),
                         "; ".join(duplicates.get(r["underwriter"], []))])
    return out.getvalue()
