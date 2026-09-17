"""Turns the dashboard's filter bar (the page address, e.g.
/?tf=ttm&bt=New&lob=Cyber) into a Scope, and back again.

The filter bar is a plain HTML form, so every choice lives in the address:
a filtered view can be bookmarked or pasted to someone and opens exactly as
it was. Each filter, what it does and why, is listed in the metrics
workbook, tab 7.

Query parameters:
    tf     timeframe: "ytd" (months picked on the month bar) or "ttm"
           (the twelve months ending with the last complete month)
    year   the year being looked at; compared against the year before
    m      months, repeated (m=1&m=2...). Ignored under ttm
    bt     business type: New / Renewal (blank = all)
    mop    placement: Open Market / Facility/DUA / Agreement (blank = all)
    basis  date basis: inception / submission
    lob, ent, uw   line of business, entity, underwriter (blank = all)
"""
from dataclasses import dataclass, field
from urllib.parse import urlencode

from config.settings import (DEFAULT_TIMEFRAME, DEFAULT_BUSINESS_TYPE, DEFAULT_PLACEMENT,
                             DEFAULT_DATE_BASIS)
from scope.filter import Scope, INCEPTION, SUBMISSION
from scope.period import last_complete_month


@dataclass
class FilterState:
    """Exactly what the filter bar shows. Blank strings mean "All"."""
    tf: str
    year: int
    months: list
    bt: str = ""
    mop: str = ""
    basis: str = INCEPTION
    lob: str = ""
    ent: str = ""
    uw: str = ""
    cleared: list = field(default_factory=list)  # selections dropped as no longer valid

    def to_scope(self, as_at) -> Scope:
        """The Scope these choices describe."""
        _, last_month = last_complete_month(as_at)
        return Scope(
            year=self.year,
            months=None if self.tf == "ttm" else list(self.months),
            ttm_end_month=last_month if self.tf == "ttm" else None,
            business_type=self.bt or None,
            placement=self.mop or None,
            date_basis=self.basis,
            line_of_business=self.lob or None,
            entity=self.ent or None,
            underwriter=self.uw or None,
        )

    def query(self, **changes) -> str:
        """The page address for these choices, with any changes applied."""
        values = {k: getattr(self, k) for k in ("tf", "year", "months", "bt", "mop",
                                                 "basis", "lob", "ent", "uw")}
        values.update(changes)
        params = [(k, v) for k, v in values.items() if k != "months" and v not in ("", None)]
        if values["tf"] != "ttm":
            params += [("m", m) for m in values["months"]]
        return "?" + urlencode(params)


def default_state(as_at) -> FilterState:
    """What the page opens on and what Reset goes back to (config/settings.py)."""
    year, last_month = last_complete_month(as_at)
    return FilterState(tf=DEFAULT_TIMEFRAME, year=year, months=list(range(1, last_month + 1)),
                       bt=DEFAULT_BUSINESS_TYPE or "", mop=DEFAULT_PLACEMENT or "",
                       basis=DEFAULT_DATE_BASIS)


def _pick(value, allowed, fallback):
    """Keep a value only if it's one of the allowed choices."""
    return value if value in allowed else fallback


def parse_filters(params, as_at, years, business_types, placements) -> FilterState:
    """Read the filter choices from the page address, falling back to defaults.

    params is anything with .get(name) and .getlist(name) (Starlette's
    QueryParams). Anything unrecognised - a typo'd year, a month of 13 - is
    ignored rather than trusted, so a bad link can't produce a wrong page.
    """
    state = default_state(as_at)
    if not params:
        return state

    state.tf = _pick(params.get("tf"), ("ytd", "ttm"), state.tf)
    try:
        year = int(params.get("year", state.year))
        state.year = year if year in years else state.year
    except ValueError:
        pass
    months = sorted({int(m) for m in params.getlist("m") if m.isdigit() and 1 <= int(m) <= 12})
    if months:
        state.months = months
    state.bt = _pick(params.get("bt", state.bt), [""] + list(business_types), state.bt)
    state.mop = _pick(params.get("mop", state.mop), [""] + list(placements), state.mop)
    state.basis = _pick(params.get("basis"), (INCEPTION, SUBMISSION), state.basis)
    state.lob = params.get("lob", "")
    state.ent = params.get("ent", "")
    state.uw = params.get("uw", "")
    return state


def drop_stranded_selections(state: FilterState, options_for) -> tuple:
    """Clear a dropdown choice the other filters have made impossible.

    E.g. picking an entity an underwriter never wrote for: rather than
    showing an empty page, the underwriter choice is cleared and the page
    says so. Same behaviour as Matt's build.

    The narrowest choice goes first (underwriter, then entity, then line of
    business), and the lists are worked out again after each clear - so
    changing Entity drops a stranded underwriter without also throwing away
    the entity that was just picked.

    options_for(state) returns the dropdown lists for a FilterState.
    Returns (state, the final dropdown lists).
    """
    options = options_for(state)
    for attr, field_name in (("uw", "underwriter"), ("ent", "entity"),
                             ("lob", "line_of_business")):
        value = getattr(state, attr)
        if value and value not in options[field_name]:
            setattr(state, attr, "")
            state.cleared.append(value)
            options = options_for(state)
    return state, options
