"""Parsers — M0 scaffold.

Parsers only parse. No DB writes, no business logic.
"""

from app.services.parser.dspace_snapshot_parser import DSpaceSnapshotParser
from app.services.parser.scopus_csv_parser import ScopusCsvParser

__all__ = ["ScopusCsvParser", "DSpaceSnapshotParser"]