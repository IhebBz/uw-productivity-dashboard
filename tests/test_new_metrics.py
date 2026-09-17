"""Checks the metrics added to finish tab 4 and tab 5 of the workbook, on the
shared sample in tests/sample_data.py. Every expected figure is worked out
by hand in the test's docstring.
"""
import pytest

from metrics import premium, quality, composition
from scope.filter import Scope
from tests.sample_data import dsr_rows, rbs_rows

YTD_2026 = Scope(year=2026, months=list(range(1, 9)))


def test_average_deal_size():
    """Premium 60+40+300 = 400 over 2 distinct policies (P1, P4) = 200."""
    assert premium.average_deal_size(rbs_rows(), YTD_2026) == pytest.approx(200.0)
    assert premium.average_deal_size(rbs_rows(), Scope(year=2030)) is None


def test_bound_premium_from_dsr_counts_bound_statuses_only():
    """DSR 2026 bound rows: P1 100 + P4 300. P2 (Quote NTU) and P3 (Declined) don't count."""
    assert premium.bound_premium_from_dsr(dsr_rows(), YTD_2026) == pytest.approx(400.0)


def test_attachment_points():
    """Excess: only P1's excess line, 10M. Primary: deductibles blank (=0) and 2,000 -> median 1,000."""
    rbs = rbs_rows()
    assert quality.attachment_point_excess(rbs, YTD_2026) == pytest.approx(10_000_000)
    assert quality.attachment_point_primary(rbs, YTD_2026) == pytest.approx(1000)


def test_median_limit():
    """Exposures 5M, 3M, 9M -> median 5M (not the 5.67M average)."""
    assert quality.median_limit(rbs_rows(), YTD_2026) == pytest.approx(5_000_000)


def test_rate_adequacy_rbs_benchmark():
    """1609 premium 30+40+150 = 220 over 1609 benchmark 25+30+100 = 155."""
    assert quality.rate_adequacy_rbs_benchmark(rbs_rows(), YTD_2026) == pytest.approx(100 * 220 / 155)


def test_average_agency_share_is_premium_weighted():
    """(50x60 + 100x40 + 20x300) / 400 = 32.5 - a plain average would say 56.7."""
    assert composition.average_agency_share(rbs_rows(), YTD_2026) == pytest.approx(32.5)


def test_scm_share():
    """1 - 220 (Mosaic 1609 premium) / 400 (all premium) = 0.45."""
    assert composition.scm_share(rbs_rows(), YTD_2026) == pytest.approx(0.45)


def test_broker_concentration():
    """Aon 300 of 400 is the top broker; top 5 covers everything."""
    rbs = rbs_rows()
    assert composition.broker_concentration(rbs, YTD_2026, top_n=1) == pytest.approx(0.75)
    assert composition.broker_concentration(rbs, YTD_2026) == pytest.approx(1.0)


def test_average_policy_length_counts_each_policy_once():
    """P1 (12 months, two lines) and P4 (24 months) -> 18, not the per-line 16."""
    assert composition.average_policy_length(rbs_rows(), YTD_2026) == pytest.approx(18.0)


def test_renewal_premium_growth_is_renewals_only():
    """P4: 300 renewal premium on 250 expiring = 1.2, even with the New filter on."""
    rbs = rbs_rows()
    assert composition.renewal_premium_growth(rbs, YTD_2026) == pytest.approx(1.2)
    new_only = Scope(year=2026, months=list(range(1, 9)), business_type="New")
    assert composition.renewal_premium_growth(rbs, new_only) == pytest.approx(1.2)


def test_missing_optional_column_gives_blank_not_error():
    """An extract without Broker Name blanks Broker Concentration, nothing else."""
    rbs = rbs_rows()
    rbs["broker"] = None
    assert composition.broker_concentration(rbs, YTD_2026) is None
