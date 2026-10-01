"""DSpace crawler — M0 HIGH-RISK STUB.

Allowed in M0:
  - CLI signature
  - function signature
Prohibited in M0:
  - HTTP calls
  - live crawling

ADR-002: ingestion is OFFLINE. This script only writes the local NDJSON
snapshot; it does not perform live HTTP at runtime.
"""

from __future__ import annotations

from pathlib import Path


def crawl(output_path: Path) -> None:
    """M0 stub. TODO(M1): produce an NDJSON snapshot under output_path.

    The implementation MUST NOT issue live HTTP requests against the
    ICTU Repository at runtime. Operational crawling happens out-of-band.
    """
    raise NotImplementedError("crawl() not implemented in M0.")


def main() -> None:
    """CLI entrypoint (M0 stub)."""
    raise NotImplementedError("CLI not implemented in M0.")


if __name__ == "__main__":  # pragma: no cover
    main()