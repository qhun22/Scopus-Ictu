"""Review service — M0 scaffold."""

from __future__ import annotations


class ReviewService:
    """M0 stub. TODO(M1): approval / rejection / compensating revision flows."""

    def approve(self, identity_id: int, reviewer_id: int) -> None:
        raise NotImplementedError("ReviewService.approve not implemented in M0.")

    def reject(self, identity_id: int, reviewer_id: int, reason: str) -> None:
        raise NotImplementedError("ReviewService.reject not implemented in M0.")

    def revert(self, identity_id: int, reviewer_id: int, reason: str) -> None:
        """Create a compensating revision (ADR-003)."""
        raise NotImplementedError("ReviewService.revert not implemented in M0.")