"""PostgreSQL contract tests for M2.7B-3S confidence nullability."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor


@pytest.fixture(scope="module")
def confidence_engine() -> Engine:
    """Use only the caller-provided isolated PostgreSQL database."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL must point to an isolated PostgreSQL database")
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield engine
    finally:
        engine.dispose()


def _insert_evidence(
    engine: Engine,
    confidence_score: Decimal | None,
    *,
    features: dict | None = None,
    source_refs: list | None = None,
) -> Decimal | None:
    lecturer_id = uuid.uuid4()
    author_id = uuid.uuid4()
    identity_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    with Session(engine) as session:
        session.add_all(
            [
                Lecturer(
                    id=lecturer_id,
                    full_name="M2.7B-3S Test Lecturer",
                    full_name_normalized="m2 7b 3s test lecturer",
                ),
                ScopusAuthor(
                    id=author_id,
                    scopus_id=f"m27b3s-{author_id}",
                    preferred_name="M2.7B-3S Test Author",
                ),
            ]
        )
        session.flush()
        session.add(
            LecturerScopusIdentity(
                id=identity_id,
                lecturer_id=lecturer_id,
                scopus_author_id=author_id,
            )
        )
        session.flush()
        session.add(
            IdentityEvidence(
                id=evidence_id,
                identity_id=identity_id,
                evidence_type="NAME_SIMILARITY",
                direction="SUPPORTS",
                confidence_score=confidence_score,
                algorithm_version="m27b3s-test-1",
                features=features or {"name_similarity": "not-computed"},
                source_refs=source_refs or [{"kind": "test"}],
                evidence_fingerprint=uuid.uuid4().hex * 2,
            )
        )
        session.flush()
        stored = session.get(IdentityEvidence, evidence_id)
        assert stored is not None
        return stored.confidence_score


def test_schema_is_nullable_without_changing_numeric_contract(
    confidence_engine: Engine,
) -> None:
    column = next(
        column
        for column in inspect(confidence_engine).get_columns("identity_evidence")
        if column["name"] == "confidence_score"
    )
    assert column["nullable"] is True
    assert column["type"].precision == 5
    assert column["type"].scale == 4

    with confidence_engine.connect() as connection:
        constraint = connection.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'identity_evidence'::regclass
                  AND conname = 'ck_identity_evidence_confidence_score'
                """
            )
        ).scalar_one()
    assert "confidence_score >= 0.0" in constraint
    assert "confidence_score <= 1.0" in constraint


@pytest.mark.parametrize(
    "confidence_score",
    [None, Decimal("0.0000"), Decimal("1.0000"), Decimal("0.7500")],
)
def test_null_and_in_range_decimal_scores_are_stored(
    confidence_engine: Engine, confidence_score: Decimal | None
) -> None:
    stored = _insert_evidence(confidence_engine, confidence_score)
    assert stored == confidence_score
    assert stored is None or isinstance(stored, Decimal)


def test_candidate_derived_evidence_can_have_no_machine_score(
    confidence_engine: Engine,
) -> None:
    stored = _insert_evidence(
        confidence_engine,
        None,
        features={"source": "candidate-derived", "score": "not-computed"},
        source_refs=[{"kind": "candidate_evidence", "id": "test-only"}],
    )
    assert stored is None


@pytest.mark.parametrize("confidence_score", [Decimal("-0.0001"), Decimal("1.0001")])
def test_out_of_range_scores_are_rejected(
    confidence_engine: Engine, confidence_score: Decimal
) -> None:
    with pytest.raises(IntegrityError):
        _insert_evidence(confidence_engine, confidence_score)
