"""Traces every dashboard figure back to the raw DSR and RBS columns.

Each figure is worked out a second time here, straight from the raw export
columns (their real names, e.g. "Agency Share Gross Written Premium (USD)"),
with plain pandas and WITHOUT using anything in ingest/, scope/ or metrics/.
Then it's compared with what the dashboard shows. If the two ever differ,
either the code or its documented definition has drifted.

This file is the written-out lineage: the column names and row rules below
are the same ones listed in the metrics workbook, tab 10 ("Metric lineage").
Change one, change the other.

Needs the real extracts in data/. Skipped when they aren't there.
"""
import pathlib
import re

import pandas as pd
import pytest

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
pytestmark = pytest.mark.skipif(not (DATA / "DSR.xlsx").exists() or not (DATA / "RBS.xlsx").exists(),
                                reason="real DSR.xlsx / RBS.xlsx not in data/")

# The two views checked: the dashboard's default, and a narrow slice.
VIEWS = {
    "Jan-Aug 2026, no filters": dict(lob=None, entity=None, placement=None),
    "Jan-Aug 2026, Cyber, Mosaic UK, Open Market": dict(lob="Cyber", entity="Mosaic UK",
                                                        placement="Open Market"),
}
YEAR, MONTHS = 2026, range(1, 9)

# DSR "XFI Policy Status" values, written out (workbook tab 10).
QUOTED = {"Bound", "Cancelled", "Firm Order Noted", "Live Policy", "Non Renewed", "Quote",
          "Quote NTU", "Renewed"}
BOUND = {"Bound", "Cancelled", "Firm Order Noted", "Live Policy", "Non Renewed", "Renewed"}
ENTITY_ALIASES = {"Mosaic Syndicate 2610": "Mosaic 2610", "Mosaic Syndicate 5431 (EEA)": "Mosaic 5431"}


def _name(value):
    """Underwriter matching key: lower case, punctuation to spaces, single spaces."""
    if pd.isna(value):
        return None
    return " ".join(re.sub(r"[^\w\s]", " ", str(value).lower()).split()) or None


def _wavg(values, weights):
    total = weights.sum()
    return (values * weights).sum() / total if total else None


@pytest.fixture(scope="module")
def raw():
    from data_sources.excel_source import ExcelSource  # only reads the files, no cleaning
    source = ExcelSource(folder=str(DATA))
    return source.get_dsr(), source.get_rbs()


@pytest.fixture(scope="module")
def dashboard():
    from data_sources.excel_source import ExcelSource
    from pipeline.build_dashboard_data import prepare
    return prepare(ExcelSource(folder=str(DATA)))


def _dsr_view(dsr, lob, entity, placement):
    inception = pd.to_datetime(dsr["Inception date"], errors="coerce")
    keep = (inception.dt.year == YEAR) & inception.dt.month.isin(MONTHS)
    ent = dsr["Producing Mosaic Entity"].map(
        lambda e: ENTITY_ALIASES.get(" ".join(str(e).split()), " ".join(str(e).split())) if pd.notna(e) else None)
    if lob:
        keep &= dsr["Class Of Business"] == lob
    if entity:
        keep &= ent == entity
    if placement:
        keep &= dsr["Mapped Method of Placement (MOP)"] == placement
    f = dsr[keep].copy()
    f["premium"] = pd.to_numeric(f["Agency Share Gross Written Premium (USD)"], errors="coerce").fillna(0)
    f["uw"] = f["Producing Underwriter Name"].fillna(f["Underwriter Name"]).map(_name)
    return f


def _rbs_view(rbs, lob, entity, placement, renewal_only=False):
    inception = pd.to_datetime(rbs["Inception Date"], errors="coerce")
    keep = (inception.dt.year == YEAR) & inception.dt.month.isin(MONTHS)
    if lob:
        keep &= rbs["Class of Business"] == lob
    if entity:
        keep &= rbs["Producing Mosaic Entity"].map(lambda e: " ".join(str(e).split())) == entity
    if placement:
        keep &= rbs["Mapped Method of Placement (MOP)"] == placement
    if renewal_only:
        keep &= rbs["Renewal Status"] == "Renewal"
    f = rbs[keep].copy()
    num = lambda col: pd.to_numeric(f[col], errors="coerce")
    # Percent columns arrive as fractions (0.40) in this extract; shown in percent units (40.0).
    assert pd.to_numeric(rbs["Agency GELR (%)"], errors="coerce").quantile(0.99) <= 3
    f["premium"] = num("Agency Share Gross Written Premium (USD)").fillna(0)
    f["gelr"] = num("Agency GELR (%)") * 100
    f["usable"] = f["gelr"].notna() & f["gelr"].ne(0)
    f["commission"] = (num("Original Commission (%)") * 100).fillna(0)
    f["plan"] = num("Business Plan Loss Ratio (%)") * 100
    f["uw"] = f["Producing Underwriter Name"].fillna(f["Underwriter Name"]).map(_name)
    return f


