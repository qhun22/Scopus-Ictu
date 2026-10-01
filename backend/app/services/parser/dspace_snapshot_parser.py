"""DSpace snapshot parser — M0 scaffold.

Parses NDJSON snapshot files produced by the crawler.
NO normalization, NO DB writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedDSpaceItem:
    """M0 stub. TODO(M1): external_id, name, affiliation, raw_payload."""

    item_no: int


@dataclass(frozen=True)
class ParsedDSpaceSnapshot:
    """M0 stub."""

    items: list[ParsedDSpaceItem]


class DSpaceSnapshotParser:
    """M0 stub. TODO(M1): implement NDJSON streaming parser."""

    def parse(self, file_path: Path) -> ParsedDSpaceSnapshot:
        """Parse a DSpace NDJSON snapshot file (M0 stub)."""
        raise NotImplementedError("DSpaceSnapshotParser.parse not implemented in M0.")