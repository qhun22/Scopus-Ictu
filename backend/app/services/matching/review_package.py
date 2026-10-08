"""Human matching review package — C3-A2.

Research/review tooling only.  It prepares deterministic material for a human
reviewer and NEVER creates ground truth: it does not fill decisions, expected
Scopus IDs, or confirmation metadata, and it computes no precision/recall/F1,
no ranking, and no score.

Suggestions come from the CURRENT production ``CandidateGenerator`` output
enriched by the existing ``PublicationEvidenceEnricher``.  Persisted candidate
state is never read.  No database writes are performed here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

SCHEMA_VERSION = "1.0"

SUGGESTION_CANDIDATE = "CANDIDATE"
SUGGESTION_NONE = "NO_CANDIDATE_GENERATED"

CANDIDATE_REVIEW_COLUMNS: tuple[str, ...] = (
    "lecturer_source_id",
    "institutional_email",
    "lecturer_full_name",
    "suggestion_status",
    "candidate_count",
    "candidate_scopus_id",
    "candidate_preferred_name",
    "name_rule_ids",
    "name_evidence_json",
    "publication_evidence_count",
    "publication_rule_ids",
    "publication_evidence_json",
    "lecturer_publication_conflict_count",
    "lecturer_publication_conflict_reasons",
)

# Must equal the C3-A1 reference contract header exactly (order included).
LABELING_SHEET_COLUMNS: tuple[str, ...] = (
    "lecturer_source_id",
    "institutional_email",
    "lecturer_full_name",
    "decision",
    "expected_scopus_id",
    "confirmation_source",
    "confirmed_at",
    "notes",
)

MANIFEST_FIELDS: tuple[str, ...] = (
    "schema_version",
    "generated_at",
    "official_lecturer_dataset_sha256",
    "source_id_file_sha256",
    "candidate_rule_set_id",
    "candidate_rule_set_version",
    "selected_lecturer_count",
    "lecturers_with_candidates",
    "lecturers_without_candidates",
    "candidate_pair_count",
    "ambiguous_lecturer_count",
    "publication_conflict_count",
    "candidate_review_sha256",
    "reference_labeling_sheet_sha256",
)


class ReviewPackageError(Exception):
    """Domain/input error with a message safe to show to the operator."""


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OfficialLecturer:
    source_id: str
    full_name: str
    institutional_email: str | None


@dataclass(frozen=True)
class ReviewCandidate:
    scopus_id: str
    preferred_name: str
    name_evidence: tuple[dict[str, str], ...]
    publication_evidence: tuple[dict[str, str | None], ...]


@dataclass(frozen=True)
class ReviewLecturer:
    source_id: str
    institutional_email: str | None
    full_name: str
    candidates: tuple[ReviewCandidate, ...]
    publication_conflict_count: int
    publication_conflict_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPackageCounts:
    selected_lecturer_count: int
    lecturers_with_candidates: int
    lecturers_without_candidates: int
    candidate_pair_count: int
    ambiguous_lecturer_count: int
    publication_conflict_count: int


@dataclass(frozen=True)
class ReviewPackage:
    lecturers: tuple[ReviewLecturer, ...]
    counts: ReviewPackageCounts
    candidate_review_csv: bytes
    reference_labeling_sheet_csv: bytes
    manifest: dict[str, Any]
    manifest_json: bytes


# ---------------------------------------------------------------------------
# Official dataset and selection
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_official_lecturers(dataset_bytes: bytes) -> tuple[OfficialLecturer, ...]:
    """Parse the official lecturer dataset; every source_id must be unique."""
    try:
        raw = json.loads(dataset_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReviewPackageError("Official lecturer dataset is not valid UTF-8 JSON.") from None

    rows = raw.get("lecturers") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        raise ReviewPackageError("Official lecturer dataset has no 'lecturers' list.")

    lecturers: list[OfficialLecturer] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ReviewPackageError(f"Official lecturer row {index} is not an object.")
        source_id = row.get("source_id")
        full_name = row.get("full_name")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ReviewPackageError(f"Official lecturer row {index} has no source_id.")
        if not isinstance(full_name, str) or not full_name.strip():
            raise ReviewPackageError(f"Official lecturer row {index} has no full_name.")
        source_id = source_id.strip()
        if source_id in seen:
            duplicates.add(source_id)
        seen.add(source_id)
        email = row.get("institutional_email")
        email = email.strip() if isinstance(email, str) and email.strip() else None
        lecturers.append(OfficialLecturer(source_id, full_name.strip(), email))

    if duplicates:
        raise ReviewPackageError(
            f"Official lecturer dataset has duplicate source_id values: {sorted(duplicates)!r}"
        )
    return tuple(sorted(lecturers, key=lambda lecturer: lecturer.source_id))


def parse_source_id_file(content: bytes) -> tuple[str, ...]:
    """One lecturer_source_id per line; blank lines and '#' comments allowed."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ReviewPackageError("Source-id file is not valid UTF-8.") from None

    requested: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
        requested.append(value)

    if duplicates:
        raise ReviewPackageError(f"Source-id file has duplicate entries: {sorted(duplicates)!r}")
    if not requested:
        raise ReviewPackageError("Source-id file selects no lecturers.")
    return tuple(requested)


