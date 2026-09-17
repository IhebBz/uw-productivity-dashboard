"""Reads DSR and RBS straight from the Excel exports.

This is our only data source today. It exists purely so the rest of the
pipeline has something real to run against before Redshift access is ready -
see redshift_source.py for the planned replacement.

Caches the parsed result next to the source file, keyed by the file's size
and modified-time. Reading a large Excel file with openpyxl genuinely takes
over a minute (the original prototype's own documentation says the same
thing about the same files) - re-parsing an unchanged file on every
background refresh would waste most of the refresh cycle on nothing.
"""
import hashlib
import logging
import pathlib

import pandas as pd

from .base import DataSource

logger = logging.getLogger(__name__)


def _cached_read_excel(path: pathlib.Path, sheet_name: str) -> pd.DataFrame:
    """Read an Excel sheet, reusing a cached copy if the file hasn't changed."""
    stat = path.stat()
    signature = hashlib.sha256(
        f"{path.name}|{stat.st_size}|{int(stat.st_mtime)}".encode()).hexdigest()[:16]
    cache_path = path.with_suffix(".cache.pkl")
    sig_path = path.with_suffix(".cache.sig")

    if cache_path.exists() and sig_path.exists() and sig_path.read_text().strip() == signature:
        logger.info("%s unchanged since last read - using the cached copy.", path.name)
        return pd.read_pickle(cache_path)

    logger.info("%s changed (or first run) - parsing from Excel. This can take "
                "a couple of minutes on a large file.", path.name)
    df = pd.read_excel(path, sheet_name=sheet_name)
    df.to_pickle(cache_path)
    sig_path.write_text(signature)
    return df


class ExcelSource(DataSource):
    """Loads DSR.xlsx and RBS.xlsx from a given folder, sheet 'Export' in each."""

    def __init__(self, folder: str):
        """Store the folder that holds DSR.xlsx and RBS.xlsx."""
        self.folder = pathlib.Path(folder)

    def get_dsr(self) -> pd.DataFrame:
        """Read the DSR export as-is, no cleaning applied yet."""
        return _cached_read_excel(self.folder / "DSR.xlsx", "Export")

    def get_rbs(self) -> pd.DataFrame:
        """Read the RBS export as-is, no cleaning applied yet."""
        return _cached_read_excel(self.folder / "RBS.xlsx", "Export")