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


def _first_and_last(key: str):
    """("rob", "stedman") from the matching key "stedman rob" (names arrive as "Last, First")."""
    parts = key.split()
    return (" ".join(parts[1:]), parts[0]) if len(parts) > 1 else ("", key)


def possible_duplicates(names: dict, similarity: float = 0.9) -> dict:
    """Pairs of underwriter names that are probably one person typed two ways.

    Tidying capitals and punctuation (normalise_underwriter_name) can't catch a
    genuinely different spelling (workbook tab 3, Rule 5). This flags likely
    cases for a person to check - it never merges anyone. Two names are flagged
    when either:
    - the surname matches and one first name starts the other
      ("Stedman, Rob" / "Stedman, Robert"), or
    - the whole names are at least `similarity` alike ("Hirst, Justin" /
      "Hurst, Justin").

    names: {matching key: display name}. Returns {key: [display names it may duplicate]}.
    """
    import difflib

    keys = sorted(names)
    found = {}
    for i, a in enumerate(keys):
        first_a, last_a = _first_and_last(a)
        for b in keys[i + 1:]:
            first_b, last_b = _first_and_last(b)
            prefix = (last_a == last_b and first_a and first_b
                      and (first_a.startswith(first_b) or first_b.startswith(first_a)))
            matcher = difflib.SequenceMatcher(None, a, b)
            alike = matcher.real_quick_ratio() >= similarity and matcher.ratio() >= similarity
            if prefix or alike:
                found.setdefault(a, []).append(names[b])
                found.setdefault(b, []).append(names[a])
    return found
