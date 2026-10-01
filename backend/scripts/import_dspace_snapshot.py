"""Import DSpace snapshot — M0 stub.

Reads a local NDJSON snapshot and produces canonical lecturer rows.
TODO(M1): real parser → normalize → upsert flow.
"""

from __future__ import annotations

from pathlib import Path


def import_snapshot(snapshot_path: Path) -> None:
    """M0 stub. TODO(M1): load snapshot → normalize → upsert lecturer rows."""
    raise NotImplementedError("import_snapshot() not implemented in M0.")


if __name__ == "__main__":  # pragma: no cover
    import_snapshot(Path("./data/snapshots/"))