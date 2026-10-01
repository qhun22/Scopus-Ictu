"""Import orchestrator — M0 scaffold.

Coordinates the stages of the Scopus import pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportContext:
    """M0 stub. TODO(M1): import_id, file_path, user_id, configuration."""

    import_id: int


class ImportOrchestrator:
    """M0 stub. TODO(M1): orchestrate validate → stage → normalize → dedupe → diff → apply → audit."""

    def run(self, context: ImportContext) -> None:
        """Run the full pipeline for a single import (M0 stub)."""
        raise NotImplementedError("ImportOrchestrator.run not implemented in M0.")