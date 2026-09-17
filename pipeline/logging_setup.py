"""Configures logging once, the same way, for every entry point (the CLI
script and the local server). Every module just does
`logger = logging.getLogger(__name__)` and calls logger.warning(...) etc -
this is the only place that decides where those messages actually go.
"""
import logging


def setup_logging(level=logging.INFO) -> None:
    """Turn on console logging with a timestamp and the source module name."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
