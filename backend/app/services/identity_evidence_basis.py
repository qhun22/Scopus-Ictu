"""D-3: what evidence an APPROVED lecturer ↔ Scopus-author link actually rests on.

Derived only from persisted ``identity_evidence`` rows. Those rows are copied
from the candidate's machine-generated evidence at ACCEPT time; a human review
decision is never stored as evidence, so accepting a candidate cannot raise the
level computed here.

Levels, strongest first (only SUPPORTS rows count towards a level):
  IDENTIFIER_SUPPORT    an exact independent identifier match (ORCID_EXACT)
  PUBLICATION_SUPPORT   bibliographic evidence (DOI_EXACT, PUBLICATION_OVERLAP,
                        COAUTHOR_CONFIRMED)
  NAME_ONLY             name similarity only
  NO_RECORDED_EVIDENCE  no supporting row (e.g. a link created before evidence
                        promotion existed)

AFFILIATION_MATCH is affiliation evidence, not identity evidence, and APPROVED_ID
has no specified meaning yet; both are reported but never raise the level.
``independently_verified`` is true only for IDENTIFIER_SUPPORT with no
contradicting evidence.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import IdentityEvidence

IDENTIFIER_TYPES = frozenset({"ORCID_EXACT"})
PUBLICATION_TYPES = frozenset({"DOI_EXACT", "PUBLICATION_OVERLAP", "COAUTHOR_CONFIRMED"})
NAME_TYPES = frozenset({"NAME_SIMILARITY"})
AFFILIATION_TYPES = frozenset({"AFFILIATION_MATCH"})


def evidence_basis(rows: Iterable[tuple[str, str]]) -> dict:
    """Classify (evidence_type, direction) pairs for one identity."""

    supporting: list[str] = []
    contradicting: list[str] = []
    for evidence_type, direction in rows:
        (supporting if direction == "SUPPORTS" else contradicting).append(evidence_type)
    count = lambda types: sum(1 for t in supporting if t in types)  # noqa: E731
    identifier, publication, name = count(IDENTIFIER_TYPES), count(PUBLICATION_TYPES), count(NAME_TYPES)
    if identifier:
        level = "IDENTIFIER_SUPPORT"
    elif publication:
        level = "PUBLICATION_SUPPORT"
    elif name:
        level = "NAME_ONLY"
    else:
        level = "NO_RECORDED_EVIDENCE"
    return {
        "level": level,
        "supporting_evidence_types": sorted(set(supporting)),
        "contradicting_evidence_types": sorted(set(contradicting)),
        "identifier_evidence_count": identifier,
        "publication_evidence_count": publication,
        "name_evidence_count": name,
        "affiliation_evidence_count": count(AFFILIATION_TYPES),
        "independently_verified": level == "IDENTIFIER_SUPPORT" and not contradicting,
    }


def evidence_basis_by_identity(session: Session, identity_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """One set-based query for many identities; identities without rows get NO_RECORDED_EVIDENCE."""

    grouped: dict[uuid.UUID, list[tuple[str, str]]] = defaultdict(list)
    if identity_ids:
        for identity_id, evidence_type, direction in session.execute(
            select(IdentityEvidence.identity_id, IdentityEvidence.evidence_type, IdentityEvidence.direction)
            .where(IdentityEvidence.identity_id.in_(set(identity_ids)))
        ).all():
            grouped[identity_id].append((evidence_type, direction))
    return {identity_id: evidence_basis(grouped.get(identity_id, [])) for identity_id in identity_ids}


__all__ = ["evidence_basis", "evidence_basis_by_identity"]
