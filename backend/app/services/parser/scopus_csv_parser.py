"""Scopus CSV parser — M0 scaffold.

Parses raw Scopus CSV into an in-memory structure.
NO normalization, NO DB writes, NO matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedScopusRow:
    """M0 stub. TODO(M1): eid, doi, title, year, authors, raw_payload."""

    row_no: int


@dataclass(frozen=True)
class ParsedScopusFile:
    """M0 stub."""

    rows: list[ParsedScopusRow]


class ScopusCsvParser:
    """M0 stub. TODO(M1): implement streaming CSV parse with header detection."""

    def parse(self, file_path: Path) -> ParsedScopusFile:
        """Parse a Scopus CSV file (M0 stub)."""
        raise NotImplementedError("ScopusCsvParser.parse not implemented in M0.")