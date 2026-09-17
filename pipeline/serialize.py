"""Turns pipeline results into plain, JSON-safe Python types.

pandas/numpy hand back their own number types (numpy.bool_, numpy.int64,
...) which the standard json module and FastAPI's encoder don't know how to
read. This is the one place that conversion happens, used by both the CLI
script and the local server, so it's never solved twice.
"""
import dataclasses
import numpy as np


def to_json_safe(obj):
    """Recursively convert dataclasses, numpy scalars, dicts and lists to plain Python types."""
    if dataclasses.is_dataclass(obj):
        return {k: to_json_safe(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj
