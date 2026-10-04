"""Deterministic, read-only lecturer ↔ Scopus candidate retrieval.

This module deliberately stops at candidate generation.  It does not score,
rank, confirm, reject or persist anything.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor, ScopusAuthorNameVariant
from app.services.matching.candidate_types import (
    CandidateEvidence,
    LecturerScopusCandidate,
    RuleId,
    SurfaceType,
)

# Exact whitelist derived from the frozen 410-lecturer acceptance dataset.
# ``Khác.`` is observed in the data but is not an academic-title prefix and is
# intentionally not stripped.
OBSERVED_TITLE_PREFIXES: tuple[str, ...] = (
    "DH.",
    "GS.TS.",
    "PGS.TS.",
    "ThS.",
    "TS.",
)

RULE_ORDER: tuple[RuleId, ...] = (
    "RULE_EXACT_N0",
    "RULE_TITLE_STRIPPED_N0",
    "RULE_TITLE_STRIPPED_N2",
    "RULE_TITLE_STRIPPED_N2_FORMAT",
)

_TITLE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    + "|".join(re.escape(prefix) for prefix in OBSERVED_TITLE_PREFIXES)
    + r")(?:\s|$)\s*",
    flags=re.IGNORECASE,
)


def normalize_name_n0(value: str) -> str:
    """Conservative Unicode/text normalization used by RULE_EXACT_N0."""
    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def normalize_name_n2(value: str) -> str:
    """N0 plus Vietnamese diacritic folding for candidate retrieval only."""
    value = normalize_name_n0(value).replace("đ", "d").replace("ð", "d")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if not unicodedata.combining(character)
    )


def normalize_comma_equivalence(value: str) -> str:
    """Remove comma separators while preserving the original token order."""
    return " ".join(re.sub(r"\s*,\s*", " ", normalize_name_n2(value)).split())


def has_observed_title_prefix(value: str) -> bool:
    """Return whether a whitelisted title prefix occurs at the beginning."""
    return _TITLE_PREFIX_PATTERN.match(value) is not None


def strip_observed_title_prefix(value: str) -> str:
    """Strip at most one whitelisted beginning prefix, otherwise leave intact."""
    return _TITLE_PREFIX_PATTERN.sub("", value, count=1)


@dataclass(frozen=True, slots=True)
class _ScopusSurface:
    scopus_author_id: UUID
    scopus_id: str
    preferred_name: str
    surface_type: SurfaceType
    surface_value: str


@dataclass(frozen=True, slots=True)
class _IndexedSurface:
    surface: _ScopusSurface
    comparison_value: str


def _surface_type(value: str) -> SurfaceType:
    if value not in {"AUTHOR_FULL_NAME", "AUTHOR_DISPLAY"}:
        raise ValueError(f"Unsupported Scopus name variant type: {value}")
    return value  # type: ignore[return-value]


def _lecturer_query(rule_id: RuleId, full_name: str) -> str | None:
    if rule_id == "RULE_EXACT_N0":
        return normalize_name_n0(full_name)

    if not has_observed_title_prefix(full_name):
        return None

    stripped = strip_observed_title_prefix(full_name)
    if rule_id == "RULE_TITLE_STRIPPED_N0":
        return normalize_name_n0(stripped)
    if rule_id == "RULE_TITLE_STRIPPED_N2":
        return normalize_name_n2(stripped)
    if rule_id == "RULE_TITLE_STRIPPED_N2_FORMAT":
        return normalize_comma_equivalence(stripped)
    raise ValueError(f"Unknown candidate rule: {rule_id}")


def _surface_query(rule_id: RuleId, value: str) -> str:
    if rule_id in {"RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N0"}:
        return normalize_name_n0(value)
    if rule_id == "RULE_TITLE_STRIPPED_N2":
        return normalize_name_n2(value)
    if rule_id == "RULE_TITLE_STRIPPED_N2_FORMAT":
        return normalize_comma_equivalence(value)
    raise ValueError(f"Unknown candidate rule: {rule_id}")


def _surface_sort_key(indexed: _IndexedSurface) -> tuple[str, str, str, str]:
    surface = indexed.surface
    return (
        surface.surface_type,
        surface.surface_value,
        surface.scopus_id,
        str(surface.scopus_author_id),
    )


def _build_surfaces(
    authors: Iterable[ScopusAuthor],
    variants: Iterable[ScopusAuthorNameVariant],
) -> tuple[_ScopusSurface, ...]:
    authors_by_id = {author.id: author for author in authors}
    surfaces: set[_ScopusSurface] = set()

    for author in authors_by_id.values():
        surfaces.add(
            _ScopusSurface(
                scopus_author_id=author.id,
                scopus_id=author.scopus_id,
                preferred_name=author.preferred_name,
                surface_type="PREFERRED_NAME",
                surface_value=author.preferred_name,
            )
        )

    for variant in variants:
        author = authors_by_id.get(variant.scopus_author_id)
        if author is None:
            continue
        surfaces.add(
            _ScopusSurface(
                scopus_author_id=author.id,
                scopus_id=author.scopus_id,
                preferred_name=author.preferred_name,
                surface_type=_surface_type(variant.variant_type),
                surface_value=variant.variant_name,
            )
        )

    return tuple(
        sorted(
            surfaces,
            key=lambda surface: (
                surface.surface_type,
                surface.surface_value,
                surface.scopus_id,
                str(surface.scopus_author_id),
            ),
        )
    )


def generate_candidates(
    lecturers: Iterable[Lecturer],
    authors: Iterable[ScopusAuthor],
    variants: Iterable[ScopusAuthorNameVariant],
) -> tuple[LecturerScopusCandidate, ...]:
    """Generate deterministic transient candidates from already-loaded rows."""
    lecturer_rows = tuple(sorted(lecturers, key=lambda lecturer: str(lecturer.id)))
    author_rows = tuple(authors)
    variant_rows = tuple(variants)
    surfaces = _build_surfaces(author_rows, variant_rows)

    indexes: dict[RuleId, dict[str, list[_IndexedSurface]]] = {}
    for rule_id in RULE_ORDER:
        index: dict[str, list[_IndexedSurface]] = defaultdict(list)
        for surface in surfaces:
            if rule_id == "RULE_TITLE_STRIPPED_N2_FORMAT" and "," not in surface.surface_value:
                continue
            indexed = _IndexedSurface(
                surface=surface,
                comparison_value=_surface_query(rule_id, surface.surface_value),
            )
            index[indexed.comparison_value].append(indexed)
        indexes[rule_id] = index

    evidence_by_pair: dict[tuple[UUID, UUID], set[CandidateEvidence]] = defaultdict(set)
    author_by_pair: dict[tuple[UUID, UUID], _ScopusSurface] = {}

    for lecturer in lecturer_rows:
        for rule_id in RULE_ORDER:
            lecturer_comparison = _lecturer_query(rule_id, lecturer.full_name)
            if lecturer_comparison is None:
                continue
            matching_surfaces = indexes[rule_id].get(lecturer_comparison, ())
            for indexed in matching_surfaces:
                surface = indexed.surface
                pair = (lecturer.id, surface.scopus_author_id)
                evidence_by_pair[pair].add(
                    CandidateEvidence(
                        rule_id=rule_id,
                        lecturer_source_value=lecturer.full_name,
                        lecturer_comparison_value=lecturer_comparison,
                        scopus_surface_type=surface.surface_type,
                        scopus_surface_value=surface.surface_value,
                        scopus_comparison_value=indexed.comparison_value,
                    )
                )
                author_by_pair.setdefault(pair, surface)

    def evidence_key(evidence: CandidateEvidence) -> tuple[int, str, str, str]:
        return (
            RULE_ORDER.index(evidence.rule_id),
            evidence.scopus_surface_type,
            evidence.scopus_surface_value,
            evidence.scopus_comparison_value,
        )

    result = []
    for pair in sorted(
        evidence_by_pair,
        key=lambda value: (
            str(value[0]),
            author_by_pair[value].scopus_id,
            str(value[1]),
        ),
    ):
        surface = author_by_pair[pair]
        result.append(
            LecturerScopusCandidate(
                lecturer_id=pair[0],
                scopus_author_id=pair[1],
                scopus_id=surface.scopus_id,
                preferred_name=surface.preferred_name,
                evidence=tuple(sorted(evidence_by_pair[pair], key=evidence_key)),
            )
        )
    return tuple(result)


class CandidateGenerator:
    """Read-only service that loads canonical rows in three bulk queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _load_inputs(
        self,
    ) -> tuple[list[Lecturer], list[ScopusAuthor], list[ScopusAuthorNameVariant]]:
        lecturers = list(self._session.scalars(select(Lecturer).order_by(Lecturer.id)))
        authors = list(self._session.scalars(select(ScopusAuthor).order_by(ScopusAuthor.id)))
        variants = list(
            self._session.scalars(
                select(ScopusAuthorNameVariant).order_by(
                    ScopusAuthorNameVariant.scopus_author_id,
                    ScopusAuthorNameVariant.variant_type,
                    ScopusAuthorNameVariant.variant_name,
                    ScopusAuthorNameVariant.id,
                )
            )
        )
        return lecturers, authors, variants

    def generate_all(self) -> tuple[LecturerScopusCandidate, ...]:
        """Generate candidates for every canonical lecturer without writes."""
        lecturers, authors, variants = self._load_inputs()
        return generate_candidates(lecturers, authors, variants)

    def generate_for_lecturer(self, lecturer_id: UUID) -> tuple[LecturerScopusCandidate, ...]:
        """Generate candidates for one lecturer using the same bulk author index."""
        lecturer = self._session.scalar(select(Lecturer).where(Lecturer.id == lecturer_id))
        if lecturer is None:
            return ()
        _, authors, variants = self._load_inputs()
        return generate_candidates((lecturer,), authors, variants)

    def generate(self, context: object | None = None) -> tuple[LecturerScopusCandidate, ...]:
        """Compatibility entry point for the previous matching scaffold."""
        del context
        return self.generate_all()
