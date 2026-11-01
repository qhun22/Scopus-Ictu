"""E3-P2-B2: staging persistence on real PostgreSQL. NOT executed until authorized.

Requires TEST_DATABASE_URL pointing to an allowlisted disposable database; the conftest guard
(tests/db_safety_guard.py) re-verifies the target. Each test works in its own schema created by
running the real Alembic migration chain's staging revision DDL, then dropped. Synthetic data.
"""

from __future__ import annotations

import hashlib
import importlib.util
import threading
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.services.source_staging.service import Actor, SourceStagingService, StagingError
from tests.db_safety_guard import assert_safe_for_destructive_test
from tests.source_staging_fixtures import ORCID_A, harvest, lecturer

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "a77e01c33ee1_e3_p2b1_source_claim_staging.py")
ACTOR = Actor(service="e3-p2b2-pg-tests")
STAGING = ("source_claims", "source_records", "source_analyses", "source_artifacts",
           "source_captures", "source_contents", "source_rule_sets")


@pytest.fixture
def pg(isolated_db_engine: Engine | None) -> Generator[sessionmaker, None, None]:
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    schema = f"e3p2b2_{uuid.uuid4().hex}"
    with isolated_db_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(isolated_db_engine.url, future=True, pool_pre_ping=True,
                           connect_args={"options": f"-csearch_path={schema} "
                                                    "-cstatement_timeout=30000 -clock_timeout=30s"})
    try:
        others = [t for n, t in Base.metadata.tables.items() if n not in STAGING]
        Base.metadata.create_all(bind=engine, tables=others)
        spec = importlib.util.spec_from_file_location("e3_p2b1", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()          # the real staging DDL, CHECKs and views
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(isolated_db_engine)
        with isolated_db_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _activate(factory) -> None:
    with factory() as s:
        SourceStagingService(s, ACTOR).activate_rule_set()
        s.commit()


def test_pg_round_trip_checks_and_views(pg):
    _activate(pg)
    with pg() as s:
        result = SourceStagingService(s, ACTOR).ingest_harvest(
            **harvest([lecturer(1, orcid=ORCID_A), lecturer(2, orcid=ORCID_A)]))
        s.commit()
    assert result.outcome == "CREATED"
    with pg() as s:
        assert s.execute(text("SELECT COUNT(*) FROM source_claim_observations")).scalar_one() == 4
        with pytest.raises(IntegrityError):    # content-hash CHECK is real on PostgreSQL
            s.execute(text("UPDATE source_contents SET content_json = content_json || ' '"))
        s.rollback()


def test_pg_parallel_ingest_of_the_same_files_creates_one_set_of_rows(pg):
    _activate(pg)
    files = harvest([lecturer(1, orcid=ORCID_A)])
    results, errors, barrier = [], [], threading.Barrier(2)

    def worker():
        try:
            with pg() as s:
                barrier.wait(timeout=10)
                results.append(SourceStagingService(s, ACTOR).ingest_harvest(**files).outcome)
                s.commit()
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    assert sorted(results) == ["ALREADY_INGESTED", "CREATED"]
    with pg() as s:
        counts = {t: s.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()
                  for t in ("source_contents", "source_artifacts", "source_analyses")}
    assert counts == {"source_contents": 1, "source_artifacts": 1, "source_analyses": 1}


def test_pg_activation_waits_for_an_open_ingest_transaction(pg):
    _activate(pg)
    ingest_session: Session = pg()
    SourceStagingService(ingest_session, ACTOR).ingest_harvest(**harvest([lecturer(1)]))
    done = threading.Event()

    def activate():
        with pg() as s:
            SourceStagingService(s, ACTOR).activate_rule_set()   # exclusive advisory lock
            s.commit()
        done.set()

    thread = threading.Thread(target=activate)
    thread.start()
    assert not done.wait(timeout=2)            # blocked behind the shared ingest lock
    ingest_session.commit()
    ingest_session.close()
    thread.join(timeout=30)
    assert done.is_set()


def test_pg_failed_ingest_keeps_the_callers_earlier_work(pg):
    _activate(pg)
    with pg() as s:
        service = SourceStagingService(s, ACTOR)
        kept = service.ingest_harvest(**harvest([lecturer(1)]))
        files = harvest([lecturer(2)])
        wrong_sha = hashlib.sha256(b"x").hexdigest()
        with pytest.raises(StagingError):
            service.ingest_harvest(**{**files, "lecturers_sha256": wrong_sha})
        s.commit()
    with pg() as s:
        ids = s.execute(text("SELECT id FROM source_artifacts")).scalars().all()
    assert kept.outcome == "CREATED" and ids == [kept.artifact_id]
