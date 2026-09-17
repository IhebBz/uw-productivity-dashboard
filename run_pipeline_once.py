"""Run the pipeline once against the Excel files in data/, print a summary,
and save the full result as JSON in outputs/.

Usage:
    python run_pipeline_once.py
"""
import json

from data_sources.excel_source import ExcelSource
from scope.filter import Scope
from pipeline.build_dashboard_data import build
from pipeline.serialize import to_json_safe
from pipeline.logging_setup import setup_logging


def main():
    """Load data/DSR.xlsx and data/RBS.xlsx, run the pipeline, print and save results."""
    setup_logging()
    source = ExcelSource(folder="data")
    scope = Scope()  # no filters: the whole book, every year in the data

    result = build(source, scope)

    print("Submissions:  ", result["funnel"]["submissions"])
    print("Quotes:       ", result["funnel"]["quotes"])
    print("Binds:        ", result["funnel"]["binds"],
          "(DSR said", result["funnel"]["binds_reconciliation"].dsr_value, ")")
    print("Bound Premium:", result["premium"]["bound_premium"])
    print("UW Margin %:  ", result["quality"]["uw_margin_pct"])
    print("Active UWs:   ", result["headcount"]["active_underwriters"])
    print("Premium / UW: ", result["headcount"]["premium_per_active_underwriter"])

    with open("outputs/latest_result.json", "w") as f:
        json.dump(to_json_safe(result), f, indent=2, default=str)
    print("\nFull result saved to outputs/latest_result.json")


if __name__ == "__main__":
    main()
