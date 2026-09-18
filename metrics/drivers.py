"""What drove the change in Premium per Active Underwriter, year on year.

Premium per underwriter splits exactly into four drivers multiplied together:

    Premium        Submissions     Quotes          Binds        Premium
    -----------  = -----------  x  -----------  x  --------  x  -------
    Underwriters   Underwriters    Submissions     Quotes       Binds

    (per person)   (flow)          (quote rate)    (win rate)   (deal size)

So a change in premium per underwriter is fully explained by the changes in
those four. Each driver's share of the total move is its log-change divided
by the total log-change: the shares always add back to the total exactly,
whichever order you look at them in.

This is the same split as the log-share bridge in Matt's build, but NOT the
waterfall his page draws: that one allocates by Shapley value over every
ordering of the drivers and carries a fifth margin term, so his on-screen
contributions won't match ours figure for figure (workbook tab 12).

Underwriters here is the Active underwriters stand-in (no HR file), so this
reads "per active underwriter", never "per head". See metrics/lineage.py
("drivers.premium_per_active_underwriter").
"""
import math

DRIVERS = [
    # (key, label, what it means when it went up, ... when it went down)
    ("submissions_per_underwriter", "Submissions per underwriter",
     "more business coming in per underwriter", "less business coming in per underwriter"),
    ("quote_rate", "Quote rate (Q/S)", "pricing more of what came in", "pricing less of what came in"),
    ("bind_rate", "Win rate (B/Q)", "winning more of what we priced", "winning less of what we priced"),
    ("average_deal_size", "Average deal size", "more premium per win", "less premium per win"),
]


def _flow_meaning(submissions_change, underwriters_change):
    """Why submissions-per-underwriter moved: the flow, the head count, or both.

    Without this the panel says "less business coming in per underwriter" when
    submissions actually ROSE and the stand-in head count rose faster - which
    is a different story, and the one the reader needs.
    """
    subs = f"submissions {submissions_change:+.1%}"
    heads = f"underwriters {underwriters_change:+.1%}"
    if submissions_change >= 0 and underwriters_change > submissions_change:
        return f"{subs}, but spread across more underwriters ({heads})"
    if submissions_change < 0 and underwriters_change <= 0:
        return f"less business coming in ({subs}), with fewer underwriters ({heads})"
    if submissions_change < 0:
        return f"less business coming in ({subs}) while underwriters grew ({heads})"
    if underwriters_change < 0:
        return f"{subs} across fewer underwriters ({heads})"
    return f"{subs} against {heads}"


def _factors(result):
    """The four drivers and the total, from one period's result. None if any can't be worked out."""
    f, p = result["funnel"], result["premium"]
    heads = result["productivity_stand_in"]["active_underwriters_stand_in"]
    subs, quotes, binds, premium = f["submissions"], f["quotes"], f["binds"], p["bound_premium"]
    if not all(v is not None and v > 0 for v in (heads, subs, quotes, binds, premium)):
        return None
    return {
        "submissions_per_underwriter": subs / heads,
        "quote_rate": quotes / subs,
        "bind_rate": binds / quotes,
        "average_deal_size": premium / binds,
        "total": premium / heads,
    }


def productivity_drivers(current: dict, prior: dict) -> dict:
    """Split the change in Premium per Active Underwriter into its four drivers.

    Returns None when the split can't be made: no prior period, or a zero in
    either period (e.g. no binds), since a ratio of zero has no meaningful
    percentage change. Otherwise:
        total_change      e.g. -0.093 for -9.3%
        rows              one per driver: prior, current, change (e.g. +0.043),
                          contribution (its share of total_change, same units;
                          the contributions add up to total_change)
    """
    if prior is None:
        return None
    now, was = _factors(current), _factors(prior)
    if now is None or was is None:
        return None

    total_change = now["total"] / was["total"] - 1
    total_log = math.log(now["total"] / was["total"])
    rows = []
    for key, label, if_up, if_down in DRIVERS:
        log_change = math.log(now[key] / was[key])
        rows.append({
            "key": key,
            "label": label,
            "meaning": if_up if now[key] >= was[key] else if_down,
            "prior": was[key],
            "current": now[key],
            "change": now[key] / was[key] - 1,
            # With no overall move there's nothing to share out.
            "contribution": log_change / total_log * total_change if total_log else 0.0,
        })
    # The first driver holds the head count in its denominator, so name both
    # sides of it rather than calling every fall "less business coming in".
    counts = {}
    for key, section, name in (("submissions", "funnel", "submissions"),
                               ("underwriters", "productivity_stand_in",
                                "active_underwriters_stand_in")):
        counts[key] = (prior[section][name], current[section][name])
    subs_change = counts["submissions"][1] / counts["submissions"][0] - 1
    heads_change = counts["underwriters"][1] / counts["underwriters"][0] - 1
    rows[0]["meaning"] = _flow_meaning(subs_change, heads_change)
    return {"prior": was["total"], "current": now["total"], "total_change": total_change,
            "rows": rows, "counts": counts,
            "changes": {"submissions": subs_change, "underwriters": heads_change}}


def describe(drivers: dict) -> str:
    """One plain-English sentence summing up what moved it most."""
    if not drivers:
        return ""
    move = drivers["total_change"]
    direction = "rose" if move > 0 else "fell" if move < 0 else "was flat"
    up = max(drivers["rows"], key=lambda r: r["contribution"])
    down = min(drivers["rows"], key=lambda r: r["contribution"])
    subs = drivers["counts"]["submissions"]
    heads = drivers["counts"]["underwriters"]
    parts = [f"Premium per active underwriter {direction} {abs(move) * 100:.1f}%.",
             f"Behind it: submissions {subs[0]:,} → {subs[1]:,} "
             f"({drivers['changes']['submissions'] * 100:+.1f}%) and active underwriters "
             f"{heads[0]:,} → {heads[1]:,} ({drivers['changes']['underwriters'] * 100:+.1f}%)."]
    if down["contribution"] < 0:
        parts.append(f"Biggest drag: {down['label']} {down['change'] * 100:+.1f}% - {down['meaning']}.")
    if up["contribution"] > 0:
        parts.append(f"Biggest lift: {up['label']} {up['change'] * 100:+.1f}% - {up['meaning']}.")
    return " ".join(parts)
