"""Persistence for deterministic pre-identity candidate observations.

The writer accepts already-generated and already-enriched candidates.  It does
not run matching rules, score, rank, review, or create identity rows.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.models.publication import (
    Publication,
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate


SOURCE_STATE_SCHEMA_VERSION = 1
CANDIDATE_RULE_SET_ID = "M2.7A_CANDIDATE_GENERATOR"
CANDIDATE_RULE_SET_VERSION = "M2.7A-2"
PUBLICATION_RULE_SET_ID = "M2.7A_PUBLICATION_ENRICHMENT"
PUBLICATION_RULE_SET_VERSION = "M2.7A-5"
GENERATION_RULE_SET_ID = "M2.7A_CANDIDATE_EVIDENCE"
GENERATION_RULE_SET_VERSION = "M2.7A-2+M2.7A-5"

CANDIDATE_RULE_IDS = (
    "RULE_EXACT_N0",
    "RULE_TITLE_STRIPPED_N0",
    "RULE_TITLE_STRIPPED_N2",
    "RULE_TITLE_STRIPPED_N2_FORMAT",
)
PUBLICATION_RULE_IDS = (
    "RULE_KNOWN_PUBLICATION_DOI_EXACT",
    "RULE_KNOWN_PUBLICATION_TITLE_EXACT",
)


class GenerationRunConflict(ValueError):
    """The requested run identity was previously used for another execution."""


class GenerationRunStateError(RuntimeError):
    """A run cannot safely transition through the requested lifecycle."""


@dataclass(frozen=True, slots=True)
class GenerationRunSpec:
    """Stable caller-supplied identity and metadata for one generation run."""

    run_id: UUID
    rule_set_id: str = GENERATION_RULE_SET_ID
    rule_set_version: str = GENERATION_RULE_SET_VERSION
    source_state: Mapping[str, Any] | None = None
    started_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CandidatePersistenceResult:
    """Durable counts and lifecycle result returned by the writer."""

    run_id: UUID
    run_status: str
    candidate_roots: int
    observations: int
    evidence: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class _PreparedEvidence:
    evidence_kind: str
    rule_id: str
    rule_version: str
    payload: dict[str, Any]
    source_refs: list[dict[str, Any]]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _PreparedCandidate:
    candidate: EnrichedLecturerScopusCandidate
    snapshot: dict[str, Any]
    observation_hash: str
    evidence: tuple[_PreparedEvidence, ...]


def _json_value(value: Any) -> Any:
    """Convert supported domain values into deterministic JSON values."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value without volatile ordering."""
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    """Return the lowercase SHA-256 of canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fingerprint_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = sorted((_json_value(row) for row in rows), key=canonical_json)
    return {"count": len(normalized), "sha256": sha256_json(normalized)}


def build_source_state(
    session: Session,
    *,
    candidate_rule_set_id: str = CANDIDATE_RULE_SET_ID,
    candidate_rule_set_version: str = CANDIDATE_RULE_SET_VERSION,
    publication_rule_set_id: str = PUBLICATION_RULE_SET_ID,
    publication_rule_set_version: str = PUBLICATION_RULE_SET_VERSION,
) -> dict[str, Any]:
    """Build the compact, deterministic source-state contract for a run.

    Only counts and fingerprints are persisted; raw rows, filesystem paths,
    credentials, and tokens are never copied into ``source_state``.
    """

    lecturers = list(session.scalars(select(Lecturer).order_by(Lecturer.id)))
    authors = list(session.scalars(select(ScopusAuthor).order_by(ScopusAuthor.id)))
    variants = list(
        session.scalars(
            select(ScopusAuthorNameVariant).order_by(ScopusAuthorNameVariant.id)
        )
    )
    snapshots = list(
        session.scalars(select(LecturerSourceSnapshot).order_by(LecturerSourceSnapshot.id))
    )
    known_publications = list(
        session.scalars(select(LecturerKnownPublication).order_by(LecturerKnownPublication.id))
    )
    publications = list(session.scalars(select(Publication).order_by(Publication.id)))
    publication_authors = list(
        session.scalars(select(PublicationAuthor).order_by(PublicationAuthor.id))
    )

    return {
        "schema_version": SOURCE_STATE_SCHEMA_VERSION,
        "rules": {
            "candidate_generator": {
                "rule_set_id": candidate_rule_set_id,
                "rule_set_version": candidate_rule_set_version,
                "rule_ids": list(CANDIDATE_RULE_IDS),
            },
            "publication_enrichment": {
                "rule_set_id": publication_rule_set_id,
                "rule_set_version": publication_rule_set_version,
                "rule_ids": list(PUBLICATION_RULE_IDS),
            },
        },
        "inputs": {
            "lecturers": _fingerprint_rows(
                {
                    "id": row.id,
                    "full_name": row.full_name,
                    "full_name_normalized": row.full_name_normalized,
                    "version": row.version,
                    "is_active": row.is_active,
                }
                for row in lecturers
            ),
            "scopus_authors": _fingerprint_rows(
                {
                    "id": row.id,
                    "scopus_id": row.scopus_id,
                    "preferred_name": row.preferred_name,
                }
                for row in authors
            ),
            "scopus_author_name_variants": _fingerprint_rows(
                {
                    "id": row.id,
                    "scopus_author_id": row.scopus_author_id,
                    "variant_type": row.variant_type,
                    "variant_name": row.variant_name,
                    "variant_name_normalized": row.variant_name_normalized,
                }
                for row in variants
            ),
            "lecturer_source_snapshots": _fingerprint_rows(
                {
                    "id": row.id,
                    "lecturer_id": row.lecturer_id,
                    "source_system": row.source_system,
                    "source_url": row.source_url,
                    "snapshot_hash": row.snapshot_hash,
                    "parser_version": row.parser_version,
                    "validation_status": row.validation_status,
                    "fetched_at": row.fetched_at,
                }
                for row in snapshots
            ),
            "lecturer_known_publications": _fingerprint_rows(
                {
                    "id": row.id,
                    "lecturer_id": row.lecturer_id,
                    "snapshot_id": row.snapshot_id,
                    "title_normalized": row.title_normalized,
                    "doi_normalized": row.doi_normalized,
                    "published_year": row.published_year,
                }
                for row in known_publications
            ),
            "publications": _fingerprint_rows(
                {
                    "id": row.id,
                    "eid": row.eid,
                    "doi": row.doi,
                    "title_normalized": row.title_normalized,
                    "version": row.version,
                }
                for row in publications
            ),
            "publication_authors": _fingerprint_rows(
                {
                    "id": row.id,
                    "publication_id": row.publication_id,
                    "scopus_author_id": row.scopus_author_id,
                    "author_order": row.author_order,
                }
                for row in publication_authors
            ),
        },
    }


def _validate_source_state(source_state: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(source_state, Mapping):
        raise ValueError("source_state must be a JSON object")
    if source_state.get("schema_version") != SOURCE_STATE_SCHEMA_VERSION:
        raise ValueError("unsupported source_state schema version")
    for key in ("rules", "inputs"):
        if not isinstance(source_state.get(key), Mapping):
            raise ValueError(f"source_state.{key} must be an object")
    return dict(_json_value(source_state))


def _rule_versions(source_state: Mapping[str, Any]) -> tuple[str, str]:
    rules = source_state["rules"]
    candidate_rules = rules["candidate_generator"]
    publication_rules = rules["publication_enrichment"]
    candidate_version = candidate_rules.get("rule_set_version")
    publication_version = publication_rules.get("rule_set_version")
    if not isinstance(candidate_version, str) or not candidate_version.strip():
        raise ValueError("source_state.rules.candidate_generator.rule_set_version is required")
    if not isinstance(publication_version, str) or not publication_version.strip():
        raise ValueError(
            "source_state.rules.publication_enrichment.rule_set_version is required"
        )
    return candidate_version, publication_version


def _name_evidence(
    candidate: EnrichedLecturerScopusCandidate,
    rule_version: str,
) -> list[dict[str, Any]]:
    rows = []
    for evidence in candidate.name_evidence:
        rows.append(
            {
                "rule_id": evidence.rule_id,
                "rule_version": rule_version,
                "payload": {
                    "lecturer_source_value": evidence.lecturer_source_value,
                    "lecturer_comparison_value": evidence.lecturer_comparison_value,
                    "scopus_surface_type": evidence.scopus_surface_type,
                    "scopus_surface_value": evidence.scopus_surface_value,
                    "scopus_comparison_value": evidence.scopus_comparison_value,
                },
                "source_refs": [],
            }
        )
    return rows


def _publication_evidence(
    candidate: EnrichedLecturerScopusCandidate,
    rule_version: str,
) -> list[dict[str, Any]]:
    rows = []
    for evidence in candidate.publication_evidence:
        rows.append(
            {
                "rule_id": evidence.rule_id,
                "rule_version": rule_version,
                "payload": {
                    "lecturer_id": evidence.lecturer_id,
                    "candidate_scopus_author_id": evidence.candidate_scopus_author_id,
                    "known_publication_doi_normalized": evidence.known_publication_doi_normalized,
                    "known_publication_title_normalized": evidence.known_publication_title_normalized,
                    "canonical_publication_eid": evidence.canonical_publication_eid,
                    "canonical_publication_doi": evidence.canonical_publication_doi,
                    "canonical_publication_title": evidence.canonical_publication_title,
                    "reconciliation": evidence.reconciliation,
                },
                "source_refs": [
                    {
                        "kind": "lecturer_known_publication",
                        "id": evidence.known_publication_id,
                    },
                    {
                        "kind": "lecturer_source_snapshot",
                        "id": evidence.lecturer_snapshot_id,
                    },
                    {
                        "kind": "publication",
                        "id": evidence.canonical_publication_id,
                    },
                    {
                        "kind": "publication_author",
                        "scopus_author_id": evidence.candidate_scopus_author_id,
                        "publication_id": evidence.canonical_publication_id,
                    },
                ],
            }
        )
    return rows


def _prepare_candidate(
    candidate: EnrichedLecturerScopusCandidate,
    candidate_rule_version: str,
    publication_rule_version: str,
) -> _PreparedCandidate:
    raw_evidence = [
        ("NAME", item) for item in _name_evidence(candidate, candidate_rule_version)
    ] + [
        ("PUBLICATION", item)
        for item in _publication_evidence(candidate, publication_rule_version)
    ]

    prepared = []
    for evidence_kind, descriptor in raw_evidence:
        payload = dict(_json_value(descriptor["payload"]))
        source_refs = list(_json_value(descriptor["source_refs"]))
        fingerprint = sha256_json(
            {
                "evidence_kind": evidence_kind,
                "rule_id": descriptor["rule_id"],
                "rule_version": descriptor["rule_version"],
                "payload": payload,
                "source_refs": source_refs,
            }
        )
        prepared.append(
            _PreparedEvidence(
                evidence_kind=evidence_kind,
                rule_id=descriptor["rule_id"],
                rule_version=descriptor["rule_version"],
                payload=payload,
                source_refs=source_refs,
                fingerprint=fingerprint,
            )
        )

    prepared.sort(key=lambda item: (item.evidence_kind, item.rule_id, item.fingerprint))
    snapshot = _json_value(
        {
            "schema_version": 1,
            "lecturer_id": candidate.lecturer_id,
            "scopus_author_id": candidate.scopus_author_id,
            "scopus_id": candidate.scopus_id,
            "preferred_name": candidate.preferred_name,
            "evidence": [
                {
                    "evidence_kind": item.evidence_kind,
                    "rule_id": item.rule_id,
                    "rule_version": item.rule_version,
                    "payload": item.payload,
                    "source_refs": item.source_refs,
                    "evidence_fingerprint": item.fingerprint,
                }
                for item in prepared
            ],
        }
    )
    observation_hash = sha256_json(snapshot)
    return _PreparedCandidate(candidate, snapshot, observation_hash, tuple(prepared))


class CandidatePersistenceService:
    """Persist deterministic candidate output without identity side effects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def persist_generation(
        self,
        spec: GenerationRunSpec,
        candidates: Iterable[EnrichedLecturerScopusCandidate],
    ) -> CandidatePersistenceResult:
        source_state = _validate_source_state(spec.source_state)
        prepared = tuple(
            _prepare_candidate(candidate, *_rule_versions(source_state))
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    str(item.lecturer_id),
                    str(item.scopus_author_id),
                ),
            )
        )
        self._start_or_resume_run(spec, source_state)
        try:
            return self._persist_started_run(spec.run_id, prepared)
        except Exception:
            self._mark_run_failed(spec.run_id)
            raise

    def _start_or_resume_run(
        self,
        spec: GenerationRunSpec,
        source_state: dict[str, Any],
    ) -> None:
        now = spec.started_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        with self._session.begin():
            run = self._session.get(
                CandidateGenerationRun,
                spec.run_id,
                with_for_update=True,
            )
            if run is None:
                self._session.add(
                    CandidateGenerationRun(
                        id=spec.run_id,
                        rule_set_id=spec.rule_set_id,
                        rule_set_version=spec.rule_set_version,
                        source_state=source_state,
                        started_at=now.astimezone(UTC),
                        status="RUNNING",
                    )
                )
                return

            if (
                run.rule_set_id != spec.rule_set_id
                or run.rule_set_version != spec.rule_set_version
                or run.source_state != source_state
            ):
                raise GenerationRunConflict(
                    f"generation run {spec.run_id} was created with different metadata"
                )
            if run.status == "FAILED":
                run.status = "RUNNING"
                run.completed_at = None
            elif run.status not in {"RUNNING", "COMPLETED"}:
                raise GenerationRunStateError(
                    f"generation run {spec.run_id} has unsupported status {run.status}"
                )

    def _persist_started_run(
        self,
        run_id: UUID,
        prepared: Sequence[_PreparedCandidate],
    ) -> CandidatePersistenceResult:
        with self._session.begin():
            run = self._session.get(
                CandidateGenerationRun,
                run_id,
                with_for_update=True,
            )
            if run is None:
                raise GenerationRunStateError(f"generation run {run_id} does not exist")

            if run.status == "COMPLETED":
                self._verify_existing_run(run_id, prepared)
                return self._result_for_run(run_id, idempotent_replay=True)
            if run.status != "RUNNING":
                raise GenerationRunStateError(
                    f"generation run {run_id} is not RUNNING: {run.status}"
                )

            observation_count = 0
            evidence_count = 0
            for item in prepared:
                root = self._get_or_create_root(item.candidate, run.started_at)
                observation = self._session.scalar(
                    select(LecturerScopusCandidateObservation)
                    .where(
                        LecturerScopusCandidateObservation.candidate_id == root.id,
                        LecturerScopusCandidateObservation.generation_run_id == run_id,
                    )
                    .with_for_update()
                )
                if observation is not None:
                    if observation.observation_hash != item.observation_hash:
                        raise GenerationRunConflict(
                            f"observation for candidate {root.id} has different content"
                        )
                    self._verify_observation_evidence(observation.id, item.evidence)
                    continue

                observation = LecturerScopusCandidateObservation(
                    candidate_id=root.id,
                    generation_run_id=run_id,
                    observed_at=run.started_at,
                    candidate_snapshot=item.snapshot,
                    observation_hash=item.observation_hash,
                )
                self._session.add(observation)
                self._session.flush()
                self._session.add_all(
                    LecturerScopusCandidateEvidence(
                        observation_id=observation.id,
                        evidence_kind=evidence.evidence_kind,
                        rule_id=evidence.rule_id,
                        rule_version=evidence.rule_version,
                        payload=evidence.payload,
                        source_refs=evidence.source_refs,
                        evidence_fingerprint=evidence.fingerprint,
                    )
                    for evidence in item.evidence
                )
                root.last_seen_at = run.started_at
                observation_count += 1
                evidence_count += len(item.evidence)

            run.status = "COMPLETED"
            run.completed_at = datetime.now(UTC)
            self._session.flush()
            result = self._result_for_run(
                run_id,
                idempotent_replay=False,
                candidate_roots=len(prepared),
                observations=observation_count,
                evidence=evidence_count,
            )
            return result

    def _get_or_create_root(
        self,
        candidate: EnrichedLecturerScopusCandidate,
        observed_at: datetime,
    ) -> LecturerScopusCandidate:
        # FOR UPDATE cannot lock a missing row.  Insert-or-ignore closes that
        # race, after which the locked select gives both writers one root.
        self._session.execute(
            pg_insert(LecturerScopusCandidate.__table__)
            .values(
                lecturer_id=candidate.lecturer_id,
                scopus_author_id=candidate.scopus_author_id,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            .on_conflict_do_nothing(
                index_elements=["lecturer_id", "scopus_author_id"]
            )
        )
        root = self._session.scalar(
            select(LecturerScopusCandidate)
            .where(
                LecturerScopusCandidate.lecturer_id == candidate.lecturer_id,
                LecturerScopusCandidate.scopus_author_id == candidate.scopus_author_id,
            )
            .with_for_update()
        )
        if root is None:
            raise GenerationRunStateError("candidate root insert was not observable")
        if root.last_seen_at < observed_at:
            root.last_seen_at = observed_at
        return root

    def _verify_observation_evidence(
        self,
        observation_id: UUID,
        expected: Sequence[_PreparedEvidence],
    ) -> None:
        actual = self._session.scalars(
            select(LecturerScopusCandidateEvidence)
            .where(LecturerScopusCandidateEvidence.observation_id == observation_id)
            .order_by(LecturerScopusCandidateEvidence.id)
        )
        actual_keys = {
            (row.evidence_kind, row.rule_id, row.rule_version, row.evidence_fingerprint)
            for row in actual
        }
        expected_keys = {
            (row.evidence_kind, row.rule_id, row.rule_version, row.fingerprint)
            for row in expected
        }
        if actual_keys != expected_keys:
            raise GenerationRunConflict(
                f"evidence for observation {observation_id} has different content"
            )

    def _verify_existing_run(
        self,
        run_id: UUID,
        prepared: Sequence[_PreparedCandidate],
    ) -> None:
        persisted_pairs = {
            tuple(row)
            for row in self._session.execute(
                select(
                    LecturerScopusCandidate.lecturer_id,
                    LecturerScopusCandidate.scopus_author_id,
                )
                .join(
                    LecturerScopusCandidateObservation,
                    LecturerScopusCandidateObservation.candidate_id
                    == LecturerScopusCandidate.id,
                )
                .where(
                    LecturerScopusCandidateObservation.generation_run_id == run_id
                )
            ).all()
        }
        requested_pairs = {
            (item.candidate.lecturer_id, item.candidate.scopus_author_id)
            for item in prepared
        }
        if persisted_pairs != requested_pairs:
            raise GenerationRunConflict(
                f"completed run {run_id} has a different candidate pair set"
            )

        for item in prepared:
            root = self._session.scalar(
                select(LecturerScopusCandidate).where(
                    LecturerScopusCandidate.lecturer_id == item.candidate.lecturer_id,
                    LecturerScopusCandidate.scopus_author_id == item.candidate.scopus_author_id,
                )
            )
            if root is None:
                raise GenerationRunConflict("completed run is missing a candidate root")
            observation = self._session.scalar(
                select(LecturerScopusCandidateObservation).where(
                    LecturerScopusCandidateObservation.candidate_id == root.id,
                    LecturerScopusCandidateObservation.generation_run_id == run_id,
                )
            )
            if observation is None or observation.observation_hash != item.observation_hash:
                raise GenerationRunConflict("completed run has different observation content")
            self._verify_observation_evidence(observation.id, item.evidence)

    def _mark_run_failed(self, run_id: UUID) -> None:
        self._session.rollback()
        try:
            with self._session.begin():
                run = self._session.get(
                    CandidateGenerationRun,
                    run_id,
                    with_for_update=True,
                )
                if run is not None and run.status == "RUNNING":
                    run.status = "FAILED"
                    run.completed_at = datetime.now(UTC)
        except Exception:
            self._session.rollback()

    def _result_for_run(
        self,
        run_id: UUID,
        *,
        idempotent_replay: bool,
        candidate_roots: int | None = None,
        observations: int | None = None,
        evidence: int | None = None,
    ) -> CandidatePersistenceResult:
        run = self._session.get(CandidateGenerationRun, run_id)
        if run is None:
            raise GenerationRunStateError(f"generation run {run_id} does not exist")
        if candidate_roots is None:
            candidate_roots = int(
                self._session.scalar(
                    select(func.count(func.distinct(LecturerScopusCandidateObservation.candidate_id))).where(
                        LecturerScopusCandidateObservation.generation_run_id == run_id
                    )
                )
                or 0
            )
        if observations is None:
            observations = int(
                self._session.scalar(
                    select(func.count(LecturerScopusCandidateObservation.id)).where(
                        LecturerScopusCandidateObservation.generation_run_id == run_id
                    )
                )
                or 0
            )
        if evidence is None:
            evidence = int(
                self._session.scalar(
                    select(func.count(LecturerScopusCandidateEvidence.id))
                    .join(
                        LecturerScopusCandidateObservation,
                        LecturerScopusCandidateObservation.id
                        == LecturerScopusCandidateEvidence.observation_id,
                    )
                    .where(LecturerScopusCandidateObservation.generation_run_id == run_id)
                )
                or 0
            )
        return CandidatePersistenceResult(
            run_id=run_id,
            run_status=run.status,
            candidate_roots=candidate_roots,
            observations=observations,
            evidence=evidence,
            idempotent_replay=idempotent_replay,
        )


__all__ = [
    "CANDIDATE_RULE_IDS",
    "CANDIDATE_RULE_SET_ID",
    "CANDIDATE_RULE_SET_VERSION",
    "CandidatePersistenceResult",
    "CandidatePersistenceService",
    "GenerationRunConflict",
    "GenerationRunSpec",
    "GenerationRunStateError",
    "GENERATION_RULE_SET_ID",
    "GENERATION_RULE_SET_VERSION",
    "PUBLICATION_RULE_IDS",
    "PUBLICATION_RULE_SET_ID",
    "PUBLICATION_RULE_SET_VERSION",
    "SOURCE_STATE_SCHEMA_VERSION",
    "build_source_state",
    "canonical_json",
    "sha256_json",
]
