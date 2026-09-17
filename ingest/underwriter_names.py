"""Cleans up obvious formatting differences in underwriter names so near
identical spellings match (capitals, punctuation, extra spaces).

This is a known partial fix, not a full one - see the metrics workbook, tab
3, Rule 5. Without the HR file's name-mapping table, a genuine spelling
variant (a name typed two different ways entirely) will still slip through
as two separate people. Worth a manual review once real data is in.
"""


def normalise_underwriter_name(name: str) -> str:
    """Lower-case, strip punctuation and collapse extra spaces in a name."""
    raise NotImplementedError
