"""Matching engine — M0 HIGH-RISK STUB.

Allowed in M0:
  - orchestration interface
Prohibited in M0:
  - score calculation
  - candidate ranking logic
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchingContext:
    """M0 stub. TODO(M1): lecturer_id, candidate_set, evidence rules."""

    pass


class MatchingEngine:
    """M0 stub. TODO(M1): orchestrate candidate generation + scoring + evidence attachment."""

    def run(self, context: MatchingContext) -> None:
        raise NotImplementedError("MatchingEngine.run not implemented in M0.")