"""Checks the underwriter table (workbook tab 4, "LOOKING AT ONE
UNDERWRITER") gives the same figures as the whole-book functions run for one
underwriter - the table is a faster grouped version and must never drift.
"""
import dataclasses

import pytest

from metrics import funnel, quality, underwriters
from scope.filter import Scope
from tests.sample_data import dsr_rows, rbs_rows

YTD_2026 = Scope(year=2026, months=list(range(1, 9)))


def _row(table, key):
    return next(r for r in table["rows"] if r["underwriter"] == key)


@pytest.mark.parametrize("key", ["smith jane", "lee bob"])
def test_table_matches_whole_book_functions(key):
    """Every column equals the same metric computed with the Underwriter filter set."""
    dsr, rbs = dsr_rows(), rbs_rows()
    row = _row(underwriters.underwriter_table(dsr, rbs, YTD_2026), key)
    one = dataclasses.replace(YTD_2026, underwriter=key)
    assert row["submissions"] == funnel.submissions(dsr, one)
    assert row["quotes"] == funnel.quotes(dsr, one)
    assert row["quote_rate"] == funnel.quote_rate(dsr, one)
    assert row["binds"] == funnel.binds_from_rbs(rbs, one)
    assert row["bind_rate"] == funnel.bind_rate(dsr, rbs, one)
    assert row["premium"] == pytest.approx(rbs[rbs["underwriter"] == key].pipe(
        lambda f: f[f["inception_date"].dt.year == 2026]["premium"].sum()))
    expected_margin = quality.uw_margin_pct(rbs, one)
    if expected_margin is None:
        assert row["uw_margin_pct"] is None
    else:
        assert row["uw_margin_pct"] == pytest.approx(expected_margin)


def test_peer_comparison_against_median():
    """Premiums 100 (Jane) and 300 (Bob): median 200, so 0.5x and 1.5x. Biggest first."""
    table = underwriters.underwriter_table(dsr_rows(), rbs_rows(), YTD_2026)
    assert table["peer_median_premium"] == pytest.approx(200)
    assert [r["underwriter"] for r in table["rows"]] == ["lee bob", "smith jane"]
    assert _row(table, "smith jane")["premium_vs_peer_median"] == pytest.approx(0.5)
    assert _row(table, "lee bob")["premium_vs_peer_median"] == pytest.approx(1.5)


def test_submission_basis_leaves_rbs_columns_blank():
    """Without RBS (submission basis), binds, premium and margin are blank, not zero."""
    scope = dataclasses.replace(YTD_2026, date_basis="submission")
    row = _row(underwriters.underwriter_table(dsr_rows(), None, scope), "lee bob")
    assert row["submissions"] == 2
    assert row["binds"] is None and row["premium"] is None and row["uw_margin_pct"] is None
