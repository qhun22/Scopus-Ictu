"""Gate E.1 follow-ups on a real PostgreSQL test database.

G10  ADMIN revokes an approved identity (append-only compensation, audited).
G09  an ADMIN withdraws one paper from one lecturer; every lecturer-facing read honours it.
G12  the dashboard exposes a separate approved-lecturer publication count.

Fixtures are shared with ``test_candidate_review_service`` so both suites use the same
guarded isolated database.
"""

# ruff: noqa: F811  (pytest fixtures are imported by name and re-declared as parameters)
from __future__ import annotations

import uuid
from importlib import util as importlib_util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DatabaseError

from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.identity import LecturerScopusIdentity
from app.models.publication import Publication, PublicationAuthor
from app.models.publication_exclusion import LecturerPublicationExclusionEvent
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateAlreadyDecidedError,
    CandidateNotAcceptedError,
    CandidateReviewError,
    CandidateReviewService,
    ReviewerNotAuthorizedError,
    RevocationReasonRequiredError,
    RevokeIdentityCommand,
    StaleCandidateVersionError,
)
from app.services.dashboard_queries import get_dashboard_summary
from app.services.lecturer_scopus_projection import LecturerScopusProjectionService
from app.services.publication_exclusions import (
    PublicationExclusionError,
    PublicationExclusionService,
)
from app.services.publication_export import _batch_lecturer_links
from tests.db_safety_guard import assert_safe_for_destructive_test
from tests.integration.test_candidate_review_service import (  # noqa: F401  (fixtures)
    _make_user,
    ready_fixture,
    review_engine,
    review_session,
    session_factory,
)

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "e4a1b7c92d10_g09_lecturer_publication_exclusions.py")


@pytest.fixture(autouse=True)
def _clean_publication_tables(review_engine):
    """The shared review fixtures do not truncate publications; this suite adds some."""

    def wipe():
        assert_safe_for_destructive_test(review_engine)
        with review_engine.begin() as conn:
            conn.execute(text("TRUNCATE publications, lecturer_publication_exclusion_events "
                              "CASCADE"))

    wipe()
    yield
    wipe()


def _accepted(review_session, ready_fixture):
    """Accept the fixture candidate; returns (candidate, identity_id, admin)."""
    cand, obs = ready_fixture["candidate"], ready_fixture["observation"]
    result = CandidateReviewService(review_session).accept_candidate(AcceptCandidateCommand(
        candidate_id=cand.id, observation_id=obs.id, candidate_version=cand.version,
        reviewer_user_id=ready_fixture["reviewer"].id))
    admin = _make_user(review_session, role="ADMIN")
    review_session.commit()
    return review_session.get(LecturerScopusCandidate, cand.id), result.resulting_identity_id, admin


def _publication(review_session, ready_fixture, n=1) -> Publication:
    pub = Publication(eid=f"2-s2.0-{uuid.uuid4().int % 10**10:010d}", title=f"Paper {n}",
                      title_normalized=f"paper {n}", year=2025)
    review_session.add(pub)
    review_session.flush()
    review_session.add(PublicationAuthor(publication_id=pub.id,
                                         scopus_author_id=ready_fixture["author_id"],
                                         author_order=n))
    review_session.commit()
    return pub


def _revoke(review_session, candidate, admin_id, reason="Synthetic mistaken approval"):
    return CandidateReviewService(review_session).revoke_identity(RevokeIdentityCommand(
        candidate_id=candidate.id, candidate_version=candidate.version,
        admin_user_id=admin_id, reason=reason))


# -- G10 ----------------------------------------------------------------------

def test_g10_admin_revokes_an_approved_identity_and_history_is_kept(review_session, ready_fixture):
    cand, identity_id, admin = _accepted(review_session, ready_fixture)
    before_version = cand.version
    result = _revoke(review_session, cand, admin.id)

    assert (result.action, result.candidate_status) == ("REVOKE", "PENDING")
    assert result.candidate_version == before_version + 1
    identity = review_session.get(LecturerScopusIdentity, identity_id)
    review_session.refresh(identity)
    assert identity.status == "REVOKED"                          # the row is kept, not deleted
    actions = review_session.scalars(select(LecturerScopusCandidateReview.action).where(
        LecturerScopusCandidateReview.candidate_id == cand.id).order_by(
        LecturerScopusCandidateReview.created_at)).all()
    assert actions == ["ACCEPT", "REOPEN"]                       # compensation is an append
    reopen = review_session.scalar(select(LecturerScopusCandidateReview).where(
        LecturerScopusCandidateReview.action == "REOPEN"))
    assert reopen.reason == "Synthetic mistaken approval"
    assert reopen.resulting_identity_id == identity_id
    audit = set(review_session.scalars(select(AuditEvent.action)).all())
    assert {"IDENTITY_REVOKED", "CANDIDATE_REOPENED_BY_REVOCATION"} <= audit


