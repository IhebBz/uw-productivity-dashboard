"""A tiny, hand-built pair of already-cleaned DSR and RBS tables, shared by
the tests that need both reports at once. Small enough that every expected
answer in the tests can be worked out by hand.
"""
import pandas as pd

from ingest.underwriter_names import display_names
from pipeline.build_dashboard_data import PreparedData


def dsr_rows():
    """Six submissions across 2025 and 2026, two underwriters."""
    rows = [
        # policy, status, underwriter, entity, lob, business type, placement, premium, inception, submission
        ("P1", "Bound", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 100.0, "2026-02-01", "2025-12-15"),
        ("P2", "Quote NTU", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 0.0, "2026-03-01", "2026-02-10"),
        ("P3", "Declined", "Lee, Bob", "Mosaic US", "Political Risk", "Renewal", "Open Market", 0.0, "2026-03-01", "2026-02-20"),
        ("P4", "Bound", "Lee, Bob", "Mosaic US", "Political Risk", "Renewal", "Facility/DUA", 300.0, "2026-04-01", "2026-03-01"),
        ("P5", "Bound", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 80.0, "2025-02-01", "2025-01-10"),
        ("P6", "Declined", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 0.0, "2025-03-01", "2025-02-10"),
    ]
    df = pd.DataFrame(rows, columns=[
        "policy_reference", "status", "underwriter_raw", "entity", "line_of_business",
        "business_type", "placement", "premium", "inception_date", "submission_date"])
    df["underwriter"] = df["underwriter_raw"].str.lower().str.replace(",", "")
    df["inception_date"] = pd.to_datetime(df["inception_date"])
    df["submission_date"] = pd.to_datetime(df["submission_date"])
    return df


def rbs_rows():
    """The bound policies from dsr_rows, with P1 on two lines."""
    rows = [
        # policy, underwriter, entity, lob, business type, placement, premium, inception,
        # gelr, commission, plan LR, layer, slip lead, excess, deductible, exposure,
        # agency share, 1609 premium, 1609 benchmark, broker, tenor, rarc, expired premium
        ("P1", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 60.0, "2026-02-01",
         40.0, 20.0, 50.0, "Primary", "Mosaic 1609", 0.0, None, 5_000_000.0,
         50.0, 30.0, 25.0, "Marsh", 12.0, None, None),
        ("P1", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 40.0, "2026-02-01",
         40.0, 20.0, 50.0, "Excess", "Other Market", 10_000_000.0, 1000.0, 3_000_000.0,
         100.0, 40.0, 30.0, "Marsh", 12.0, None, None),
        ("P4", "Lee, Bob", "Mosaic US", "Political Risk", "Renewal", "Facility/DUA", 300.0, "2026-04-01",
         None, 10.0, 50.0, "Primary", "Mosaic US", 0.0, 2000.0, 9_000_000.0,
         20.0, 150.0, 100.0, "Aon", 24.0, 105.0, 250.0),
        ("P5", "Smith, Jane", "Mosaic UK", "Cyber", "New", "Open Market", 80.0, "2025-02-01",
         50.0, 15.0, 50.0, "Primary", "Mosaic 1609", 0.0, 500.0, 4_000_000.0,
         60.0, 40.0, 40.0, "Marsh", 12.0, None, None),
    ]
    df = pd.DataFrame(rows, columns=[
        "policy_reference", "underwriter_raw", "entity", "line_of_business", "business_type",
        "placement", "premium", "inception_date", "gelr", "commission", "plan_loss_ratio",
        "layer_type", "slip_lead", "excess", "deductible", "exposure", "agency_share",
        "mosaic_1609_premium", "mosaic_1609_benchmark", "broker", "tenor_months", "rarc",
        "expired_premium"])
    df["underwriter"] = df["underwriter_raw"].str.lower().str.replace(",", "")
    df["inception_date"] = pd.to_datetime(df["inception_date"])
    df["gelr_ok"] = df["gelr"].notna() & df["gelr"].ne(0)
    for column in ("gelr", "deductible", "rarc", "expired_premium"):
        df[column] = pd.to_numeric(df[column])
    return df


def prepared(as_at="2026-09-15"):
    """Both tables wrapped the way pipeline.prepare() hands them to the dashboard."""
    dsr, rbs = dsr_rows(), rbs_rows()
    return PreparedData(dsr=dsr, rbs=rbs, as_at=pd.Timestamp(as_at),
                        underwriter_names=display_names(dsr, rbs))