def select_lecturers(
    official: Sequence[OfficialLecturer],
    requested_source_ids: Sequence[str] | None,
) -> tuple[OfficialLecturer, ...]:
    """Default: all official lecturers.  Otherwise exactly the requested ones."""
    ordered = tuple(sorted(official, key=lambda lecturer: lecturer.source_id))
    if requested_source_ids is None:
        return ordered
    by_id = {lecturer.source_id: lecturer for lecturer in ordered}
    unknown = sorted(set(requested_source_ids) - set(by_id))
    if unknown:
        raise ReviewPackageError(f"Unknown lecturer_source_id values: {unknown!r}")
    return tuple(sorted((by_id[s] for s in set(requested_source_ids)), key=lambda l: l.source_id))


def resolve_canonical_ids(
    selected: Sequence[OfficialLecturer],
    canonical_rows: Iterable[tuple[str, UUID]],
) -> dict[str, UUID]:
    """Map every selected source_id to exactly one canonical Lecturer id."""
    found: dict[str, list[UUID]] = defaultdict(list)
    for source_id, lecturer_id in canonical_rows:
        found[source_id].append(lecturer_id)

    errors: list[str] = []
    resolved: dict[str, UUID] = {}
    for lecturer in selected:
        ids = found.get(lecturer.source_id, [])
        if len(ids) == 0:
            errors.append(f"{lecturer.source_id!r}: no canonical Lecturer row")
        elif len(ids) > 1:
            errors.append(f"{lecturer.source_id!r}: {len(ids)} canonical Lecturer rows")
        else:
            resolved[lecturer.source_id] = ids[0]
    if errors:
        raise ReviewPackageError(
            "Canonical lecturer resolution failed (exactly one required): " + "; ".join(errors)
        )
    return resolved


# ---------------------------------------------------------------------------
# DB-layer helpers (read-only SELECTs)
# ---------------------------------------------------------------------------


def resolve_canonical_lecturers_from_db(
    selected: Sequence[OfficialLecturer], session: Any
) -> dict[str, UUID]:
    from sqlalchemy import select

    from app.models.master_lecturer import Lecturer

    source_ids = [lecturer.source_id for lecturer in selected]
    rows = session.execute(
        select(Lecturer.repository_profile_url, Lecturer.id).where(
            Lecturer.repository_profile_url.in_(source_ids)
        )
    ).all()
    return resolve_canonical_ids(selected, ((row[0], row[1]) for row in rows))


def compute_publication_conflicts(
    known_publications: Iterable[Any],
    snapshots: Iterable[Any],
    publications: Iterable[Any],
) -> tuple[Any, ...]:
    """Conflict descriptors via the SAME reconciliation used by the enricher.

    Reuses the production reconciliation helper so there is no divergent copy
    of the rules.  Runs over whatever known publications are supplied, so the
    caller can cover lecturers that have zero generated candidates.
    """
    from app.services.matching.publication_evidence_enricher import (
        _reconcile_known_publications,
    )

    snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
    _reconciled, conflicts = _reconcile_known_publications(
        known_publications, snapshots_by_id, publications
    )
    return tuple(conflicts)