def test_g10_revocation_removes_the_lecturers_publications(review_session, ready_fixture):
    cand, _, admin = _accepted(review_session, ready_fixture)
    _publication(review_session, ready_fixture)
    projection = LecturerScopusProjectionService(review_session)
    lecturer_id = ready_fixture["lecturer_id"]
    assert projection.get_lecturer_publications(lecturer_id).total == 1
    _revoke(review_session, cand, admin.id)
    assert projection.get_lecturer_publications(lecturer_id).total == 0


def test_g10_guards(review_session, ready_fixture):
    cand, _, admin = _accepted(review_session, ready_fixture)
    reviewer = ready_fixture["reviewer"]                         # REVIEWER, not ADMIN
    with pytest.raises(ReviewerNotAuthorizedError):
        _revoke(review_session, cand, reviewer.id)
    with pytest.raises(RevocationReasonRequiredError):
        _revoke(review_session, cand, admin.id, reason="   ")
    with pytest.raises(StaleCandidateVersionError):
        CandidateReviewService(review_session).revoke_identity(RevokeIdentityCommand(
            candidate_id=cand.id, candidate_version=cand.version + 5,
            admin_user_id=admin.id, reason="x"))
    review_session.rollback()
    assert review_session.get(LecturerScopusIdentity, review_session.scalar(
        select(LecturerScopusIdentity.id))).status == "APPROVED"      # nothing changed


def test_g10_pending_candidate_and_double_revoke_are_refused(review_session, ready_fixture):
    cand, _, admin = _accepted(review_session, ready_fixture)
    _revoke(review_session, cand, admin.id)
    review_session.refresh(cand)
    with pytest.raises(CandidateNotAcceptedError):                # now PENDING
        _revoke(review_session, cand, admin.id)


def test_g10_a_revoked_pair_cannot_be_silently_re_accepted(review_session, ready_fixture):
    cand, _, admin = _accepted(review_session, ready_fixture)
    _revoke(review_session, cand, admin.id)
    review_session.refresh(cand)
    with pytest.raises((CandidateAlreadyDecidedError, CandidateReviewError)):
        CandidateReviewService(review_session).accept_candidate(AcceptCandidateCommand(
            candidate_id=cand.id, observation_id=ready_fixture["observation"].id,
            candidate_version=cand.version, reviewer_user_id=ready_fixture["reviewer"].id))
    review_session.rollback()
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 1


# -- G09 + G12 ----------------------------------------------------------------

def test_g09_exclusion_is_honoured_by_lists_exports_and_counts(review_session, ready_fixture):
    _, _, admin = _accepted(review_session, ready_fixture)
    keep, drop = _publication(review_session, ready_fixture, 1), _publication(
        review_session, ready_fixture, 2)
    lecturer_id = ready_fixture["lecturer_id"]
    projection = LecturerScopusProjectionService(review_session)
    service = PublicationExclusionService(review_session)
    assert projection.get_lecturer_publications(lecturer_id).total == 2
    summary = get_dashboard_summary(review_session)
    corpus = review_session.scalar(text("SELECT count(*) FROM publications"))   # fixture adds one
    assert (summary.total_publications, summary.approved_ictu_publications) == (corpus, 2)

    service.exclude(lecturer_id, drop.id, admin.id, "Mixed Scopus profile: another person's paper")

    page = projection.get_lecturer_publications(lecturer_id)
    assert page.total == 1 and [i.publication_id for i in page.items] == [keep.id]
    assert projection.get_lecturer_publication_aggregates(lecturer_id).total_publications == 1
    assert _batch_lecturer_links(review_session, [drop.id]) == {}
    assert len(_batch_lecturer_links(review_session, [keep.id])[keep.id]) == 1
    summary = get_dashboard_summary(review_session)
    # The corpus count is untouched; only the approved-lecturer count drops.
    assert (summary.total_publications, summary.approved_ictu_publications) == (corpus, 1)
    assert [r.publication_id for r in service.list_excluded(lecturer_id)] == [drop.id]
    assert review_session.get(Publication, drop.id) is not None   # the paper itself stays

    service.restore(lecturer_id, drop.id, admin.id, "Checked: the paper is theirs")
    assert projection.get_lecturer_publications(lecturer_id).total == 2
    assert get_dashboard_summary(review_session).approved_ictu_publications == 2
    assert review_session.scalar(text(
        "SELECT count(*) FROM lecturer_publication_exclusion_events")) == 2   # history kept


