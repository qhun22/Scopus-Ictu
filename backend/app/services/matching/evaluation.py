"""Candidate-retrieval evaluation service — C3-A1.

This is a read-only research/evaluation utility.  It must never write to any
database table, create candidates, create identities, or create audit events.

Evaluation measures CANDIDATE RETRIEVAL QUALITY only:
- TP / FP / FN pairs
- Precision / Recall / F1 over generated candidate pairs
- Corpus-present vs corpus-missing target distinction

No ranking, scoring, thresholds, top-k, MRR, or NDCG are computed here.
Those require a separate approved slice with a production ranking contract.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_DECISIONS = frozenset({"MATCH", "NO_MATCH"})

_REQUIRED_COLUMNS = frozenset(
    {
        "lecturer_source_id",
        "institutional_email",
        "lecturer_full_name",
        "decision",
        "expected_scopus_id",
        "confirmation_source",
        "confirmed_at",
        "notes",
    }
)

_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # date
    r"(?:[T ]\d{2}:\d{2}(:\d{2})?)"  # time (seconds optional)
    r"(?:Z|[+-]\d{2}:?\d{2})?$"  # timezone optional
)


# ---------------------------------------------------------------------------
# Reference DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceDecision:
    """Parsed, validated single reference row."""

    lecturer_source_id: str
    institutional_email: str | None
    lecturer_full_name: str
    decision: str  # "MATCH" | "NO_MATCH"
    expected_scopus_id: str | None  # None for NO_MATCH
    confirmation_source: str
    confirmed_at: str
    notes: str


@dataclass(frozen=True)
class ReferenceRecord:
    """A validated reference row paired with its resolved lecturer display info."""

    decision: ReferenceDecision
    row_number: int


@dataclass(frozen=True)
class ReferenceValidationIssue:
    """A non-fatal warning about a reference row."""

    row_number: int | None
    field: str
    message: str


@dataclass(frozen=True)
class ReferenceValidationError(Exception):
    """Fatal structural error in the reference CSV."""

    message: str
    issues: tuple[ReferenceValidationIssue, ...]

    def __str__(self) -> str:
        lines = [self.message]
        for issue in self.issues:
            row_label = f"row {issue.row_number}" if issue.row_number else "header"
            lines.append(f"  [{row_label}] {issue.field}: {issue.message}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reference CSV parsing
# ---------------------------------------------------------------------------


def parse_reference_csv(content: str | bytes) -> tuple[ReferenceRecord, ...]:
    """Parse and validate a reference CSV string/bytes.

    Raises :class:`ReferenceValidationError` on any structural violation.
    Returns an immutable tuple of :class:`ReferenceRecord` on success.

    Enforces:
    - UTF-8
    - required columns present, no unknown columns
    - empty lecturer_source_id rejected
    - empty lecturer_full_name rejected
    - decision exactly MATCH or NO_MATCH
    - MATCH requires expected_scopus_id
    - NO_MATCH forbids expected_scopus_id
    - confirmation_source non-empty
    - confirmed_at non-empty and ISO-8601 parseable
    - duplicate lecturer_source_id rejected
    - duplicate MATCH expected_scopus_id rejected
    """
    if isinstance(content, bytes):
        text = content.decode("utf-8")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))

    # --- column validation --------------------------------------------------
    if reader.fieldnames is None:
        raise ReferenceValidationError(
            message="Reference CSV has no header row.",
            issues=(),
        )

    actual_columns = frozenset(f.strip() for f in reader.fieldnames)
    missing = _REQUIRED_COLUMNS - actual_columns
    extra = actual_columns - _REQUIRED_COLUMNS

    issues: list[ReferenceValidationIssue] = []
    if missing:
        issues.append(
            ReferenceValidationIssue(
                row_number=None,
                field="header",
                message=f"Missing required columns: {sorted(missing)}",
            )
        )
    if extra:
        issues.append(
            ReferenceValidationIssue(
                row_number=None,
                field="header",
                message=f"Unknown columns (not permitted): {sorted(extra)}",
            )
        )
    if issues:
        raise ReferenceValidationError(
            message="Reference CSV column contract violated.",
            issues=tuple(issues),
        )

    # --- row validation -----------------------------------------------------
    records: list[ReferenceRecord] = []
    seen_source_ids: dict[str, int] = {}
    seen_match_scopus_ids: dict[str, int] = {}
    row_issues: list[ReferenceValidationIssue] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items()}

        source_id = row.get("lecturer_source_id", "")
        full_name = row.get("lecturer_full_name", "")
        decision = row.get("decision", "")
        expected_scopus_id = row.get("expected_scopus_id", "") or None
        confirmation_source = row.get("confirmation_source", "")
        confirmed_at_raw = row.get("confirmed_at", "")
        raw_email = row.get("institutional_email", "") or None
        notes = row.get("notes", "")

        ok = True

        if not source_id:
            row_issues.append(
                ReferenceValidationIssue(row_number, "lecturer_source_id", "Must not be empty.")
            )
            ok = False
        if not full_name:
            row_issues.append(
                ReferenceValidationIssue(row_number, "lecturer_full_name", "Must not be empty.")
            )
            ok = False
        if decision not in _VALID_DECISIONS:
            row_issues.append(
                ReferenceValidationIssue(
                    row_number, "decision",
                    f"Must be MATCH or NO_MATCH, got: {decision!r}"
                )
            )
            ok = False
        else:
            if decision == "MATCH" and not expected_scopus_id:
                row_issues.append(
                    ReferenceValidationIssue(
                        row_number, "expected_scopus_id",
                        "MATCH row requires a non-empty expected_scopus_id."
                    )
                )
                ok = False
            if decision == "NO_MATCH" and expected_scopus_id:
                row_issues.append(
                    ReferenceValidationIssue(
                        row_number, "expected_scopus_id",
                        "NO_MATCH row must have an empty expected_scopus_id."
                    )
                )
                ok = False

        if not confirmation_source:
            row_issues.append(
                ReferenceValidationIssue(row_number, "confirmation_source", "Must not be empty.")
            )
            ok = False

        if not confirmed_at_raw:
            row_issues.append(
                ReferenceValidationIssue(row_number, "confirmed_at", "Must not be empty.")
            )
            ok = False
        elif not _ISO_DATETIME_RE.match(confirmed_at_raw):
            row_issues.append(
                ReferenceValidationIssue(
                    row_number, "confirmed_at",
                    f"Must be ISO-8601 date/datetime, got: {confirmed_at_raw!r}"
                )
            )
            ok = False

        # duplicate checks (only if source_id is non-empty)
        if source_id and source_id in seen_source_ids:
            row_issues.append(
                ReferenceValidationIssue(
                    row_number, "lecturer_source_id",
                    f"Duplicate: already seen at row {seen_source_ids[source_id]}."
                )
            )
            ok = False
        elif source_id:
            seen_source_ids[source_id] = row_number

        if decision == "MATCH" and expected_scopus_id:
            if expected_scopus_id in seen_match_scopus_ids:
                row_issues.append(
                    ReferenceValidationIssue(
                        row_number, "expected_scopus_id",
                        f"Duplicate MATCH Scopus ID: already used at row "
                        f"{seen_match_scopus_ids[expected_scopus_id]}."
                    )
                )
                ok = False
            else:
                seen_match_scopus_ids[expected_scopus_id] = row_number

        if ok:
            records.append(
                ReferenceRecord(
                    decision=ReferenceDecision(
                        lecturer_source_id=source_id,
                        institutional_email=raw_email,
                        lecturer_full_name=full_name,
                        decision=decision,
                        expected_scopus_id=expected_scopus_id,
                        confirmation_source=confirmation_source,
                        confirmed_at=confirmed_at_raw,
                        notes=notes,
                    ),
                    row_number=row_number,
                )
            )

    if row_issues:
        raise ReferenceValidationError(
            message="Reference CSV row validation failed.",
            issues=tuple(row_issues),
        )

    return tuple(records)


# ---------------------------------------------------------------------------
# Official lecturer dataset cross-check
# ---------------------------------------------------------------------------


def _norm_email(email: str) -> str:
    return email.strip().casefold()


def _norm_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def validate_against_lecturer_dataset(
    records: tuple[ReferenceRecord, ...],
    lecturer_dataset_path: Path,
) -> None:
    """Cross-check reference rows against the official ICTU lecturer dataset.

    Raises :class:`ReferenceValidationError` if any mismatch is found.
    Does NOT require all 410 lecturers to be present (subset is allowed).
    """
    raw = json.loads(lecturer_dataset_path.read_text(encoding="utf-8"))
    lecturers_by_source_id: dict[str, dict] = {
        lec["source_id"]: lec for lec in raw.get("lecturers", [])
    }

    issues: list[ReferenceValidationIssue] = []
    for ref in records:
        d = ref.decision
        official = lecturers_by_source_id.get(d.lecturer_source_id)
        if official is None:
            issues.append(
                ReferenceValidationIssue(
                    ref.row_number,
                    "lecturer_source_id",
                    f"Not found in official lecturer dataset: {d.lecturer_source_id!r}",
                )
            )
            continue

        # name cross-check
        official_name = official.get("full_name", "")
        if _norm_name(d.lecturer_full_name) != _norm_name(official_name):
            issues.append(
                ReferenceValidationIssue(
                    ref.row_number,
                    "lecturer_full_name",
                    f"Name mismatch: reference={d.lecturer_full_name!r} "
                    f"official={official_name!r}",
                )
            )

        # email cross-check (only when provided)
        if d.institutional_email:
            official_email = official.get("institutional_email", "") or ""
            if official_email and _norm_email(d.institutional_email) != _norm_email(official_email):
                issues.append(
                    ReferenceValidationIssue(
                        ref.row_number,
                        "institutional_email",
                        f"Email mismatch: reference={d.institutional_email!r} "
                        f"official={official_email!r}",
                    )
                )

    if issues:
        raise ReferenceValidationError(
            message="Reference CSV cross-check against official lecturer dataset failed.",
            issues=tuple(issues),
        )


# ---------------------------------------------------------------------------
# Evaluation input types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EvaluationLecturer:
    """Resolved canonical lecturer for a reference row."""

    db_id: UUID
    source_id: str  # repository_profile_url
    full_name: str
    email: str | None


@dataclass(frozen=True)
class _GeneratedPair:
    """One generated candidate pair (lecturer ↔ Scopus author)."""

    lecturer_db_id: UUID
    scopus_id: str
    rule_ids: tuple[str, ...]
    has_publication_evidence: bool


# ---------------------------------------------------------------------------
# Case-level output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceCaseResult:
    """Per-reference-row evaluation result."""

    lecturer_source_id: str
    institutional_email: str | None
    lecturer_full_name: str
    decision: str  # "MATCH" | "NO_MATCH"
    expected_scopus_id: str | None
    target_in_scopus_corpus: bool | None  # None for NO_MATCH

    generated_candidate_count: int
    generated_scopus_ids: tuple[str, ...]  # sorted lexicographically

    # MATCH only: did the expected Scopus ID appear in generated candidates?
    match_found: bool | None  # None for NO_MATCH

    expected_candidate_rule_ids: tuple[str, ...]  # sorted; empty if not found
    expected_candidate_has_publication_evidence: bool | None  # None if not found or NO_MATCH


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateRetrievalMetrics:
    """Aggregate retrieval-quality metrics over all reference rows."""

    reference_count: int
    match_reference_count: int
    no_match_reference_count: int

    generated_pair_count: int

    true_positive_pairs: int
    false_positive_pairs: int
    false_negative_pairs: int

    candidate_pair_precision: float
    candidate_pair_recall: float
    candidate_pair_f1: float

    match_hit_count: int
    match_miss_count: int

    single_candidate_match_count: int  # MATCH lecturers with exactly 1 candidate generated
    ambiguous_match_count: int  # MATCH lecturers with >1 candidate generated (correct one included)

    no_match_with_candidate_count: int
    no_match_without_candidate_count: int

    mean_candidates_per_reference: float

    corpus_present_match_count: int
    corpus_missing_match_count: int

    end_to_end_candidate_recall: float
    eligible_candidate_recall: float


@dataclass(frozen=True)
class CandidateRetrievalEvaluation:
    """Full evaluation result."""

    metrics: CandidateRetrievalMetrics
    cases: tuple[ReferenceCaseResult, ...]  # sorted by lecturer_source_id


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------


def evaluate_candidate_retrieval(
    reference_records: tuple[ReferenceRecord, ...],
    resolved_lecturers: dict[str, _EvaluationLecturer],
    scopus_corpus_ids: frozenset[str],
    generated_pairs_by_lecturer_db_id: dict[UUID, tuple[_GeneratedPair, ...]],
) -> CandidateRetrievalEvaluation:
    """Compute candidate-retrieval evaluation.

    Arguments:
        reference_records: validated reference rows.
        resolved_lecturers: mapping from lecturer_source_id ->
            _EvaluationLecturer (from DB).
        scopus_corpus_ids: all scopus_id values present in the DB corpus.
        generated_pairs_by_lecturer_db_id: generated pairs keyed by
            lecturer UUID.

    No DB writes are performed here.
    """
    cases: list[ReferenceCaseResult] = []

    tp = 0
    fp = 0
    fn = 0
    total_generated = 0

    match_hit_count = 0
    match_miss_count = 0
    single_candidate_match_count = 0
    ambiguous_match_count = 0
    no_match_with = 0
    no_match_without = 0

    corpus_present = 0
    corpus_missing = 0
    eligible_tp = 0
    eligible_total = 0

    for ref in reference_records:
        d = ref.decision
        lec = resolved_lecturers.get(d.lecturer_source_id)
        if lec is None:
            # Input error: reference row has no resolved DB lecturer.
            # Include a minimal case but do not count it in metrics.
            cases.append(
                ReferenceCaseResult(
                    lecturer_source_id=d.lecturer_source_id,
                    institutional_email=d.institutional_email,
                    lecturer_full_name=d.lecturer_full_name,
                    decision=d.decision,
                    expected_scopus_id=d.expected_scopus_id,
                    target_in_scopus_corpus=None,
                    generated_candidate_count=0,
                    generated_scopus_ids=(),
                    match_found=None,
                    expected_candidate_rule_ids=(),
                    expected_candidate_has_publication_evidence=None,
                )
            )
            continue

        pairs: tuple[_GeneratedPair, ...] = generated_pairs_by_lecturer_db_id.get(lec.db_id, ())
        generated_ids = tuple(sorted(p.scopus_id for p in pairs))
        total_generated += len(pairs)

        if d.decision == "MATCH":
            expected = d.expected_scopus_id
            assert expected is not None

            in_corpus = expected in scopus_corpus_ids
            if in_corpus:
                corpus_present += 1
                eligible_total += 1
            else:
                corpus_missing += 1

            # Find the expected pair in generated pairs
            matched_pair = next((p for p in pairs if p.scopus_id == expected), None)
            found = matched_pair is not None

            if found:
                tp += 1
                match_hit_count += 1
                if in_corpus:
                    eligible_tp += 1
                # FP: any other generated pair for this lecturer
                fp += len(pairs) - 1
                if len(pairs) == 1:
                    single_candidate_match_count += 1
                else:
                    ambiguous_match_count += 1
            else:
                fn += 1
                match_miss_count += 1
                fp += len(pairs)  # all generated pairs are FP

            rule_ids = (
                tuple(sorted(matched_pair.rule_ids)) if matched_pair else ()
            )
            has_pub_evidence = (
                matched_pair.has_publication_evidence if matched_pair else None
            )

            cases.append(
                ReferenceCaseResult(
                    lecturer_source_id=d.lecturer_source_id,
                    institutional_email=d.institutional_email,
                    lecturer_full_name=d.lecturer_full_name,
                    decision="MATCH",
                    expected_scopus_id=expected,
                    target_in_scopus_corpus=in_corpus,
                    generated_candidate_count=len(pairs),
                    generated_scopus_ids=generated_ids,
                    match_found=found,
                    expected_candidate_rule_ids=rule_ids,
                    expected_candidate_has_publication_evidence=has_pub_evidence,
                )
            )

        else:  # NO_MATCH
            fp += len(pairs)
            if len(pairs) > 0:
                no_match_with += 1
            else:
                no_match_without += 1

            cases.append(
                ReferenceCaseResult(
                    lecturer_source_id=d.lecturer_source_id,
                    institutional_email=d.institutional_email,
                    lecturer_full_name=d.lecturer_full_name,
                    decision="NO_MATCH",
                    expected_scopus_id=None,
                    target_in_scopus_corpus=None,
                    generated_candidate_count=len(pairs),
                    generated_scopus_ids=generated_ids,
                    match_found=None,
                    expected_candidate_rule_ids=(),
                    expected_candidate_has_publication_evidence=None,
                )
            )

    # --- aggregate metrics --------------------------------------------------
    precision_denom = tp + fp
    recall_denom = tp + fn
    precision = tp / precision_denom if precision_denom > 0 else 0.0
    recall = tp / recall_denom if recall_denom > 0 else 0.0
    f1_denom = precision + recall
    f1 = 2 * precision * recall / f1_denom if f1_denom > 0 else 0.0

    match_ref_count = sum(1 for r in reference_records if r.decision.decision == "MATCH")
    no_match_ref_count = len(reference_records) - match_ref_count

    end_to_end_recall = match_hit_count / match_ref_count if match_ref_count > 0 else 0.0
    eligible_recall = eligible_tp / eligible_total if eligible_total > 0 else 0.0

    mean_cands = total_generated / len(reference_records) if reference_records else 0.0

    metrics = CandidateRetrievalMetrics(
        reference_count=len(reference_records),
        match_reference_count=match_ref_count,
        no_match_reference_count=no_match_ref_count,
        generated_pair_count=total_generated,
        true_positive_pairs=tp,
        false_positive_pairs=fp,
        false_negative_pairs=fn,
        candidate_pair_precision=round(precision, 6),
        candidate_pair_recall=round(recall, 6),
        candidate_pair_f1=round(f1, 6),
        match_hit_count=match_hit_count,
        match_miss_count=match_miss_count,
        single_candidate_match_count=single_candidate_match_count,
        ambiguous_match_count=ambiguous_match_count,
        no_match_with_candidate_count=no_match_with,
        no_match_without_candidate_count=no_match_without,
        mean_candidates_per_reference=round(mean_cands, 4),
        corpus_present_match_count=corpus_present,
        corpus_missing_match_count=corpus_missing,
        end_to_end_candidate_recall=round(end_to_end_recall, 6),
        eligible_candidate_recall=round(eligible_recall, 6),
    )

    cases_sorted = tuple(sorted(cases, key=lambda c: c.lecturer_source_id))
    return CandidateRetrievalEvaluation(metrics=metrics, cases=cases_sorted)


# ---------------------------------------------------------------------------
# DB-layer helpers (used by evaluate_matching_reference.py CLI)
# ---------------------------------------------------------------------------


def resolve_lecturers_from_db(
    reference_records: tuple[ReferenceRecord, ...],
    session: Any,
) -> tuple[dict[str, "_EvaluationLecturer"], list[str]]:
    """Resolve DB Lecturer rows for each reference record.

    Returns (resolved_map, errors).
    Uses Lecturer.repository_profile_url == lecturer_source_id.
    Does NOT write to the database.
    """
    from sqlalchemy import select as sa_select

    from app.models.master_lecturer import Lecturer as _Lecturer

    resolved: dict[str, _EvaluationLecturer] = {}
    errors: list[str] = []

    for ref in reference_records:
        source_id = ref.decision.lecturer_source_id
        rows = session.execute(
            sa_select(_Lecturer).where(
                _Lecturer.repository_profile_url == source_id
            )
        ).scalars().all()

        if len(rows) == 0:
            errors.append(
                f"lecturer_source_id={source_id!r}: no Lecturer row with "
                f"matching repository_profile_url found."
            )
        elif len(rows) > 1:
            errors.append(
                f"lecturer_source_id={source_id!r}: multiple Lecturer rows found "
                f"({len(rows)}), expected exactly one."
            )
        else:
            lec = rows[0]
            resolved[source_id] = _EvaluationLecturer(
                db_id=lec.id,
                source_id=source_id,
                full_name=lec.full_name,
                email=lec.email,
            )

    return resolved, errors


def load_scopus_corpus_ids(session: Any) -> frozenset[str]:
    """Return all scopus_id values from the canonical ScopusAuthor corpus.

    Read-only SELECT.
    """
    from sqlalchemy import select as sa_select

    from app.models.publication import ScopusAuthor

    rows = session.execute(sa_select(ScopusAuthor.scopus_id)).scalars().all()
    return frozenset(rows)


def load_generated_pairs(
    lecturer_db_ids: frozenset[UUID],
    session: Any,
) -> dict[UUID, tuple[_GeneratedPair, ...]]:
    """Load generated candidate pairs for a set of lecturer DB IDs.

    Uses only the latest-COMPLETED observation per candidate, consistent with
    the review queue convention. Read-only SELECT.
    """
    from sqlalchemy import select as sa_select

    from app.models.candidate import (
        LecturerScopusCandidate as _DBCandidate,
        LecturerScopusCandidateEvidence,
        LecturerScopusCandidateObservation,
        CandidateGenerationRun,
    )
    from app.models.publication import ScopusAuthor

    if not lecturer_db_ids:
        return {}

    # Load all PENDING candidates for these lecturers
    candidate_rows = session.execute(
        sa_select(_DBCandidate, ScopusAuthor.scopus_id)
        .join(ScopusAuthor, ScopusAuthor.id == _DBCandidate.scopus_author_id)
        .where(_DBCandidate.lecturer_id.in_(lecturer_db_ids))
        .where(_DBCandidate.status == "PENDING")
    ).all()

    if not candidate_rows:
        return {lid: () for lid in lecturer_db_ids}

    candidate_ids = [row[0].id for row in candidate_rows]
    candidate_map = {row[0].id: (row[0], row[1]) for row in candidate_rows}

    # Load evidence for those candidates (from any observation — for rule listing)
    evidence_rows = session.execute(
        sa_select(
            LecturerScopusCandidateEvidence.observation_id,
            LecturerScopusCandidateEvidence.rule_id,
            LecturerScopusCandidateEvidence.evidence_kind,
            LecturerScopusCandidateObservation.candidate_id,
        )
        .join(
            LecturerScopusCandidateObservation,
            LecturerScopusCandidateObservation.id
            == LecturerScopusCandidateEvidence.observation_id,
        )
        .where(LecturerScopusCandidateObservation.candidate_id.in_(candidate_ids))
    ).all()

    # Build per-candidate rule + publication evidence sets
    rules_by_candidate: dict[UUID, set[str]] = {}
    pub_evidence_by_candidate: dict[UUID, bool] = {}
    for ev_row in evidence_rows:
        cid = ev_row.candidate_id
        if cid not in rules_by_candidate:
            rules_by_candidate[cid] = set()
            pub_evidence_by_candidate[cid] = False
        rules_by_candidate[cid].add(ev_row.rule_id)
        if ev_row.evidence_kind == "PUBLICATION":
            pub_evidence_by_candidate[cid] = True

    result: dict[UUID, list[_GeneratedPair]] = {lid: [] for lid in lecturer_db_ids}
    for cand_row, scopus_id in candidate_rows:
        cand = cand_row
        rules = tuple(sorted(rules_by_candidate.get(cand.id, set())))
        has_pub = pub_evidence_by_candidate.get(cand.id, False)
        pair = _GeneratedPair(
            lecturer_db_id=cand.lecturer_id,
            scopus_id=scopus_id,
            rule_ids=rules,
            has_publication_evidence=has_pub,
        )
        result[cand.lecturer_id].append(pair)

    return {lid: tuple(pairs) for lid, pairs in result.items()}


__all__ = [
    "ReferenceDecision",
    "ReferenceRecord",
    "ReferenceValidationIssue",
    "ReferenceValidationError",
    "ReferenceCaseResult",
    "CandidateRetrievalMetrics",
    "CandidateRetrievalEvaluation",
    "parse_reference_csv",
    "validate_against_lecturer_dataset",
    "evaluate_candidate_retrieval",
    "resolve_lecturers_from_db",
    "load_scopus_corpus_ids",
    "load_generated_pairs",
    "_EvaluationLecturer",
    "_GeneratedPair",
]
