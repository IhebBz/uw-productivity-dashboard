"""The DSR <-> RBS field name translation table.

DSR and RBS often store the same idea under different column names (see the
metrics workbook, tab 3, Rule 2). Every lookup by concept - never by a raw
column string scattered through the codebase - goes through this map, so a
renamed source column is a one-line fix here, not a hunt through the project.
"""

FIELD_MAP = {
    "line_of_business": {"dsr": "Class Of Business", "rbs": "Class of Business"},
    "business_type": {"dsr": "Business Type", "rbs": "Renewal Status"},
    "placement": {"dsr": "Mapped Method of Placement (MOP)",
                  "rbs": "Mapped Method of Placement (MOP)"},
    "underwriter": {"dsr": "Producing Underwriter Name", "rbs": "Producing Underwriter Name"},
    "underwriter_fallback": {"dsr": "Underwriter Name", "rbs": "Underwriter Name"},
    "entity": {"dsr": "Producing Mosaic Entity", "rbs": "Producing Mosaic Entity"},
    "inception_date": {"dsr": "Inception date", "rbs": "Inception Date"},
    "submission_date": {"dsr": "Submission Date", "rbs": None},
    "premium": {"dsr": "Agency Share Gross Written Premium (USD)",
                "rbs": "Agency Share Gross Written Premium (USD)"},
    "status": {"dsr": "XFI Policy Status", "rbs": None},
    "policy_reference": {"dsr": "Policy Reference", "rbs": "Policy Reference"},
}


def column_for(concept: str, source: str) -> str:
    """Return the real column name for a concept, on a given source ('dsr' or 'rbs').

    Returns None where the source genuinely has no equivalent column (e.g.
    RBS has no submission date) - callers must handle that case explicitly.
    Raises a clear error for a typo'd or unknown concept/source, rather than
    a bare KeyError that doesn't say what went wrong.
    """
    if concept not in FIELD_MAP:
        raise KeyError(f"'{concept}' is not a known concept. Known: {sorted(FIELD_MAP)}")
    if source not in FIELD_MAP[concept]:
        raise KeyError(f"'{source}' is not a valid source for '{concept}'. Use 'dsr' or 'rbs'.")
    return FIELD_MAP[concept][source]
