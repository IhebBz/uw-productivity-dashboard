"""Cleans up obvious formatting differences in underwriter names so near
identical spellings match (capitals, punctuation, extra spaces).

This is a known partial fix, not a full one - see the metrics workbook, tab
3, Rule 5. Without the HR file's name-mapping table, a genuine spelling
variant (a name typed two different ways entirely) will still slip through
as two separate people. Worth a manual review once real data is in.
"""
import re

import pandas as pd

_PUNCTUATION = re.compile(r"[^\w\s]")


def normalise_underwriter_name(name):
    """Lower-case, strip punctuation and collapse extra spaces in a name.

    Returns None for a blank name, so a missing underwriter stays missing
    rather than becoming an empty-string "person".
    """
    if name is None or pd.isna(name):
        return None
    cleaned = " ".join(_PUNCTUATION.sub(" ", str(name).lower()).split())
    return cleaned or None


def display_names(*frames: pd.DataFrame) -> dict:
    """Map each cleaned-up underwriter name to the spelling shown on screen.

    Matching uses the cleaned-up name ("jane o neil"), which is right for
    counting but ugly to read. The spelling shown is whichever original
    spelling appears on the most rows across the reports given.
    """
    both = pd.concat([f[["underwriter", "underwriter_raw"]] for f in frames])
    both = both.dropna(subset=["underwriter"])
    counts = both.groupby(["underwriter", "underwriter_raw"]).size().rename("rows").reset_index()
    counts = counts.sort_values(["underwriter", "rows", "underwriter_raw"],
                                ascending=[True, False, True])
    top = counts.drop_duplicates("underwriter")
    return dict(zip(top["underwriter"], top["underwriter_raw"].astype(str).str.strip()))
