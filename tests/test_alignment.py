"""Checks the tab 3 rules that make DSR and RBS agree: New/Renewal follows
RBS (Rule 2), entity names are cleaned the same way on both sides (Rule 2),
and underwriter names are matched after formatting clean-up (Rule 5).
"""
import pandas as pd

from config.field_map import normalise_entity
from ingest.align_reports import align_business_type
from ingest.underwriter_names import normalise_underwriter_name
from scope.filter import Scope, apply_scope


def test_dsr_business_type_follows_rbs_when_they_disagree():
    """A policy in both reports takes RBS's value; a DSR-only policy keeps its own."""
    dsr = pd.DataFrame({
        "policy_reference": ["P1", "P2"],
        "business_type": ["New", "New"],
    })
    rbs = pd.DataFrame({
        "policy_reference": ["P1", "P1", "P1"],
        "business_type": ["Renewal", "Renewal", "New"],  # most common wins
    })
    aligned = align_business_type(dsr, rbs)
    assert aligned["business_type"].tolist() == ["Renewal", "New"]


def test_business_type_tie_goes_to_the_value_that_sorts_first():
    """One New line and one Renewal line on the same RBS policy -> New."""
    dsr = pd.DataFrame({"policy_reference": ["P1"], "business_type": ["Renewal"]})
    rbs = pd.DataFrame({"policy_reference": ["P1", "P1"], "business_type": ["Renewal", "New"]})
    assert align_business_type(dsr, rbs)["business_type"].tolist() == ["New"]


def test_entity_alias_maps_dsr_spelling_onto_rbs():
    """DSR's longer entity names match RBS's after clean-up."""
    assert normalise_entity("Mosaic Syndicate 2610") == "Mosaic 2610"
    assert normalise_entity("Mosaic Syndicate 5431 (EEA)") == "Mosaic 5431"
    assert normalise_entity("  Mosaic   UK ") == "Mosaic UK"
    assert normalise_entity(None) is None


def test_underwriter_names_match_despite_formatting():
    """Capitals, punctuation and extra spaces don't split one person in two."""
    assert normalise_underwriter_name("Jane  O'NEIL") == normalise_underwriter_name("jane o neil")
    assert normalise_underwriter_name(None) is None
    assert normalise_underwriter_name("  ") is None


def test_scope_filters_apply_the_same_clean_up():
    """Filtering by a raw spelling still finds the cleaned-up rows."""
    df = pd.DataFrame({
        "inception_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        "entity": ["Mosaic 2610", "Mosaic UK"],
        "underwriter": ["jane smith", "bob lee"],
    })
    assert len(apply_scope(df, Scope(entity="Mosaic Syndicate 2610"))) == 1
    assert len(apply_scope(df, Scope(underwriter="Jane SMITH"))) == 1
