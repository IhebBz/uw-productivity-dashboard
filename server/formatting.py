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

def fmt_amount(value) -> str:
    """Money that can be small (an attachment point, a deductible): $M from
    $1M up, per the brand guide, and $k below that so $29k doesn't read "$0.03M".
    """
    if value is None:
        return "\u2014"
    if abs(value) >= 1_000_000:
        return fmt_money(value)
    return f"${value / 1000:,.1f}k"


def fmt_months(value) -> str:
    """A length of time in months, one decimal."""
    if value is None:
        return "\u2014"
    return f"{value:.1f} mo"


def fmt_multiple(value) -> str:
    """A ratio shown as a multiple, e.g. 1.25x the peer median."""
    if value is None:
        return "\u2014"
    return f"{value:.2f}\u00d7"


FORMATTERS = {
    "money": fmt_money,
    "amount": fmt_amount,
    "int": fmt_int,
    "pct": fmt_pct,
    "ratio": fmt_ratio_pct,
    "months": fmt_months,
    "multiple": fmt_multiple,
}


def fmt_change(current, prior, kind: str) -> tuple:
    """The move from the prior period, as (text, direction of the move).

    Percentages and 0-1 ratios move in percentage points ("+1.2 pts");
    money, counts and lengths move in percent ("+4.2%"). Direction is
    "up", "down" or "flat", or None when there's nothing to compare.
    """
    if current is None or prior is None:
        return "\u2014", None
    if kind in ("pct", "ratio"):
        points = (current - prior) * (100 if kind == "ratio" else 1)
        text = f"{points:+.1f} pts"
        move = points
    else:
        if not prior:
            return "\u2014", None
        move = current / prior - 1
        text = f"{move * 100:+.1f}%"
    if round(move, 6) == 0:
        return text, "flat"
    return text, "up" if move > 0 else "down"
