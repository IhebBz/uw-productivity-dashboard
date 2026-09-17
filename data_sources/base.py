"""Common interface for wherever DSR and RBS data comes from.

Every other part of the pipeline only ever talks to this interface, never to
Excel or Redshift directly. That's the whole point: the day the daily
Redshift feed is ready, we add RedshiftSource and swap one line in the
pipeline config. Nothing else in the project needs to change.
"""
from abc import ABC, abstractmethod
import pandas as pd


class DataSource(ABC):
    """Anything that can hand back raw DSR and RBS rows as DataFrames."""

    @abstractmethod
    def get_dsr(self) -> pd.DataFrame:
        """Return the raw DSR rows, one row per policy line, columns unchanged."""

    @abstractmethod
    def get_rbs(self) -> pd.DataFrame:
        """Return the raw RBS rows, one row per bound policy line, columns unchanged."""