def test_g09_rules(review_session, ready_fixture):
    _, _, admin = _accepted(review_session, ready_fixture)
    pub = _publication(review_session, ready_fixture)
    stranger = Publication(eid=f"2-s2.0-{uuid.uuid4().int % 10**10:010d}", title="Unlinked",
                           title_normalized="unlinked")
    review_session.add(stranger)
    review_session.commit()
    lecturer_id, reviewer = ready_fixture["lecturer_id"], ready_fixture["reviewer"]
    service = PublicationExclusionService(review_session)

    def code(call):
        with pytest.raises(PublicationExclusionError) as exc:
            call()
        review_session.rollback()
        return exc.value.code

    assert code(lambda: service.exclude(lecturer_id, pub.id, reviewer.id, "x")) == "FORBIDDEN"
    assert code(lambda: service.exclude(lecturer_id, pub.id, admin.id, "  ")) == (
        "EXCLUSION_REASON_REQUIRED")
    assert code(lambda: service.exclude(lecturer_id, stranger.id, admin.id, "x")) == (
        "PUBLICATION_NOT_LINKED")
    assert code(lambda: service.exclude(lecturer_id, uuid.uuid4(), admin.id, "x")) == "NOT_FOUND"
    assert code(lambda: service.restore(lecturer_id, pub.id, admin.id, "x")) == "NOT_EXCLUDED"
    service.exclude(lecturer_id, pub.id, admin.id, "x")
    assert code(lambda: service.exclude(lecturer_id, pub.id, admin.id, "x")) == "ALREADY_EXCLUDED"
    audit = set(review_session.scalars(select(AuditEvent.action)).all())
    assert "LECTURER_PUBLICATION_EXCLUDED" in audit


# -- G09 migration (append-only trigger) --------------------------------------

def test_g09_migration_installs_an_append_only_table(review_engine):
    schema = f"g09_{uuid.uuid4().hex}"
    with review_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(review_engine.url, future=True, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=30000"})
    try:
        others = [t for n, t in Base.metadata.tables.items()
                  if n != LecturerPublicationExclusionEvent.__tablename__]
        Base.metadata.create_all(bind=engine, tables=others)
        spec = importlib_util.spec_from_file_location("g09_mig", MIGRATION)
        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            context = MigrationContext.configure(conn, opts={"target_metadata": Base.metadata})
            with Operations.context(context):
                module.upgrade()
        with engine.begin() as conn:
            live = {r[0] for r in conn.execute(text(
                "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = :s "
                "AND t.relname = 'lecturer_publication_exclusion_events'"), {"s": schema})}
        model = {str(c.name) for c in LecturerPublicationExclusionEvent.__table__.constraints
                 if c.name}
        assert model <= live, model - live                       # model names exist in the DB
        with engine.begin() as conn:
            uid, lid, pid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            conn.execute(text("INSERT INTO users (id, email, password_hash, display_name, role, "
                              "is_active, version, auth_version) VALUES (:i, :e, 'x', 'x', "
                              "'ADMIN', true, 1, 1)"), {"i": uid, "e": f"{uid.hex}@t.local"})
            conn.execute(text("INSERT INTO lecturers (id, full_name, full_name_normalized, "
                              "version) VALUES (:i, 'L', 'l', 1)"), {"i": lid})
            conn.execute(text("INSERT INTO publications (id, eid, title, title_normalized) "
                              "VALUES (:i, 'EID1', 't', 't')"), {"i": pid})
            conn.execute(text(
                "INSERT INTO lecturer_publication_exclusion_events (lecturer_id, publication_id,"
                " action, reason, acted_by_user_id) VALUES (:l, :p, 'EXCLUDE', 'r', :u)"),
                {"l": lid, "p": pid, "u": uid})
        for statement in ("UPDATE lecturer_publication_exclusion_events SET reason = 'z'",
                          "DELETE FROM lecturer_publication_exclusion_events",
                          "TRUNCATE lecturer_publication_exclusion_events"):
            with pytest.raises(DatabaseError, match="append-only"), engine.begin() as conn:
                conn.execute(text(statement))
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(review_engine)
        with review_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))