def generate_review_inputs(
    canonical_ids: Mapping[str, UUID], session: Any
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return (enriched selected candidates, full-selected-set conflicts).

    Candidates come from the CURRENT ``CandidateGenerator``; persisted
    candidate tables are never read.
    """
    from sqlalchemy import select

    from app.models.master_lecturer import LecturerKnownPublication, LecturerSourceSnapshot
    from app.models.publication import Publication
    from app.services.matching.candidate_generator import CandidateGenerator
    from app.services.matching.publication_evidence_enricher import PublicationEvidenceEnricher

    selected_ids = frozenset(canonical_ids.values())
    generated = CandidateGenerator(session).generate_all()
    selected_candidates = tuple(c for c in generated if c.lecturer_id in selected_ids)
    enriched = tuple(PublicationEvidenceEnricher(session).enrich(selected_candidates).candidates)

    known_publications = list(
        session.scalars(
            select(LecturerKnownPublication)
            .where(LecturerKnownPublication.lecturer_id.in_(selected_ids))
            .order_by(LecturerKnownPublication.id)
        )
    )
    snapshot_ids = {row.snapshot_id for row in known_publications}
    snapshots = (
        list(
            session.scalars(
                select(LecturerSourceSnapshot)
                .where(LecturerSourceSnapshot.id.in_(snapshot_ids))
                .order_by(LecturerSourceSnapshot.id)
            )
        )
        if snapshot_ids
        else []
    )
    publications = list(session.scalars(select(Publication).order_by(Publication.id)))
    conflicts = compute_publication_conflicts(known_publications, snapshots, publications)
    return enriched, conflicts


# ---------------------------------------------------------------------------
# Safe, explicit serialization (never dataclasses.asdict)
# ---------------------------------------------------------------------------


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _safe_name_evidence(candidate: Any) -> tuple[dict[str, str], ...]:
    items = [
        {
            "rule_id": ev.rule_id,
            "lecturer_source_value": ev.lecturer_source_value,
            "scopus_surface_type": ev.scopus_surface_type,
            "scopus_surface_value": ev.scopus_surface_value,
        }
        for ev in candidate.evidence
    ]
    items.sort(
        key=lambda i: (
            i["rule_id"],
            i["scopus_surface_type"],
            i["scopus_surface_value"],
            i["lecturer_source_value"],
        )
    )
    return tuple(items)


def _safe_publication_evidence(candidate: Any) -> tuple[dict[str, str | None], ...]:
    items = [
        {
            "rule_id": ev.rule_id,
            "reconciliation": ev.reconciliation,
            "canonical_publication_eid": ev.canonical_publication_eid,
            "canonical_publication_doi": ev.canonical_publication_doi,
            "canonical_publication_title": ev.canonical_publication_title,
        }
        for ev in candidate.publication_evidence
    ]
    items.sort(
        key=lambda i: (
            i["canonical_publication_eid"] or "",
            i["rule_id"] or "",
            i["canonical_publication_title"] or "",
        )
    )
    return tuple(items)


def build_review_lecturers(
    selected: Sequence[OfficialLecturer],
    canonical_ids: Mapping[str, UUID],
    enriched_candidates: Iterable[Any],
    conflicts: Iterable[Any],
) -> tuple[ReviewLecturer, ...]:
    """Combine selection, transient candidates and conflicts per lecturer."""
    candidates_by_lecturer: dict[UUID, list[Any]] = defaultdict(list)
    for candidate in enriched_candidates:
        candidates_by_lecturer[candidate.lecturer_id].append(candidate)

    conflicts_by_lecturer: dict[UUID, list[Any]] = defaultdict(list)
    for conflict in conflicts:
        conflicts_by_lecturer[conflict.lecturer_id].append(conflict)

    result: list[ReviewLecturer] = []
    for lecturer in sorted(selected, key=lambda l: l.source_id):
        lecturer_uuid = canonical_ids[lecturer.source_id]
        review_candidates = tuple(
            ReviewCandidate(
                scopus_id=c.scopus_id,
                preferred_name=c.preferred_name,
                name_evidence=_safe_name_evidence(c),
                publication_evidence=_safe_publication_evidence(c),
            )
            for c in sorted(candidates_by_lecturer.get(lecturer_uuid, ()), key=lambda c: c.scopus_id)
        )
        lecturer_conflicts = conflicts_by_lecturer.get(lecturer_uuid, [])
        result.append(
            ReviewLecturer(
                source_id=lecturer.source_id,
                institutional_email=lecturer.institutional_email,
                full_name=lecturer.full_name,
                candidates=review_candidates,
                publication_conflict_count=len(lecturer_conflicts),
                publication_conflict_reasons=tuple(sorted({c.reason for c in lecturer_conflicts})),
            )
        )
    return tuple(result)


def _csv_bytes(columns: Sequence[str], rows: Iterable[Sequence[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def render_candidate_review_csv(lecturers: Sequence[ReviewLecturer]) -> bytes:
    rows: list[list[str]] = []
    for lecturer in sorted(lecturers, key=lambda l: l.source_id):
        base = [lecturer.source_id, lecturer.institutional_email or "", lecturer.full_name]
        conflict_cells = [
            str(lecturer.publication_conflict_count),
            _json(list(lecturer.publication_conflict_reasons)),
        ]
        count = len(lecturer.candidates)
        if count == 0:
            rows.append(
                base + [SUGGESTION_NONE, "0", "", "", "", "", "", "", ""] + conflict_cells
            )
            continue
        for candidate in sorted(lecturer.candidates, key=lambda c: c.scopus_id):
            rows.append(
                base
                + [
                    SUGGESTION_CANDIDATE,
                    str(count),
                    candidate.scopus_id,
                    candidate.preferred_name,
                    _json(sorted({e["rule_id"] for e in candidate.name_evidence})),
                    _json(list(candidate.name_evidence)),
                    str(len(candidate.publication_evidence)),
                    _json(sorted({e["rule_id"] for e in candidate.publication_evidence})),
                    _json(list(candidate.publication_evidence)),
                ]
                + conflict_cells
            )
    return _csv_bytes(CANDIDATE_REVIEW_COLUMNS, rows)


def render_labeling_sheet_csv(lecturers: Sequence[ReviewLecturer]) -> bytes:
    """Blank human labeling sheet: identity/display fields only."""
    rows = [
        [l.source_id, l.institutional_email or "", l.full_name, "", "", "", "", ""]
        for l in sorted(lecturers, key=lambda l: l.source_id)
    ]
    return _csv_bytes(LABELING_SHEET_COLUMNS, rows)


def compute_counts(
    lecturers: Sequence[ReviewLecturer], conflicts: Sequence[Any]
) -> ReviewPackageCounts:
    candidate_counts = [len(l.candidates) for l in lecturers]
    return ReviewPackageCounts(
        selected_lecturer_count=len(lecturers),
        lecturers_with_candidates=sum(1 for n in candidate_counts if n >= 1),
        lecturers_without_candidates=sum(1 for n in candidate_counts if n == 0),
        candidate_pair_count=sum(candidate_counts),
        ambiguous_lecturer_count=sum(1 for n in candidate_counts if n > 1),
        publication_conflict_count=len(conflicts),
    )


def build_review_package(
    *,
    selected: Sequence[OfficialLecturer],
    canonical_ids: Mapping[str, UUID],
    enriched_candidates: Iterable[Any],
    conflicts: Iterable[Any],
    official_dataset_bytes: bytes,
    source_id_file_bytes: bytes | None,
    rule_set_id: str,
    rule_set_version: str,
    generated_at: datetime,
) -> ReviewPackage:
    selected_uuids = frozenset(canonical_ids[l.source_id] for l in selected)
    selected_conflicts = tuple(c for c in conflicts if c.lecturer_id in selected_uuids)
    lecturers = build_review_lecturers(
        selected, canonical_ids, tuple(enriched_candidates), selected_conflicts
    )
    counts = compute_counts(lecturers, selected_conflicts)

    review_csv = render_candidate_review_csv(lecturers)
    sheet_csv = render_labeling_sheet_csv(lecturers)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "official_lecturer_dataset_sha256": sha256_hex(official_dataset_bytes),
        "source_id_file_sha256": (
            sha256_hex(source_id_file_bytes) if source_id_file_bytes is not None else None
        ),
        "candidate_rule_set_id": rule_set_id,
        "candidate_rule_set_version": rule_set_version,
        "selected_lecturer_count": counts.selected_lecturer_count,
        "lecturers_with_candidates": counts.lecturers_with_candidates,
        "lecturers_without_candidates": counts.lecturers_without_candidates,
        "candidate_pair_count": counts.candidate_pair_count,
        "ambiguous_lecturer_count": counts.ambiguous_lecturer_count,
        "publication_conflict_count": counts.publication_conflict_count,
        "candidate_review_sha256": sha256_hex(review_csv),
        "reference_labeling_sheet_sha256": sha256_hex(sheet_csv),
    }
    manifest_json = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    return ReviewPackage(
        lecturers=lecturers,
        counts=counts,
        candidate_review_csv=review_csv,
        reference_labeling_sheet_csv=sheet_csv,
        manifest=manifest,
        manifest_json=manifest_json,
    )


__all__ = [
    "CANDIDATE_REVIEW_COLUMNS",
    "LABELING_SHEET_COLUMNS",
    "MANIFEST_FIELDS",
    "SUGGESTION_CANDIDATE",
    "SUGGESTION_NONE",
    "OfficialLecturer",
    "ReviewCandidate",
    "ReviewLecturer",
    "ReviewPackage",
    "ReviewPackageCounts",
    "ReviewPackageError",
    "build_review_package",
    "compute_publication_conflicts",
    "generate_review_inputs",
    "parse_official_lecturers",
    "parse_source_id_file",
    "resolve_canonical_ids",
    "resolve_canonical_lecturers_from_db",
    "select_lecturers",
    "sha256_hex",
]
