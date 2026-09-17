"""Checks that reconcile() always keeps RBS's figure, and handles a zero
RBS value without inventing a misleading percentage.
"""
from reconcile.cross_check import reconcile


def test_close_match_is_not_flagged():
    """A small, expected gap between DSR and RBS should not be flagged."""
    result = reconcile(dsr_value=100.0, rbs_value=99.0)
    assert result.flagged is False
    assert result.kept_value == 99.0


def test_rbs_value_is_always_kept():
    """Even with a large gap, the kept value must equal RBS's figure."""
    result = reconcile(dsr_value=1000.0, rbs_value=10.0)
    assert result.kept_value == 10.0
    assert result.flagged is True


def test_large_gap_is_flagged():
    """A gap past the tolerance in settings.py should set flagged=True."""
    result = reconcile(dsr_value=105.0, rbs_value=100.0)  # 5% gap
    assert result.flagged is True  # tolerance is 2%


def test_zero_rbs_value_is_undefined_not_100_percent():
    """RBS=0 with a nonzero DSR must not be reported as a false 100% gap."""
    result = reconcile(dsr_value=500.0, rbs_value=0.0)
    assert result.gap_pct is None
    assert result.is_undefined_gap is True
    assert result.flagged is True
    assert result.kept_value == 0.0


def test_both_zero_is_a_clean_match():
    """Both sources agreeing on zero is a real match, not an edge case to flag."""
    result = reconcile(dsr_value=0.0, rbs_value=0.0)
    assert result.gap_pct == 0.0
    assert result.flagged is False
