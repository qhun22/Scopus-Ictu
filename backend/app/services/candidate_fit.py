"""Read-only "degree of fit" of a lecturer <-> Scopus author candidate, with its reasons.

The thesis brief asks the suggestion to show its grounds and a degree of fit. This module turns the
evidence a reviewer already sees into one of four labels plus a list of reason codes. It is NOT a
probability, it is computed on read (nothing is stored), and it never confirms or rejects anything:
the reviewer still decides, and the D-2 reason policy is untouched.

Signals
-------
* publication support   : the Scopus author owns a paper the lecturer is known to have written
* ICTU affiliation      : papers of the Scopus author whose collected affiliation text names ICTU
* name evidence         : the names match under at least one normalisation rule
* penalties             : the ID is proposed for several lecturers, or the lecturer has several IDs

Levels (HIGH > MEDIUM > LOW > INSUFFICIENT)
-------------------------------------------
HIGH          publication support AND ICTU affiliation, ID not shared
MEDIUM        publication support, OR ICTU affiliation together with a name match; a shared ID never
              rises above MEDIUM
LOW           name evidence only
INSUFFICIENT  nothing to go on
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.affiliation import (
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.affiliation_override import PublicationAuthorAffiliationOverride
from app.models.publication import PublicationAuthor
from app.services.text_folding import fold_text

FitLevel = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]

_ICTU_ACRONYM = re.compile(r"\bictu\b")


def is_ictu_affiliation(text: str | None) -> bool:
    """True when an affiliation string names the University of ICT (Vietnamese or English)."""

    if not text:
        return False
    plain = fold_text(text)
    return (
        ("cong nghe thong tin" in plain and "truyen thong" in plain)
        or ("information and communication technology" in plain and "thai nguyen" in plain)
        or bool(_ICTU_ACRONYM.search(plain))
    )


@dataclass(frozen=True, slots=True)
class FitAssessment:
    level: FitLevel
    reasons: tuple[str, ...]
    ictu_affiliation_papers: int


def assess_fit(
    *,
    name_evidence_count: int,
    publication_support_count: int,
    ictu_affiliation_papers: int,
    is_shared_author: bool,
    is_ambiguous_lecturer: bool,
) -> FitAssessment:
    reasons: list[str] = []
    supported = publication_support_count > 0
    affiliated = ictu_affiliation_papers > 0
    named = name_evidence_count > 0

    if supported:
        reasons.append("PUBLICATION_SUPPORT")
    if affiliated:
        reasons.append("ICTU_AFFILIATION")
    if named:
        reasons.append("NAME_MATCH")
    if named and not supported and not affiliated:
        reasons.append("NAME_ONLY")
    if is_shared_author:
        reasons.append("SHARED_ID")
    if is_ambiguous_lecturer:
        reasons.append("MULTIPLE_IDS_FOR_LECTURER")

    if supported and affiliated and not is_shared_author:
        level: FitLevel = "HIGH"
    elif supported or (affiliated and named):
        level = "MEDIUM"
    elif named or affiliated:
        level = "LOW"
    else:
        level = "INSUFFICIENT"
    if is_shared_author and level == "HIGH":
        level = "MEDIUM"
    return FitAssessment(level, tuple(reasons), ictu_affiliation_papers)


def ictu_affiliation_paper_counts(
    session: Session, scopus_author_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Per Scopus author: how many of the author's papers carry an affiliation naming ICTU.

    Looks at the affiliation text the sources reported and at the units an ADMIN recorded by hand.
    """

    ids = set(scopus_author_ids)
    if not ids:
        return {}
    papers: dict[uuid.UUID, set[uuid.UUID]] = {}

    reported = session.execute(
        select(
            PublicationAuthor.scopus_author_id,
            PublicationAuthor.id,
            PublicationAuthorAffiliation.raw_affiliation_text,
        )
        .join(
            PublicationAuthorAffiliationResolution,
            PublicationAuthorAffiliationResolution.publication_author_id == PublicationAuthor.id,
        )
        .join(
            PublicationAuthorAffiliation,
            PublicationAuthorAffiliation.resolution_id == PublicationAuthorAffiliationResolution.id,
        )
        .where(
            PublicationAuthor.scopus_author_id.in_(ids),
            PublicationAuthorAffiliation.raw_affiliation_text.is_not(None),
        )
    ).all()
    for author_id, position_id, text in reported:
        if is_ictu_affiliation(text):
            papers.setdefault(author_id, set()).add(position_id)

    recorded = session.execute(
        select(
            PublicationAuthor.scopus_author_id,
            PublicationAuthor.id,
            PublicationAuthorAffiliationOverride.affiliation_text,
        )
        .join(
            PublicationAuthorAffiliationOverride,
            PublicationAuthorAffiliationOverride.publication_author_id == PublicationAuthor.id,
        )
        .where(
            PublicationAuthor.scopus_author_id.in_(ids),
            PublicationAuthorAffiliationOverride.status == "ACTIVE",
        )
    ).all()
    for author_id, position_id, text in recorded:
        if is_ictu_affiliation(text):
            papers.setdefault(author_id, set()).add(position_id)

    return {author_id: len(positions) for author_id, positions in papers.items()}
