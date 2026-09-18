"""Checks the reading aids on the page: what drove the change, thin-data flags,
the incomplete-months warning and the reconciliation badge cards.
"""
import pandas as pd
import pytest
from starlette.datastructures import QueryParams

import server.app as app
from metrics.drivers import describe, productivity_drivers
from reconcile.cross_check import reconcile
from scope.filter import Scope
from server.insights import incomplete_period_notice, reconciliation_cards, thin_data
from tests.sample_data import prepared

AS_AT = pd.Timestamp("2026-09-15")


def _result(subs, quotes, binds, premium, heads):
    return {"funnel": {"submissions": subs, "quotes": quotes, "binds": binds},
            "premium": {"bound_premium": premium},
            "productivity_stand_in": {"active_underwriters_stand_in": heads}}


def test_drivers_multiply_back_and_shares_add_up():
    """Four drivers multiply to premium per underwriter; their shares add to the total move."""
    prior = _result(subs=200, quotes=100, binds=50, premium=5_000_000, heads=10)   # $500k per UW
    current = _result(subs=330, quotes=150, binds=60, premium=6_600_000, heads=12)  # $550k per UW
    d = productivity_drivers(current, prior)
    assert d["prior"] == pytest.approx(500_000) and d["current"] == pytest.approx(550_000)
    assert d["total_change"] == pytest.approx(0.10)
    by_key = {r["key"]: r for r in d["rows"]}
    assert by_key["submissions_per_underwriter"]["change"] == pytest.approx(27.5 / 20 - 1)
    assert by_key["quote_rate"]["change"] == pytest.approx((150 / 330) / 0.5 - 1)
    assert by_key["bind_rate"]["change"] == pytest.approx(0.4 / 0.5 - 1)
    assert by_key["average_deal_size"]["change"] == pytest.approx(110_000 / 100_000 - 1)
    assert sum(r["contribution"] for r in d["rows"]) == pytest.approx(d["total_change"])
    product = 1
    for r in d["rows"]:
        product *= 1 + r["change"]
    assert product == pytest.approx(1 + d["total_change"])


def test_drivers_need_both_years_and_no_zeros():
    good = _result(10, 5, 2, 100.0, 1)
    assert productivity_drivers(good, None) is None
    assert productivity_drivers(good, _result(10, 5, 0, 0.0, 1)) is None


def test_describe_names_the_biggest_drag_and_lift():
    prior = _result(subs=200, quotes=100, binds=50, premium=5_000_000, heads=10)
    current = _result(subs=330, quotes=150, binds=60, premium=6_600_000, heads=12)
    text = describe(productivity_drivers(current, prior))
    assert text.startswith("Premium per active underwriter rose 10.0%.")
    assert "Biggest drag: Win rate (B/Q) -20.0% - winning less of what we priced." in text
    assert "Biggest lift: Submissions per underwriter +37.5%" in text


def test_thin_data_flags_rates_on_few_policies():
    result = {"funnel": {"submissions": 5, "quotes": 40, "binds": 25},
              "productivity_stand_in": {"active_underwriters_stand_in": 1}}
    assert thin_data(result, "funnel.quote_rate") == (5, "submissions", 20)
    assert thin_data(result, "funnel.bind_rate") is None           # 40 quotes is enough
    assert thin_data(result, "quality.uw_margin_pct") is None       # 25 binds is enough
    assert thin_data(result, "funnel.submissions") is None          # a count is never "thin"
    # One underwriter: per-person figures are flagged even with plenty of binds.
    per_person = thin_data(result, "productivity_stand_in.premium_per_active_underwriter")
    assert per_person == (1, "underwriters", 5)


@pytest.mark.parametrize("scope, warned", [
    (Scope(year=2026, months=list(range(1, 13))), "Sep–Dec 2026 aren't complete yet"),
    (Scope(year=2026, months=[7, 8, 9]), "Sep 2026 isn't complete yet"),
    (Scope(year=2026, months=list(range(1, 9))), ""),                # this year so far: fine
    (Scope(year=2025, months=list(range(1, 13))), ""),               # a past year: fine
    (Scope(year=2026, ttm_end_month=8), ""),                         # last 12 months: fine
])
def test_incomplete_months_warning(scope, warned):
    notice = incomplete_period_notice(scope, AS_AT, "Jan–Dec 2025")
    if warned:
        assert warned in notice
    else:
        assert notice == ""


def test_reconciliation_card_shows_both_figures_only_when_flagged():
    flagged = {"premium": {"reconciliation": reconcile(dsr_value=90.0, rbs_value=100.0)},
               "funnel": {"binds_reconciliation": reconcile(dsr_value=100.0, rbs_value=100.0)}}
    cards = reconciliation_cards(flagged)
    assert set(cards) == {"recon-premium"}
    assert "RBS says" in cards["recon-premium"] and "10.0%" in cards["recon-premium"]


def test_page_shows_drivers_guide_and_thin_flags():
    """On the tiny sample (2 binds) every RBS rate is thin, so the flags must show."""
    app._latest.update(data=prepared(), error=None, views={}, last_run="now")
    html = app.render_dashboard(app._view_for(QueryParams("")), "now", None)
    assert "What drove Premium / Active Underwriter" in html
    assert 'data-help="guide"' in html and 'id="help-guide"' in html
    assert "few binds" in html
    full_year = app.render_dashboard(app._view_for(QueryParams("period=full")), "now", None)
    assert "aren't complete yet" in full_year
