"""Collects everything the presentation pack needs into one JSON file.

The Word document (docs/build_presentation_doc.js) and the metric definition
sheet (docs/build_metric_definitions.py) both read this, so the pack, the
workbook and the code can't drift apart: figures come from the pipeline,
column names and formulas from metrics/lineage.py, and the open questions,
checks and Matt comparison straight from the workbook tabs.

Run from the project root:
    python docs/export_doc_facts.py
"""
import json
import logging
import pathlib
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_sources.excel_source import ExcelSource  # noqa: E402
from metrics.lineage import COLUMNS, METRICS  # noqa: E402
from pipeline.build_dashboard_data import compute_with_comparison, prepare  # noqa: E402
from scope.filter import Scope  # noqa: E402
from scope.period import last_complete_month  # noqa: E402
from server.formatting import FORMATTERS, fmt_change  # noqa: E402
from server.panels import HERO, SECTIONS, UNDERWRITER_COLUMNS  # noqa: E402

logging.disable(logging.WARNING)
WORKBOOK = ROOT / "docs" / "UW_Dashboard_Metrics_Inventory.xlsx"
OUT = ROOT / "docs" / "doc_facts.json"

# How each figure is formatted, taken from the page itself so the pack shows
# the same thing the dashboard does.
KINDS = {path: kind for _, _, rows in SECTIONS for path, _, kind, _, _ in rows}
KINDS.update({f"underwriters.{key}": "money" if key == "premium" else "ratio"
              for key, _ in UNDERWRITER_COLUMNS})
SECTION_OF = {path: title for title, _, rows in SECTIONS for path, *_ in rows}
# Figures that aren't rows on the page (a note, a card, the driver split) still
# belong to a part of it, so the pack can group them where a reader expects.
SECTION_BY_PREFIX = {
    "funnel": "The funnel", "premium": "How much we wrote", "quality": "How good the business is",
    "pricing": "Pricing", "composition": "What kind of book we write",
    "productivity_stand_in": "Productivity (stand-in headcount)", "underwriters": "Underwriters",
    "drivers": "Overview",
}
# The same formats the page uses, for figures that have no row of their own.
KIND_BY_PREFIX = {"quality": "pct", "pricing": "pct", "funnel": "ratio", "premium": "money",
                  "composition": "ratio", "productivity_stand_in": "money", "underwriters": "money"}
LABELS = {path: label for _, _, rows in SECTIONS for path, label, *_ in rows}


def _value(result, path):
    section, key = path.split(".")
    kind = KINDS.get(path) or KIND_BY_PREFIX.get(section)
    value = (result.get(section) or {}).get(key)
    if kind is None or not isinstance(value, (int, float)):
        return None
    return FORMATTERS[kind](value)


def _rows_from_tab(sheet, first_data_row, columns):
    """Rows of a generated workbook tab as dicts, skipping its section headers."""
    out = []
    for row in sheet.iter_rows(min_row=first_data_row, values_only=True):
        if row[0] is None:
            continue
        if all(cell is None for cell in row[1:]):          # a section header
            out.append({"section": str(row[0])})
            continue
        out.append({name: ("" if row[i] is None else str(row[i])) for i, name in enumerate(columns)})
    return out


def _headline(current, prior, path, label, kind):
    section, key = path.split(".")
    now = (current.get(section) or {}).get(key)
    was = (prior.get(section) or {}).get(key) if prior else None
    change, _ = fmt_change(now, was, kind)
    return {"label": label, "now": FORMATTERS[kind](now),
            "prior": FORMATTERS[kind](was) if prior else None,
            "change": change.replace("▲ ", "up ").replace("▼ ", "down ").replace("+", "")}


def main():
    data = prepare(ExcelSource(folder=str(ROOT / "data")))
    year, month = last_complete_month(data.as_at)
    scope = Scope(year=year, months=list(range(1, month + 1)))
    comparison = compute_with_comparison(data, scope)
    current, prior = comparison["current"], comparison["prior"]

    metrics = []
    for key, metric in METRICS.items():
        columns = []
        seen = set()
        for report, shared in metric.columns:
            if (report, shared) in seen:
                continue
            seen.add((report, shared))
            column = COLUMNS[shared]
            columns.append({
                "report": report,
                "names": list(column.raw(report)),
                "label": column.label,
                "steps": column.steps_for(report),
                "required": column.required,
            })
        metrics.append({
            "key": key,
            "title": metric.title,
            "meaning": metric.meaning,
            "formula": metric.formula,
            "rows": metric.rows,
            "counted_per": metric.counted_per,
            "columns": columns,
            "catches": metric.catches,
            "code": metric.code,
            "traced": metric.traced,
            "check_note": metric.check_note,
            "workbook": metric.workbook,
            "section": SECTION_OF.get(key) or SECTION_BY_PREFIX.get(key.split(".")[0], "Overview"),
            "on_the_page": (key in SECTION_OF or key.startswith("underwriters.")
                            or key.startswith("drivers.")),
            "label": LABELS.get(key, metric.title),
            "now": _value(current, key),
            "prior": _value(prior, key) if prior else None,
        })

    columns = []
    for shared, column in COLUMNS.items():
        columns.append({
            "shared": shared,
            "label": column.label,
            "dsr": list(column.dsr),
            "rbs": list(column.rbs),
            "steps": column.steps,
            "dsr_steps": column.dsr_steps,
            "rbs_steps": column.rbs_steps,
            "required": column.required,
            "used_by": sorted({m.title for m in METRICS.values()
                               if any(s == shared for _, s in m.columns)}),
        })

    wb = openpyxl.load_workbook(WORKBOOK, data_only=True)
    questions = _rows_from_tab(wb["9. Decisions & questions"], 4,
                               ["number", "question", "today", "options", "status", "who", "raised",
                                "where"])
    checks = _rows_from_tab(wb["13. Checks & safeguards"], 4,
                            ["check", "looks_at", "if_it_fails", "kind", "where", "result"])
    versus = _rows_from_tab(wb["12. Ours vs Matt's build"], 4,
                            ["figure", "matt", "ours", "same", "worth", "which", "where"])
    filters = _rows_from_tab(wb["7. Filters"], 4,
                             ["filter", "what", "choices", "matt", "ours", "note", "default", "where"])

    facts = {
        "as_at": f"{data.as_at:%d %b %Y}",
        "period": current["period_label"],
        "prior_period": prior["period_label"] if prior else None,
        "rows": {"dsr": len(data.dsr), "rbs": len(data.rbs)},
        "headline": [_headline(current, prior, path, label, kind) for path, label, kind, _, _ in HERO],
        "reconciliation": {
            "premium": {k: getattr(current["premium"]["reconciliation"], k)
                        for k in ("dsr_value", "rbs_value", "gap_pct")},
            "binds": {k: getattr(current["funnel"]["binds_reconciliation"], k)
                      for k in ("dsr_value", "rbs_value", "gap_pct")},
            "binds_not_in_dsr": current["funnel"]["binds_not_in_dsr"],
        },
        "drivers": comparison["drivers"],
        "duplicates": {data.underwriter_names[k]: v for k, v in data.possible_duplicates.items()},
        "metrics": metrics,
        "columns": columns,
        "questions": questions,
        "checks": checks,
        "versus": versus,
        "filters": filters,
    }
    OUT.write_text(json.dumps(facts, indent=1, default=str), encoding="utf-8")
    print(f"Wrote {OUT.name}: {len(metrics)} metrics, {len(columns)} columns, "
          f"{len([q for q in questions if q.get('number')])} questions, "
          f"{len([c for c in checks if c.get('check')])} checks.")


if __name__ == "__main__":
    main()
