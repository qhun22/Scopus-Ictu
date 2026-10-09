"""Task 08: operator CLI for candidate generation / persistence.

Runs only against the isolated PostgreSQL test database (TEST_DATABASE_URL).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.matching.candidate_persistence import (
    CandidatePersistenceService,
    GenerationRunConflict,
    GenerationRunSpec,
)
from scripts import generate_matching_candidates as cli


@pytest.fixture
def env(isolated_db_engine: Engine, tmp_path: Path):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    with Session(isolated_db_engine) as s:
        for table in (
            "lecturer_scopus_candidate_reviews",
            "identity_evidence",
            "lecturer_scopus_identities",
            "lecturer_scopus_candidate_evidence",
            "lecturer_scopus_candidate_observations",
            "lecturer_scopus_candidates",
            "candidate_generation_runs",
            "scopus_authors",
            "lecturers",
        ):
            s.execute(text(f"TRUNCATE {table} CASCADE"))
        lecturer_a = Lecturer(full_name="Nguyen Van A", full_name_normalized="nguyen van a")
        lecturer_b = Lecturer(full_name="Tran Thi B", full_name_normalized="tran thi b")
        match = ScopusAuthor(scopus_id="11111111111", preferred_name="Nguyen Van A")
        other = ScopusAuthor(scopus_id="22222222222", preferred_name="Le Van C")
        s.add_all([lecturer_a, lecturer_b, match, other])
        s.commit()
    url = isolated_db_engine.url
    reader = cli.make_read_only_engine(url)
    writer = create_engine(url, pool_pre_ping=True)
    yield {"url": url, "reader": reader, "writer": writer, "manifest": tmp_path / "manifest.json", "engine": isolated_db_engine}
    reader.dispose()
    writer.dispose()


def _all_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        out = {
            name: conn.execute(text(f'select count(*) from "{name}"')).scalar_one()
            for name in sorted(Base.metadata.tables)
        }
        conn.rollback()
    return out


def _apply(env, **kw):
    return cli.apply_generation(
        env["reader"], env["writer"], database=env["url"].database, manifest_path=env["manifest"], **kw
    )


def test_dry_run_is_read_only_and_changes_no_table(env) -> None:
    before = _all_counts(env["engine"])
    plan = cli.build_plan(env["reader"])
    assert len(plan.candidates) == 1
    summary = cli.summarize_plan(plan)
    assert summary["candidates"] == 1 and summary["publication_evidence"] == 0
    assert _all_counts(env["engine"]) == before
    # the reader engine really refuses writes
    with Session(env["reader"]) as s, pytest.raises(Exception) as exc:
        s.execute(text("insert into candidate_generation_runs (id) values (gen_random_uuid())"))
    assert "read-only" in str(exc.value).lower()


def test_apply_persists_pending_candidates_without_identity_or_review(env) -> None:
    lecturers_before = _fingerprint(env)
    result = _apply(env, expected_candidates=1)
    assert result["run_status"] == "COMPLETED"
    assert (result["candidate_roots"], result["observations"]) == (1, 1)
    assert result["evidence"] >= 1 and result["idempotent_replay"] is False
    assert result["inputs_unchanged_after_apply"] is True
    with Session(env["reader"]) as s:
        assert s.scalar(select(func.count(LecturerScopusCandidate.id))) == 1
        assert {r for (r,) in s.execute(select(LecturerScopusCandidate.status))} == {"PENDING"}
        assert s.scalar(select(func.count(LecturerScopusIdentity.id))) == 0
        assert s.scalar(select(func.count(LecturerScopusCandidateReview.id))) == 0
        s.rollback()
    assert _fingerprint(env) == lecturers_before  # lecturer ids, scopus ids, links untouched
    manifest = json.loads(env["manifest"].read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETED" and manifest["run_id"] == result["run_id"]


def test_retry_same_run_id_is_idempotent(env) -> None:
    first = _apply(env)
    counts = _all_counts(env["engine"])
    second = _apply(env)
    assert second["run_id"] == first["run_id"] and second["idempotent_replay"] is True
    assert _all_counts(env["engine"]) == counts
    assert counts["candidate_generation_runs"] == 1


def test_run_id_is_not_reused_when_source_changed(env) -> None:
    first = _apply(env)
    with Session(env["engine"]) as s:
        s.add(ScopusAuthor(scopus_id="33333333333", preferred_name="Pham Van D"))
        s.commit()
    counts = _all_counts(env["engine"])
    with pytest.raises(cli.SourceChanged):
        _apply(env)
    assert _all_counts(env["engine"]) == counts
    # service level: the same run_id with different source_state is rejected too
    plan = cli.build_plan(env["reader"])
    with Session(env["writer"]) as session, pytest.raises(GenerationRunConflict):
        CandidatePersistenceService(session).persist_generation(
            GenerationRunSpec(run_id=uuid.UUID(first["run_id"]), source_state=plan.source_state), plan.candidates
        )
    assert _all_counts(env["engine"]) == counts


@pytest.mark.parametrize("error", [OperationalError("select", {}, Exception("connection lost")), RuntimeError("boom")])
def test_persistence_failure_never_leaves_a_completed_run(env, monkeypatch, error) -> None:
    def fail(self, run_id, prepared):
        raise error

    with monkeypatch.context() as m:
        m.setattr(CandidatePersistenceService, "_persist_started_run", fail)
        with pytest.raises(type(error)):
            _apply(env)
    with Session(env["reader"]) as s:
        assert s.scalars(select(CandidateGenerationRun.status)).all() == ["FAILED"]
        assert s.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 0
        assert s.scalar(select(func.count(LecturerScopusCandidate.id))) == 0
        s.rollback()
    assert json.loads(env["manifest"].read_text(encoding="utf-8"))["status"] == "FAILED"
    # same manifest/run_id recovers cleanly
    again = _apply(env)
    assert again["run_status"] == "COMPLETED" and again["observations"] == 1
    with Session(env["reader"]) as s:
        assert s.scalar(select(func.count(CandidateGenerationRun.id))) == 1
        s.rollback()


def test_fresh_writer_session_has_no_transaction_conflict(env) -> None:
    plan = cli.build_plan(env["reader"])
    spec = GenerationRunSpec(run_id=uuid.uuid4(), source_state=plan.source_state)
    # Pitfall the CLI avoids: a session that already read has autobegun a transaction.
    dirty = Session(env["writer"])
    dirty.execute(text("select 1"))
    with pytest.raises(InvalidRequestError, match="already begun"):
        CandidatePersistenceService(dirty).persist_generation(spec, plan.candidates)
    dirty.close()
    # The CLI path (separate read session, brand-new writer session) works.
    assert _apply(env)["run_status"] == "COMPLETED"


def test_existing_completed_run_requires_explicit_new_run(env, tmp_path) -> None:
    _apply(env)
    env["manifest"] = tmp_path / "other.json"  # no manifest => user re-ran a "check" command
    with pytest.raises(cli.RunRefused):
        _apply(env)
    assert not env["manifest"].exists()
    with Session(env["reader"]) as s:
        assert s.scalar(select(func.count(CandidateGenerationRun.id))) == 1
        s.rollback()


def test_running_run_fails_closed_without_resume_flag(env) -> None:
    run_id = uuid.uuid4()
    with Session(env["engine"]) as s:
        s.execute(
            text(
                "insert into candidate_generation_runs (id, rule_set_id, rule_set_version, source_state, started_at, status) "
                "values (:i, 'x', 'y', '{}'::jsonb, now(), 'RUNNING')"
            ),
            {"i": str(run_id)},
        )
        s.commit()
    with pytest.raises(cli.RunRefused):
        _apply(env, run_id=run_id)
    with Session(env["reader"]) as s:
        assert s.scalar(select(func.count(LecturerScopusCandidateObservation.id))) == 0
        s.rollback()


def test_expected_candidate_count_mismatch_is_refused(env) -> None:
    with pytest.raises(cli.CliRefused):
        _apply(env, expected_candidates=40)
    assert _all_counts(env["engine"])["candidate_generation_runs"] == 0
    assert not env["manifest"].exists()


def test_guards_reject_wrong_database_port_5432_and_repo_manifest(env, monkeypatch) -> None:
    url = make_url("postgresql+psycopg2://u:p@127.0.0.1:55432/scopus_ictu_demo_teacher_20261014")
    cli.validate_target_url(url, "scopus_ictu_demo_teacher_20261014", 55432)
    with pytest.raises(cli.CliRefused):
        cli.validate_target_url(url, "another_db")
    with pytest.raises(cli.CliRefused):
        cli.validate_target_url(url.set(port=5432), "scopus_ictu_demo_teacher_20261014")
    with pytest.raises(cli.CliRefused):
        no_port = make_url("postgresql+psycopg2://u:p@127.0.0.1/scopus_ictu_demo_teacher_20261014")
        cli.validate_target_url(no_port, "scopus_ictu_demo_teacher_20261014")  # implicit 5432
    with pytest.raises(cli.CliRefused):
        cli.validate_target_url(url, "scopus_ictu_demo_teacher_20261014", 55433)
    with pytest.raises(cli.CliRefused):
        cli.validate_target_url(url.set(host="10.0.0.5"), "scopus_ictu_demo_teacher_20261014")
    with pytest.raises(cli.CliRefused):
        cli.validate_target_url(url.set(database="scopus_ictu_acceptance_v2"), "scopus_ictu_acceptance_v2")
    with pytest.raises(cli.CliRefused):
        cli.validate_manifest_path(cli.REPO_ROOT / "backend" / "m.json")
    cli.validate_manifest_path(env["manifest"])
    # server-side identity must also agree with what was requested
    real = env["url"]
    cli.verify_server_identity(env["reader"], real.database, real.port)
    with pytest.raises(cli.CliRefused):
        cli.verify_server_identity(env["reader"], "not_this_db", real.port)
    with pytest.raises(cli.CliRefused):
        cli.verify_server_identity(env["reader"], real.database, 5432)

    # main(): refuses before any database work
    from app.core.config import settings

    monkeypatch.setattr(settings, "db_port", 5432)
    assert cli.main(["--dry-run", "--expected-database", settings.db_name]) == cli.EXIT_REFUSED
    monkeypatch.setattr(settings, "db_port", real.port)
    assert cli.main(["--dry-run", "--expected-database", "wrong_db"]) == cli.EXIT_REFUSED
    assert cli.main(["--apply", "--expected-database", settings.db_name]) == cli.EXIT_REFUSED  # no manifest


def test_main_dry_run_and_apply_end_to_end(env, monkeypatch, capsys) -> None:
    from app.core.config import settings

    if (settings.db_name, settings.db_port) != (env["url"].database, env["url"].port):
        pytest.skip("process settings do not point at the isolated test database")
    args = ["--expected-database", env["url"].database, "--expected-port", str(env["url"].port)]
    assert cli.main(["--dry-run", *args]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert '"tables_unchanged":true' in out and '"candidates":1' in out
    assert cli.main(["--apply", *args, "--manifest", str(env["manifest"]), "--expected-candidates", "1"]) == cli.EXIT_OK
    assert cli.main(["--apply", *args, "--manifest", str(env["manifest"]), "--expected-candidates", "1"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert '"idempotent_replay":true' in out
    assert _all_counts(env["engine"])["candidate_generation_runs"] == 1


def _fingerprint(env) -> dict:
    with Session(env["reader"]) as s:
        out = {
            "lecturers": sorted(str(i) for (i,) in s.execute(select(Lecturer.id))),
            "authors": sorted((str(i), sid) for i, sid in s.execute(select(ScopusAuthor.id, ScopusAuthor.scopus_id))),
        }
        s.rollback()
    return out
