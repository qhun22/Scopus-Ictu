"""Apply canonical changes — M0 HIGH-RISK STUB.

Allowed in M0:
  - transaction boundary signature
Prohibited in M0:
  - DB mutation implementation
"""

from __future__ import annotations


class ApplyCanonicalChangesService:
    """M0 stub. TODO(M1): atomic transaction over publications / publication_raw_sources / audit_events."""

    def apply(self, context) -> None:
        """Apply approved canonical changes (M0 stub)."""
        raise NotImplementedError("ApplyCanonicalChangesService.apply not implemented in M0.")