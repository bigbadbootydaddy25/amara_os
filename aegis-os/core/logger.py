"""
AMARA DEED logger — writes to stdout and deed/output/DEED_NOTES_*.txt.
Every instrument, gap, well, failure, and finding is logged here.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import OUTPUT_DIR, NOTES_FILENAME

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_NOTES_FILE = OUTPUT_DIR / NOTES_FILENAME


class _DeedNoteHandler(logging.FileHandler):
    """Appends to the deed notes file with ISO timestamps."""
    def __init__(self):
        _NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(str(_NOTES_FILE), mode="a", encoding="utf-8")
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        ))


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)-18s] %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    ))
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)
    # Notes file
    fh = _DeedNoteHandler()
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger


def write_section_header(log: logging.Logger, title: str) -> None:
    bar = "=" * 70
    log.info("")
    log.info(bar)
    log.info("  %s", title)
    log.info(bar)


def write_finding(log: logging.Logger, label: str, value: str) -> None:
    log.info("  %-30s %s", label + ":", value)


def write_instrument(
    log: logging.Logger,
    seq: int,
    inst_type: str,
    grantor: str,
    grantee: str,
    book: str,
    page: str,
    date: str,
    notes: str = "",
) -> None:
    log.info(
        "  [%03d] %-18s | %s → %s | BK %s PG %s | %s%s",
        seq, inst_type, grantor, grantee, book, page, date,
        f" | NOTE: {notes}" if notes else "",
    )


def write_gap(log: logging.Logger, description: str) -> None:
    log.warning("  ⚠ GAP: %s", description)


def write_missing(log: logging.Logger, field: str) -> None:
    log.warning("  ✗ MISSING: %s", field)


def write_error(log: logging.Logger, step: str, error: str) -> None:
    log.error("  ✗ FAILED [%s]: %s", step, error)