def _from_raw(dsr, rbs, lob, entity, placement):
    """Every figure, from raw columns only."""
    d = _dsr_view(dsr, lob, entity, placement)
    r = _rbs_view(rbs, lob, entity, placement)
    ren = _rbs_view(rbs, lob, entity, placement, renewal_only=True)
    out = {}

    subs = d["Policy Reference"].nunique()
    quotes = d.loc[d["XFI Policy Status"].isin(QUOTED), "Policy Reference"].nunique()
    binds = r["Policy Reference"].nunique()
    premium = r["premium"].sum()
    out["funnel.submissions"] = subs
    out["funnel.quotes"] = quotes
    out["funnel.binds"] = binds
    out["funnel.quote_rate"] = quotes / subs if subs else None
    out["funnel.bind_rate"] = binds / quotes if quotes else None
    out["funnel.end_to_end_win_rate"] = binds / subs if subs else None
    out["premium.bound_premium"] = premium
    out["premium.average_deal_size"] = premium / binds if binds else None
    out["premium.reconciliation.dsr_value"] = d.loc[d["XFI Policy Status"].isin(BOUND), "premium"].sum()

    u = r[r["usable"]]
    gelr_m = _wavg(u["gelr"], u["premium"])
    comm_m = _wavg(u["commission"], u["premium"])
    out["quality.gelr_book_basis"] = _wavg(r["gelr"].fillna(0), r["premium"])
    out["quality.gelr_margin_basis"] = gelr_m
    out["quality.commission_book_basis"] = _wavg(r["commission"], r["premium"])
    out["quality.commission_margin_basis"] = comm_m
    out["quality.uw_margin_pct"] = 100 - gelr_m - comm_m
    out["quality.margin_cover"] = u["premium"].sum() / premium
    out["quality.commission_cover"] = u.loc[u["commission"] > 0, "premium"].sum() / u["premium"].sum()
    out["quality.attachment_point_excess"] = pd.to_numeric(
        r.loc[r["Type of Layer"] == "Excess", "Excess (USD)"], errors="coerce").dropna().median()
    out["quality.attachment_point_primary"] = pd.to_numeric(
        r.loc[r["Type of Layer"] == "Primary", "Deductible (USD)"], errors="coerce").fillna(0).median()
    out["quality.median_limit"] = pd.to_numeric(r["Agency Exposure (USD)"], errors="coerce").dropna().median()

    ra = r[r["usable"] & r["plan"].gt(0)]
    out["pricing.rate_adequacy"] = 100 * ra["premium"].sum() / (ra["premium"] * ra["gelr"] / ra["plan"]).sum()
    bench = pd.to_numeric(r["Mosaic 1609 Share Benchmark Premium (USD)"], errors="coerce")
    p1609 = pd.to_numeric(r["Mosaic 1609 Share Gross Written Premium (USD)"], errors="coerce")
    out["pricing.rate_adequacy_rbs_benchmark"] = 100 * p1609[bench > 0].sum() / bench[bench > 0].sum()
    rarc = pd.to_numeric(ren["Risk Adjusted Rate Change (%)"], errors="coerce") * 100
    expired = pd.to_numeric(ren["Expired Gross Premium Agency (USD) of previous policy"], errors="coerce")
    ok = expired.notna() & expired.ne(0) & rarc.notna()
    out["pricing.rarc"] = _wavg(rarc[ok], expired[ok])

    out["composition.mosaic_as_lead"] = r["Slip Lead"].astype(str).str.contains("Mosaic", case=False).mean()
    out["composition.primary_share"] = (r["Type of Layer"] == "Primary").mean()
    share = pd.to_numeric(r["Agency Line/Share (%)"], errors="coerce") * 100
    out["composition.average_agency_share"] = _wavg(share[share.notna()], r.loc[share.notna(), "premium"])
    out["composition.scm_share"] = 1 - p1609.sum() / premium
    out["composition.broker_concentration"] = (
        r.groupby("Broker Name")["premium"].sum().nlargest(5).sum() / premium)
    tenor = r.assign(t=pd.to_numeric(r["Tenor in Months"], errors="coerce")).dropna(subset=["t"])
    out["composition.average_policy_length"] = tenor.groupby("Policy Reference")["t"].first().mean()
    grows = ren.assign(e=expired)
    grows = grows[grows["e"] > 0]
    out["composition.renewal_premium_growth"] = grows["premium"].sum() / grows["e"].sum()

    active, roster = r["uw"].dropna().nunique(), d["uw"].dropna().nunique()
    out["productivity_stand_in.active_underwriters_stand_in"] = active
    out["productivity_stand_in.roster_underwriters_stand_in"] = roster
    out["productivity_stand_in.premium_per_active_underwriter"] = premium / active
    out["productivity_stand_in.premium_per_roster_underwriter"] = premium / roster
    out["productivity_stand_in.uw_margin_per_active_underwriter"] = premium * (100 - gelr_m - comm_m) / 100 / active

    for label, column in (("new_vs_renewal_mix", "Renewal Status"),
                          ("placement_mix", "Mapped Method of Placement (MOP)")):
        shares = r.groupby(r[column].fillna("(blank)"))["premium"].sum() / premium
        out[f"composition.{label}_by_value"] = shares.to_dict()

    by_uw = r.dropna(subset=["uw"]).groupby("uw")["premium"].sum()
    mu = u.dropna(subset=["uw"]).assign(g=lambda x: x["gelr"] * x["premium"],
                                        c=lambda x: x["commission"] * x["premium"])
    mu = mu.groupby("uw")[["premium", "g", "c"]].sum()
    mu = mu[mu["premium"] != 0]
    out["underwriters.margin_by_name"] = (100 - mu["g"] / mu["premium"] - mu["c"] / mu["premium"]).to_dict()
    out["underwriters.peer_median_premium"] = by_uw[by_uw > 0].median()
    median = by_uw[by_uw > 0].median()
    out["underwriters.premium_by_name"] = by_uw.to_dict()
    out["underwriters.premium_vs_peer_median_by_name"] = (by_uw / median).to_dict()
    named_dsr = d.dropna(subset=["uw"])
    subs_uw = named_dsr.groupby("uw")["Policy Reference"].nunique()
    quotes_uw = named_dsr[named_dsr["XFI Policy Status"].isin(QUOTED)].groupby("uw")["Policy Reference"].nunique()
    binds_uw = r.dropna(subset=["uw"]).groupby("uw")["Policy Reference"].nunique()
    out["underwriters.submissions_by_name"] = subs_uw.to_dict()
    out["underwriters.quotes_by_name"] = quotes_uw.to_dict()
    out["underwriters.quote_rate_by_name"] = (quotes_uw.reindex(subs_uw.index, fill_value=0) / subs_uw).to_dict()
    out["underwriters.binds_by_name"] = binds_uw.to_dict()
    out["underwriters.bind_rate_by_name"] = (binds_uw / quotes_uw).dropna().to_dict()
    return out


