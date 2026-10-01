"""Base rule — M0 scaffold.

Rules are isolated; no rule may perform DB writes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RuleContext:
    """M0 stub. TODO(M1): lecturer_id, candidate author_id, normalized inputs."""

    pass


@dataclass(frozen=True)
class RuleResult:
    """M0 stub. TODO(M1): matched flag, evidence_kind, evidence_payload."""

    matched: bool


class BaseRule(ABC):
    """M0 stub. TODO(M1): subclass per evidence kind."""

    @abstractmethod
    def apply(self, context: RuleContext) -> RuleResult:
        raise NotImplementedError