"""M2.7B-2 durable candidate persistence tests."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.matching.candidate_persistence import (
    CANDIDATE_RULE_SET_VERSION,
    PUBLICATION_RULE_SET_VERSION,
    CandidatePersistenceService,
    GenerationRunSpec,
    canonical_json,
    sha256_json,
)
from app.services.matching.candidate_types import (
    CandidateEvidence,
    EnrichedLecturerScopusCandidate,
    PublicationEvidence,
)


def _source_state() -> dict:
    return {
        "schema_version": 1,
        "rules": {
            "candidate_generator": {
                "rule_set_id": "candidate",
                "rule_set_version": CANDIDATE_RULE_SET_VERSION,
                "rule_ids": ["RULE_EXACT_N0"],
            },
            "publication_enrichment": {
                "rule_set_id": "publication",
                "rule_set_version": PUBLICATION_RULE_SET_VERSION,
                "rule_ids": ["RULE_KNOWN_PUBLICATION_DOI_EXACT"],
            },
        },
        "inputs": {
            "lecturers": {"count": 1, "sha256": "a" * 64},
            "scopus_authors": {"count": 1, "sha256": "b" * 64},
        },
    }


def _candidate(
    lecturer_id: uuid.UUID,
    author_id: uuid.UUID,
    *,
    publication: bool = False,
) -> EnrichedLecturerScopusCandidate:
    name = CandidateEvidence(
        rule_id="RULE_EXACT_N0",
        lecturer_source_value="TS. Nguyen Van A",
        lecturer_comparison_value="ts. nguyen van a",
        scopus_surface_type="PREFERRED_NAME",
        scopus_surface_value="Nguyen Van A",
        scopus_comparison_value="nguyen van a",
    )
    publications = ()
    if publication:
        publication_id = uuid.uuid4()
        publications = (
            PublicationEvidence(
                rule_id="RULE_KNOWN_PUBLICATION_DOI_EXACT",
                known_publication_id=uuid.uuid4(),
                lecturer_id=lecturer_id,
                lecturer_snapshot_id=uuid.uuid4(),
                canonical_publication_id=publication_id,
                canonical_publication_eid="2-s2.0-123",
                candidate_scopus_author_id=author_id,
                known_publication_doi_normalized="10.1000/example",
                known_publication_title_normalized="an example",
                canonical_publication_doi="10.1000/example",
                canonical_publication_title="An example",
                reconciliation="DOI_EXACT",
            ),
        )
    return EnrichedLecturerScopusCandidate(
        lecturer_id=lecturer_id,
        scopus_author_id=author_id,
        scopus_id="12345678900",
        preferred_name="Nguyen Van A",
        evidence=(name,),
        publication_evidence=publications,
    )


def test_canonical_json_and_hash_ignore_mapping_order() -> None:
    left = {"b": [2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_json(left) == sha256_json(right)


def test_source_state_has_compact_rule_and_input_contract() -> None:
    assert _source_state()["schema_version"] == 1
    assert "inputs" in _source_state()
    assert "rules" in _source_state()


@pytest.fixture
def candidate_fixture(isolated_db_engine):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    session = Session(isolated_db_engine)
    # The shared isolated schema is session-scoped; reset only this fixture's
    # dependency slice so each persistence case starts from an empty dataset.
    for model in (
        LecturerScopusCandidateEvidence,
        LecturerScopusCandidateObservation,
        LecturerScopusCandidate,
        CandidateGenerationRun,
        ScopusAuthor,
        Lecturer,
    ):
        session.execute(delete(model))
    session.commit()
    lecturer = Lecturer(
        full_name="TS. Nguyen Van A",
        full_name_normalized="ts. nguyen van a",
    )
    author = ScopusAuthor(scopus_id=f"{uuid.uuid4().int % 10**11:011d}", preferred_name="Nguyen Van A")
    session.add_all([lecturer, author])
    session.commit()
    # Accessing expired primary keys after commit would autobegin a read
    # transaction before the service owns the session transaction.
    lecturer_id = lecturer.id
    author_id = author.id
    session.rollback()
    try:
        yield session, lecturer_id, author_id
    finally:
        session.close()


def test_first_run_and_same_run_retry_are_idempotent(candidate_fixture) -> None:
    session, lecturer_id, author_id = candidate_fixture
    run_id = uuid.uuid4()
    spec = GenerationRunSpec(run_id=run_id, source_state=_source_state())
    candidate = _candidate(lecturer_id, author_id)
    service = CandidatePersistenceService(session)

    first = service.persist_generation(spec, [candidate])
    second = service.persist_generation(spec, [candidate])

    assert first.run_status == "COMPLETED"
    assert first.candidate_roots == 1
    assert first.observations == 1
    assert first.evidence == 1
    assert second.idempotent_replay is True
    assert session.scalar(select(func.count(LecturerScopusCandidate.id))) == 1
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 1
    assert session.scalar(select(func.count(LecturerScopusCandidateEvidence.id))) == 1


def test_pair_uniqueness_allows_many_to_many_candidate_roots(candidate_fixture) -> None:
    session, lecturer_id, author_id = candidate_fixture
    second_lecturer = Lecturer(
        full_name="TS. Nguyen Van B",
        full_name_normalized="ts. nguyen van b",
    )
    second_author = ScopusAuthor(
        scopus_id=f"{uuid.uuid4().int % 10**11:011d}",
        preferred_name="Nguyen Van B",
    )
    session.add_all([second_lecturer, second_author])
    session.flush()
    second_lecturer_id, second_author_id = second_lecturer.id, second_author.id
    session.commit()
    session.rollback()

    result = CandidatePersistenceService(session).persist_generation(
        GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state()),
        [
            _candidate(lecturer_id, author_id),
            _candidate(lecturer_id, second_author_id),
            _candidate(second_lecturer_id, author_id),
        ],
    )

    assert result.candidate_roots == 3
    assert session.scalar(select(func.count(LecturerScopusCandidate.id))) == 3


def test_new_run_reuses_rejected_root_without_reopening(candidate_fixture) -> None:
    session, lecturer_id, author_id = candidate_fixture
    candidate = _candidate(lecturer_id, author_id)
    first_spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state())
    service = CandidatePersistenceService(session)
    service.persist_generation(first_spec, [candidate])

    root = session.scalar(select(LecturerScopusCandidate))
    assert root is not None
    root.status = "REJECTED"
    session.commit()

    second_spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state())
    service.persist_generation(second_spec, [candidate])

    session.expire_all()
    root = session.scalar(select(LecturerScopusCandidate))
    assert root is not None
    assert root.status == "REJECTED"
    assert session.scalar(select(func.count(LecturerScopusCandidate.id))) == 1
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 2


def test_changed_evidence_creates_new_observation_and_preserves_old(candidate_fixture) -> None:
    session, lecturer_id, author_id = candidate_fixture
    service = CandidatePersistenceService(session)
    first = _candidate(lecturer_id, author_id, publication=False)
    second = _candidate(lecturer_id, author_id, publication=True)

    first_spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state())
    service.persist_generation(first_spec, [first])
    first_observation = session.scalar(
        select(LecturerScopusCandidateObservation).where(
            LecturerScopusCandidateObservation.generation_run_id == first_spec.run_id
        )
    )
    assert first_observation is not None
    old_snapshot = first_observation.candidate_snapshot
    old_hash = first_observation.observation_hash
    session.rollback()

    service.persist_generation(
        GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state()),
        [second],
    )

    assert session.scalar(select(func.count(LecturerScopusCandidate.id))) == 1
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 2
    assert session.scalar(select(func.count(LecturerScopusCandidateEvidence.id))) == 3
    session.expire_all()
    preserved = session.scalar(
        select(LecturerScopusCandidateObservation).where(
            LecturerScopusCandidateObservation.generation_run_id == first_spec.run_id
        )
    )
    assert preserved is not None
    assert preserved.candidate_snapshot == old_snapshot
    assert preserved.observation_hash == old_hash


def test_evidence_ordering_is_canonical_and_rule_changes_are_new_history(
    candidate_fixture,
) -> None:
    session, lecturer_id, author_id = candidate_fixture
    base = _candidate(lecturer_id, author_id)
    extra = CandidateEvidence(
        rule_id="RULE_TITLE_STRIPPED_N0",
        lecturer_source_value="TS. Nguyen Van A",
        lecturer_comparison_value="ts. nguyen van a",
        scopus_surface_type="PREFERRED_NAME",
        scopus_surface_value="Nguyen Van A",
        scopus_comparison_value="nguyen van a",
    )
    ordered = replace(base, evidence=(base.evidence[0], extra))
    reversed_order = replace(base, evidence=(extra, base.evidence[0]))
    service = CandidatePersistenceService(session)

    first_spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state())
    service.persist_generation(first_spec, [ordered])
    replay = service.persist_generation(first_spec, [reversed_order])
    assert replay.idempotent_replay is True
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 1
    session.rollback()

    changed_state = _source_state()
    changed_state["rules"]["candidate_generator"]["rule_set_version"] = "M2.7A-3"
    service.persist_generation(
        GenerationRunSpec(run_id=uuid.uuid4(), source_state=changed_state),
        [reversed_order],
    )
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 2
    assert session.scalar(select(func.count(LecturerScopusCandidateEvidence.id))) == 4


def test_fatal_persistence_failure_marks_run_failed_not_completed(candidate_fixture) -> None:
    session, lecturer_id, author_id = candidate_fixture

    class FailingPersistenceService(CandidatePersistenceService):
        def _get_or_create_root(self, candidate, observed_at):
            raise RuntimeError("injected persistence failure")

    spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=_source_state())
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        FailingPersistenceService(session).persist_generation(
            spec, [_candidate(lecturer_id, author_id)]
        )

    run = session.get(CandidateGenerationRun, spec.run_id)
    assert run is not None
    assert run.status == "FAILED"
    assert run.completed_at is not None
    assert session.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 0
    assert session.scalar(select(func.count(LecturerScopusCandidateEvidence.id))) == 0