def _dashboard_value(result, path):
    node = result
    for part in path.split("."):
        node = node[part] if isinstance(node, dict) else getattr(node, part)
    return node


@pytest.mark.parametrize("view", list(VIEWS))
def test_every_figure_matches_the_raw_columns(raw, dashboard, view):
    from pipeline.build_dashboard_data import compute
    from scope.filter import Scope

    f = VIEWS[view]
    scope = Scope(year=YEAR, months=list(MONTHS), line_of_business=f["lob"], entity=f["entity"],
                  placement=f["placement"])
    shown = compute(dashboard, scope)
    expected = _from_raw(*raw, **f)

    mismatches = []
    for path, want in expected.items():
        if path.endswith(("_by_name", "_by_value")):
            continue
        got = _dashboard_value(shown, path)
        if not (got == pytest.approx(want, rel=1e-9, abs=1e-9)):
            mismatches.append(f"{path}: dashboard {got!r}, raw columns {want!r}")

    # Every underwriter table column, for every underwriter.
    table = {row["underwriter"]: row for row in shown["underwriters"]["rows"]}
    checked = 0
    for column in ("premium", "premium_vs_peer_median", "submissions", "quotes", "quote_rate",
                   "binds", "bind_rate", "uw_margin_pct"):
        source = "margin" if column == "uw_margin_pct" else column
        for name, want in expected[f"underwriters.{source}_by_name"].items():
            got = table[name][column]
            checked += 1
            if got is None or got != pytest.approx(want, rel=1e-9, abs=1e-6):
                mismatches.append(f"underwriter {name} {column}: dashboard {got!r}, raw columns {want!r}")

    # Both premium mixes, every slice.
    for label in ("new_vs_renewal_mix", "placement_mix"):
        mix = shown["composition"][label]
        for value, want in expected[f"composition.{label}_by_value"].items():
            share = mix[value]["premium_share"] if isinstance(mix[value], dict) else mix[value]
            checked += 1
            if share != pytest.approx(want, rel=1e-9):
                mismatches.append(f"{label} {value}: dashboard {share!r}, raw columns {want!r}")

    assert checked >= 20, f"only {checked} per-underwriter / mix values compared - the check isn't running"
    assert not mismatches, "\n".join(mismatches)
