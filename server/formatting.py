"""Number formatting exactly as Mosaic Dashboard Standards, section 6,
specifies. One place for this so a rule never has to be re-typed at each
call site - and so it's obvious where to fix it if the standard changes.
"""


def fmt_money(value) -> str:
    """$10M or more gets one decimal, under $10M gets two - per the brand guide."""
    if value is None:
        return "\u2014"
    millions = value / 1_000_000
    decimals = 1 if abs(millions) >= 10 else 2
    return f"${millions:,.{decimals}f}M"


def fmt_pct(value) -> str:
    """Percentages always get one decimal, per the brand guide."""
    if value is None:
        return "\u2014"
    return f"{value:.1f}%"


def fmt_int(value) -> str:
    """Plain counts, thousands-separated."""
    if value is None:
        return "\u2014"
    return f"{value:,.0f}"


def fmt_ratio_pct(value) -> str:
    """A 0-1 ratio (e.g. a win rate) shown as a one-decimal percentage."""
    if value is None:
        return "\u2014"
    return fmt_pct(value * 100)