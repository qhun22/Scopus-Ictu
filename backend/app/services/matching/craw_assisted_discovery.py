"""Craw-assisted candidate discovery — proposes NEW lecturer/Scopus-author
pairs that the name-matching rules in ``candidate_generator.py`` miss, using
Craw-sourced publication evidence plus a weak, independent name check as the
discovery signal.

Why this exists (see docs/qa/PRIORITY_4_PREIMPLEMENTATION_AUDIT.md §2.C,
§5, §6): ``publication_evidence_enricher.enrich_candidates`` only ADDS
evidence to candidate pairs that already exist from the name-matching step
— it never creates a new pair. A lecturer whose Craw-known publication
matches a Scopus publication by DOI, but whose name does not match any of
the four strict name rules (different transliteration, abbreviation,
name-order difference the name rules do not handle), never gets a candidate
at all, even though the lecturer's own known-publication record points at a
real author position in that Scopus publication.

Why author position ALONE is not the anchor (the design mistake this module
previously made, and the reason this docstring is explicit about it): a DOI
or title match only proves two *publication* records describe the same
paper. A publication can have several author positions (co-authors), and
Craw's known-publication data carries no co-author list — so "this lecturer
claims this publication" by itself says nothing about *which* author
position among several is theirs. Turning every author position on a
reconciled publication into a candidate would be exactly the mass-candidate
anti-pattern ADR-004 forbids: a 5-author paper would produce 5 candidates
for one lecturer with zero of them actually anchored to a person.

The anchor this module requires instead is two independent facts holding at
once:

    1. Author position — the lecturer's known-publication reconciles
       (DOI-exact or title-exact, never ambiguous) to a canonical
       Publication, and the candidate Scopus author holds a real author
       position (a ``publication_authors`` row) on that publication.
    2. Name correspondence — ``_has_name_correspondence`` requires BOTH of
       the following against at least one Scopus surface (preferred_name or
       a ``ScopusAuthorNameVariant``) for that author, after the same
       Vietnamese-diacritic-folding normalization ``candidate_generator.py``
       uses for RULE_TITLE_STRIPPED_N2:
         a. surname agreement — the first token of the lecturer's full_name
            (the surname position in the Vietnamese "Surname [Middle...]
            Given" convention every lecturer record uses) equals the first
            token of that Scopus surface;
         b. a shared token outside ``_GENERIC_NAME_TOKENS`` — i.e. not just
            a common surname/middle name like "Nguyen", "Van", "Thi".
       This is deliberately WEAKER than the four strict rules (if it were
       as strong, the name step would already have found it) but it is
       independent, structurally-anchored corroboration — not a bare
       token-set intersection. An earlier version of this module used plain
       "share any token >= 2 chars", which wrongly matched co-authors who
       merely share a common Vietnamese surname or middle name with the
       lecturer (see docs/qa/MATCHING_CRAW_CANDIDATE_QUALITY_AUDIT.md for
       the false-positive cases that forced this redesign).

An author position that passes check 1 but fails check 2 — e.g. a 5-author
paper where the other 4 authors only share a common surname or middle name
with the lecturer, or share a given name but under a different surname — is
NEVER turned into a candidate. It is surfaced separately as "unattributed
publication evidence" so ADMIN/REVIEWER can see the known-publication
reconciled to a real Scopus publication without the system inventing an
identity claim it cannot support.

Once both checks pass, this is purely additive: it never touches
``publication_evidence_enricher.py``, never modifies an existing candidate,
never scores, never auto-approves, and is never used to downgrade or
remove a candidate. Callers always run the name step first and pass its
result in; this module only proposes pairs absent from that result.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from app.models.master_lecturer import Lecturer, LecturerKnownPublication, LecturerSourceSnapshot
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.services.matching.candidate_generator import normalize_name_n2, strip_observed_title_prefix
from app.services.matching.candidate_types import (
    EnrichedLecturerScopusCandidate,
    PublicationEvidence,
)
from app.services.matching.publication_evidence_enricher import (
    _reconcile_known_publications,
)

RULE_CRAW_KNOWN_PUBLICATION_AUTHOR_POSITION = "RULE_CRAW_KNOWN_PUBLICATION_AUTHOR_POSITION"

_MIN_TOKEN_LENGTH = 2

# Common Vietnamese surname and middle-name tokens (verified against the 410
# real lecturer names and 1207 real Scopus author surfaces in the WITH-JSON
# acceptance dataset, docs/qa/MATCHING_CRAW_CANDIDATE_QUALITY_AUDIT.md §4).
# Sharing ONLY tokens from this set is never sufficient corroboration — see
# the surname-agreement check in ``_has_name_correspondence`` below for why
# a plain token-set intersection (the bug this constant exists to close)
# wrongly matched unrelated co-authors who merely share a common surname or
# middle name ("Nguyen", "Van", "Thi", ...).
_GENERIC_NAME_TOKENS: frozenset[str] = frozenset(
    {
        "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo",
        "dang", "bui", "do", "ho", "ngo", "duong", "dinh", "ly", "dao", "doan",
        "luong", "thai", "trinh", "cao", "truong", "ha",
        "van", "thi", "duc", "thanh", "huu", "ngoc", "quang", "minh",
        "xuan", "kim", "hai", "tien", "cong", "duy", "anh",
    }
)


@dataclass(frozen=True, slots=True)
class UnattributedPublicationEvidence:
    """A reconciled known-publication / author-position pair that failed
    the independent name check — visible to ADMIN/REVIEWER as evidence of a
    real publication link, but never promoted to a candidate because
    nothing anchors it to this specific person."""

    lecturer_id: UUID
    scopus_author_id: UUID
    publication_evidence: PublicationEvidence


@dataclass(frozen=True, slots=True)
class CrawDiscoveryResult:
    """Newly proposed candidates, publication-reconciliation conflicts (same
    shape the enricher produces), and author positions that reconciled to a
    real publication but could not be anchored to the lecturer by name."""

    discovered: tuple[EnrichedLecturerScopusCandidate, ...]
    conflicts: tuple
    unattributed: tuple[UnattributedPublicationEvidence, ...]

    def __iter__(self):
        return iter(self.discovered)


@dataclass(frozen=True, slots=True)
class _NameSurface:
    """One parsed name string: its first token (the surname position in both
    the Vietnamese ``Surname [Middle...] Given`` convention used by every
    lecturer full_name, and the Scopus ``Surname, Rest`` convention used by
    most — not all — real Scopus author surfaces) plus its full token set."""

    surname: str | None
    tokens: frozenset[str]


def _parse_name_surface(value: str, strip_title: bool = False) -> _NameSurface:
    raw = strip_observed_title_prefix(value) if strip_title else value
    tokens = tuple(
        token
        for token in normalize_name_n2(raw).replace(",", " ").replace("-", " ").split(" ")
        if len(token) >= _MIN_TOKEN_LENGTH
    )
    return _NameSurface(surname=tokens[0] if tokens else None, tokens=frozenset(tokens))


def _scopus_author_surfaces(
    author: ScopusAuthor, variants: Iterable[ScopusAuthorNameVariant]
) -> tuple[_NameSurface, ...]:
    """One surface per distinct name string on this author — preferred_name
    plus every variant, each parsed independently (never merged into one
    token bag) so the surname-agreement check in
    ``_has_name_correspondence`` can be evaluated per-surface. Merging first
    would let a surname from one surface pair with a given name from another
    and wrongly look like one coherent name."""

    seen: dict[str, _NameSurface] = {}
    for raw in (author.preferred_name, *(variant.variant_name for variant in variants)):
        surface = _parse_name_surface(raw)
        if surface.tokens:
            seen.setdefault(normalize_name_n2(raw), surface)
    return tuple(seen.values())


def _has_name_correspondence(lecturer_surface: _NameSurface, scopus_surfaces: Iterable[_NameSurface]) -> bool:
    """Two independent conditions, both required, evaluated against at least
    one Scopus surface for this author:

    PRIMARY PATH (surname-anchored):
    1. Surname agreement — the first token of the lecturer's full_name
       equals the first token of that Scopus surface. This is the
       structural anchor a plain token-set intersection lacks: two
       co-authors who share only a common surname or middle name
       ("Nguyen", "Van", "Thi", ...) have DIFFERENT given names, and without
       requiring the surname position itself to agree, a shared given-name
       token alone (e.g. both named "Dung" by coincidence, different
       surnames) would also wrongly pass.
    2. Distinctive token — at least one shared token that is NOT in
       ``_GENERIC_NAME_TOKENS``. A name built entirely from common surname/
       middle-name tokens never corroborates identity by itself.

    FALLBACK PATH (reordered Scopus name):
    Some real Scopus surfaces have the given name in the first position
    (e.g. "Canh, Hoang Thi" for lecturer "Hoang Thi Canh", or
    "Tan, Nguyen Hong" for "Nguyen Hong Tan"). The surname-agreement check
    fails these even though it is the same person. The fallback allows a
    match when ALL of the lecturer's distinctive tokens are present in the
    Scopus token set — i.e. the Scopus surface is a permutation of the
    same name, not a different person. A single distinctive token is
    sufficient because co-authors on the same paper who share NO distinctive
    token with the lecturer cannot pass this check (verified against real
    co-author pairs in docs/qa/MATCHING_CRAW_CANDIDATE_QUALITY_AUDIT.md §10).

    Initials-only Scopus surfaces (e.g. "Nguyen, V.-B.") correctly fail here
    — token length "v"/"b" never reaches ``_MIN_TOKEN_LENGTH``. They are
    recovered through a full-name ``ScopusAuthorNameVariant`` surface
    instead, evaluated as its own independent surface above.
    """

    if lecturer_surface.surname is None:
        return False
    lec_distinctive = lecturer_surface.tokens - _GENERIC_NAME_TOKENS
    for surface in scopus_surfaces:
        if surface.surname == lecturer_surface.surname:
            # Primary path: surnames agree — require a DIFFERENT distinctive
            # token to corroborate (the surname itself is not additional
            # evidence once we already know it matches).
            non_surname_lec = lecturer_surface.tokens - {lecturer_surface.surname}
            non_surname_sco = surface.tokens - {surface.surname}
            corroboration = (non_surname_lec & non_surname_sco) - _GENERIC_NAME_TOKENS
            if corroboration:
                return True
        else:
            # Fallback for reordered Scopus name: all of the lecturer's tokens
            # (including the surname) are present in the Scopus token set, and
            # there is at least one distinctive token shared. This handles cases
            # like "Canh, Hoang Thi" for lecturer "Hoang Thi Canh" — same name
            # reordered, not a different person. Requiring the lecturer's surname
            # to be present prevents matching when the Scopus surface is a
            # genuinely different person who happens to share a distinctive
            # given-name token (e.g. "Nguyen Van Dung" vs "Tran, Van Dung").
            if (
                lec_distinctive
                and lec_distinctive <= surface.tokens
                and lecturer_surface.surname in surface.tokens
            ):
                return True
    return False


def discover_craw_assisted_candidates(
    existing_candidate_pairs: Iterable[tuple[UUID, UUID]],
    known_publications: Iterable[LecturerKnownPublication],
    snapshots: Iterable[LecturerSourceSnapshot],
    publications: Iterable[Publication],
    publication_authors: Iterable[PublicationAuthor],
    scopus_authors: Iterable[ScopusAuthor],
    scopus_author_name_variants: Iterable[ScopusAuthorNameVariant],
    lecturers: Iterable[Lecturer],
) -> CrawDiscoveryResult:
    """Pure, in-memory discovery — mirrors ``enrich_candidates``'s shape so
    the two can share test fixtures, but this one MAY create new pairs,
    subject to the two-anchor rule documented on this module.

    ``existing_candidate_pairs`` is the set of (lecturer_id, scopus_author_id)
    already proposed by the name step (``candidate_generator.py``) — this
    function never re-proposes those; it only fills in pairs that step
    cannot see, while still requiring the same conservative DOI/title exact
    reconciliation (ambiguous matches are excluded, never guessed) AND an
    independent name-token correspondence to the specific author position.
    """

    existing = set(existing_candidate_pairs)
    snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
    reconciled, conflicts = _reconcile_known_publications(
        known_publications, snapshots_by_id, publications
    )

    author_rows_by_publication: dict[UUID, list[PublicationAuthor]] = defaultdict(list)
    for row in publication_authors:
        author_rows_by_publication[row.publication_id].append(row)

    author_by_id = {author.id: author for author in scopus_authors}
    variants_by_author: dict[UUID, list[ScopusAuthorNameVariant]] = defaultdict(list)
    for variant in scopus_author_name_variants:
        variants_by_author[variant.scopus_author_id].append(variant)
    lecturer_by_id = {lecturer.id: lecturer for lecturer in lecturers}

    author_surfaces_by_id: dict[UUID, tuple[_NameSurface, ...]] = {}

    def _surfaces_for_author(scopus_author_id: UUID) -> tuple[_NameSurface, ...]:
        cached = author_surfaces_by_id.get(scopus_author_id)
        if cached is not None:
            return cached
        author = author_by_id.get(scopus_author_id)
        if author is None:
            return ()
        surfaces = _scopus_author_surfaces(author, variants_by_author.get(scopus_author_id, ()))
        author_surfaces_by_id[scopus_author_id] = surfaces
        return surfaces

    # One descriptor per NEW (lecturer, scopus_author) pair discovered via a
    # specific publication. DOI provenance wins over title for the same
    # publication; UUID order then makes reruns deterministic.
    discovered_evidence: dict[tuple[UUID, UUID], PublicationEvidence] = {}
    unattributed: list[UnattributedPublicationEvidence] = []
    rule_rank = {
        "RULE_KNOWN_PUBLICATION_DOI_EXACT": 0,
        "RULE_KNOWN_PUBLICATION_TITLE_EXACT": 1,
    }

    for item in reconciled:
        lecturer_id = item.known_publication.lecturer_id
        lecturer = lecturer_by_id.get(lecturer_id)
        lecturer_surface = (
            _parse_name_surface(lecturer.full_name, strip_title=True) if lecturer is not None else _NameSurface(None, frozenset())
        )

        for author_row in sorted(
            author_rows_by_publication.get(item.publication.id, ()),
            key=lambda row: (row.author_order, str(row.id)),
        ):
            scopus_author_id = author_row.scopus_author_id
            pair = (lecturer_id, scopus_author_id)
            if pair in existing:
                continue  # the name step already proposed this pair

            descriptor = PublicationEvidence(
                rule_id=item.rule_id,
                known_publication_id=item.known_publication.id,
                lecturer_id=lecturer_id,
                lecturer_snapshot_id=item.snapshot.id,
                canonical_publication_id=item.publication.id,
                canonical_publication_eid=item.publication.eid,
                candidate_scopus_author_id=scopus_author_id,
                known_publication_doi_normalized=item.known_publication.doi_normalized,
                known_publication_title_normalized=item.known_publication.title_normalized,
                canonical_publication_doi=item.publication.doi,
                canonical_publication_title=item.publication.title,
                reconciliation=item.reconciliation,
            )

            has_name_correspondence = _has_name_correspondence(
                lecturer_surface, _surfaces_for_author(scopus_author_id)
            )
            if not has_name_correspondence:
                # Author position is real, but nothing ties THIS author
                # position to THIS lecturer by name — never guess.
                unattributed.append(
                    UnattributedPublicationEvidence(
                        lecturer_id=lecturer_id,
                        scopus_author_id=scopus_author_id,
                        publication_evidence=descriptor,
                    )
                )
                continue

            existing_descriptor = discovered_evidence.get(pair)
            if existing_descriptor is None or (
                rule_rank[descriptor.rule_id],
                str(descriptor.known_publication_id),
            ) < (rule_rank[existing_descriptor.rule_id], str(existing_descriptor.known_publication_id)):
                discovered_evidence[pair] = descriptor

    result: list[EnrichedLecturerScopusCandidate] = []
    for pair in sorted(discovered_evidence, key=lambda value: (str(value[0]), str(value[1]))):
        lecturer_id, scopus_author_id = pair
        author = author_by_id.get(scopus_author_id)
        if author is None:
            continue  # defensive: publication_authors row with no matching scopus_authors row
        result.append(
            EnrichedLecturerScopusCandidate(
                lecturer_id=lecturer_id,
                scopus_author_id=scopus_author_id,
                scopus_id=author.scopus_id,
                preferred_name=author.preferred_name,
                evidence=(),  # no strict name-rule evidence — this pair exists via Craw + weak name correspondence
                publication_evidence=(discovered_evidence[pair],),
            )
        )

    unattributed_sorted = tuple(
        sorted(
            unattributed,
            key=lambda item: (
                str(item.lecturer_id),
                str(item.scopus_author_id),
                str(item.publication_evidence.known_publication_id),
            ),
        )
    )

    return CrawDiscoveryResult(tuple(result), conflicts, unattributed_sorted)


__all__ = [
    "RULE_CRAW_KNOWN_PUBLICATION_AUTHOR_POSITION",
    "CrawDiscoveryResult",
    "UnattributedPublicationEvidence",
    "discover_craw_assisted_candidates",
]
