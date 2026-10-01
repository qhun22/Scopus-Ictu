"""Staging service — M0 scaffold.

Holds per-import parsed-but-not-canonical records in memory
(or in a per-import table — to be specified in M1).
"""

from __future__ import annotations


class StagingService:
    """M0 stub. TODO(M1): add-to-input staging + retrieval helpers."""

    def stage(self, context, rows) -> None:
        raise NotImplementedError("StagingService.stage not implemented in M0.")