"""The planned replacement for ExcelSource, once the daily Redshift refresh
is available in prod.

Not implemented yet - this file exists now so the shape of the swap is clear
from day one. When it's built, everything else in the project (ingest,
reconcile, metrics, pipeline) needs zero changes, because they only ever
depend on the DataSource interface, not on this class directly.
"""
import pandas as pd

from .base import DataSource


class RedshiftSource(DataSource):
    """Reads the Redshift tables that mirror DSR and RBS, refreshed daily."""

    def __init__(self, connection_string: str, dsr_table: str, rbs_table: str):
        """Store the connection details and the two table names to query."""
        self.connection_string = connection_string
        self.dsr_table = dsr_table
        self.rbs_table = rbs_table

    def get_dsr(self) -> pd.DataFrame:
        """Query the Redshift table that mirrors the DSR export."""
        raise NotImplementedError("Redshift access not set up yet.")

    def get_rbs(self) -> pd.DataFrame:
        """Query the Redshift table that mirrors the RBS export."""
        raise NotImplementedError("Redshift access not set up yet.")
