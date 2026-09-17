"""Reads DSR and RBS straight from the Excel exports.

This is our only data source today. It exists purely so the rest of the
pipeline has something real to run against before Redshift access is ready -
see redshift_source.py for the planned replacement.
"""
import pandas as pd

from .base import DataSource


class ExcelSource(DataSource):
    """Loads DSR.xlsx and RBS.xlsx from a given folder, sheet 'Export' in each."""

    def __init__(self, folder: str):
        """Store the folder that holds DSR.xlsx and RBS.xlsx."""
        self.folder = folder

    def get_dsr(self) -> pd.DataFrame:
        """Read the DSR export as-is, no cleaning applied yet."""
        return pd.read_excel(f"{self.folder}/DSR.xlsx", sheet_name="Export")

    def get_rbs(self) -> pd.DataFrame:
        """Read the RBS export as-is, no cleaning applied yet."""
        return pd.read_excel(f"{self.folder}/RBS.xlsx", sheet_name="Export")
