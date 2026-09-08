"""Minimal explicit logging setup; never log resumes, transcripts, or audio."""

import logging


def configure_logging(level: str) -> None:
    """Configure operational logs without adding telemetry or file handlers."""
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
