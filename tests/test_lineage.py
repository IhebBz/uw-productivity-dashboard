"""Keeps the lineage in metrics/lineage.py honest - it's what the dashboard's
(i) help and workbook tabs 10-11 show, so it must match the real pipeline.

Fails when:
- a figure on the page has no lineage (so its (i) would be missing),
- the lineage names a column the pipeline doesn't read, or the pipeline reads
  a column the lineage doesn't mention,
- a figure is marked "checked against raw columns" but the raw-column check
  (tests/test_trace_to_source.py) doesn't actually compare it.
"""
import pytest

import tests.test_trace_to_source as trace
from ingest import clean_dsr, clean_rbs
from metrics.lineage import COLUMNS, DSR, METRICS, RBS, raw_columns
from pipeline.build_dashboard_data import compute_with_comparison
from scope.filter import Scope
from server.dashboard import HERO, SECTIONS, UNDERWRITER_COLUMNS
from server.help import help_card
from tests.sample_data import prepared

MIXES = ["composition.new_vs_renewal_mix", "composition.placement_mix"]
DRIVERS = ["drivers.premium_per_active_underwriter"]


def _figures_on_page():
    keys = {path for _, _, rows in SECTIONS for path, *_ in rows}
    keys |= {path for path, *_ in HERO}
    keys |= {f"underwriters.{key}" for key, _ in UNDERWRITER_COLUMNS}
    return keys | set(MIXES) | set(DRIVERS)


def test_every_figure_on_the_page_has_lineage():
    missing = sorted(_figures_on_page() - set(METRICS))
    assert not missing, f"No lineage in metrics/lineage.py for: {missing}"


def test_every_lineage_entry_is_a_real_figure():
    """No stale entries for figures the pipeline no longer produces."""
    comparison = compute_with_comparison(prepared(), Scope(year=2026, months=list(range(1, 9))))
    result = comparison["current"]
    for key in METRICS:
        section, name = key.split(".")
        if section == "drivers":
            assert "drivers" in comparison, key
        elif section == "underwriters":
            assert name in result["underwriters"]["rows"][0], key
        else:
            assert name in result[section], key


def test_every_column_a_figure_uses_exists_for_that_report():
    for key, metric in METRICS.items():
        for report, shared in metric.columns:
            assert shared in COLUMNS, f"{key}: unknown column '{shared}'"
            assert COLUMNS[shared].raw(report), f"{key}: '{shared}' has no {report} column"


def test_lineage_names_exactly_the_columns_the_pipeline_reads():
    """Both directions: nothing documented that isn't read, nothing read that isn't documented."""
    dsr_read = set(clean_dsr.REQUIRED_COLUMNS)
    rbs_read = (set(clean_rbs.REQUIRED_COLUMNS) | set(clean_rbs.OPTIONAL_COLUMNS.values())
                | {clean_rbs.RARC_COLUMN, clean_rbs.EXPIRED_PREMIUM_COLUMN})
    assert raw_columns(DSR) == dsr_read
    assert raw_columns(RBS) == rbs_read


def test_required_and_optional_match_the_pipeline():
    """A column marked optional really is optional in ingest/, and vice versa."""
    for shared, column in COLUMNS.items():
        for name in column.dsr:
            assert column.required == (name in clean_dsr.REQUIRED_COLUMNS), shared
        for name in column.rbs:
            assert column.required == (name in clean_rbs.REQUIRED_COLUMNS), shared


def test_unchecked_figures_say_why():
    """A figure not rebuilt from raw columns must say what it relies on instead."""
    for key, metric in METRICS.items():
        assert metric.traced or metric.check_note, key


def test_every_help_card_renders():
    for key in METRICS:
        html = help_card(key)
        assert "From the original reports" in html and "<code>" in html


@pytest.mark.skipif(not (trace.DATA / "DSR.xlsx").exists(), reason="real extracts not in data/")
def test_figures_marked_checked_are_really_checked():
    """"Checked against raw columns" in the (i) help must mean test_trace_to_source compares it."""
    from data_sources.excel_source import ExcelSource
    source = ExcelSource(folder=str(trace.DATA))
    expected = trace._from_raw(source.get_dsr(), source.get_rbs(), lob=None, entity=None, placement=None)
    for key, metric in METRICS.items():
        if not metric.traced:
            continue
        section, name = key.split(".")
        if section == "underwriters":
            name = "margin" if name == "uw_margin_pct" else name
            assert f"underwriters.{name}_by_name" in expected, key
        elif key in MIXES:
            assert f"{key}_by_value" in expected, key
        else:
            assert key in expected, key
