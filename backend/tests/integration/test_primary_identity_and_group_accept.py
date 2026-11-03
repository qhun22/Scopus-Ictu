# ruff: noqa: F811  (pytest fixtures are imported by name and re-declared as parameters)
"""Main-ID label and group review on a real PostgreSQL test database.

Fixtures are shared with ``test_candidate_review_service`` (same guarded isolated database).
"""

from __future__ import annotations

import importlib.util
import json
import uuid
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
from app.models.lecturer_primary_scopus import LecturerPrimaryScopusEvent
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.services import merge_guide
from app.services.candidate_group_review import (
    GroupDuplicateError,
    GroupItem,
    GroupMismatchError,
    GroupPrimaryNotInGroupError,
    GroupReasonRequiredError,
    GroupSharedAuthorError,
    GroupSizeError,
    accept_group,
)
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateReviewError,
    CandidateReviewService,
    StaleCandidateVersionError,
)
from app.services.primary_scopus_identity import (
    PrimaryIdentityError,
    PrimaryIdentityService,
    explicit_primary,
    primary_view,
)
from app.services.publication_exclusions import PublicationExclusionService
from tests.conftest import disable_append_only_triggers
from tests.db_safety_guard import assert_safe_for_destructive_test
from tests.integration.test_candidate_review_service import (  # noqa: F401  (fixtures + helpers)
    _make_author,
    _make_candidate,
    _make_lecturer,
    _make_observation,
    _make_run,
    _make_user,
    _name_evidence,
    _publication_evidence,
    ready_fixture,
    review_engine,
    review_session,
    session_factory,
)

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "f2b8c3d19a47_lecturer_primary_scopus_events.py")


@pytest.fixture(autouse=True)
def _clean_tables(review_engine):
    def wipe():
        assert_safe_for_destructive_test(review_engine)
        with review_engine.begin() as conn:
            with disable_append_only_triggers(conn):
                conn.execute(text(
                    "TRUNCATE publications, lecturer_publication_exclusion_events, "
                    "lecturer_primary_scopus_events CASCADE"
                ))

    wipe()
    yield
    wipe()


def _second_candidate(session, ready_fixture):
    """A second PENDING candidate for the SAME lecturer, in the same generation run."""
    author = _make_author(session)
    candidate = LecturerScopusCandidate(
        lecturer_id=ready_fixture["lecturer_id"], scopus_author_id=author.id, status="PENDING")
    session.add(candidate)
    session.flush()
    obs = _make_observation(session, candidate=candidate, run=ready_fixture["run"],
                            evidence=[_name_evidence(), _publication_evidence()])
    session.commit()
    return candidate, obs, author


def _items(ready_fixture, candidate2, obs2):
    first = ready_fixture["candidate"]
    return [GroupItem(first.id, ready_fixture["observation"].id, first.version),
            GroupItem(candidate2.id, obs2.id, candidate2.version)]


def _link_publications(session, author, count):
    """Give an author ``count`` distinct publications."""
    ids = []
    for n in range(count):
        pub = Publication(eid=f"2-s2.0-{uuid.uuid4().int % 10**10:010d}", title=f"P{n}",
                          title_normalized=f"p{n}", year=2025)
        session.add(pub)
        session.flush()
        session.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=author.id,
                                      author_order=1))
        ids.append(pub.id)
    session.commit()
    return ids


def _admin(session):
    admin = _make_user(session, role="ADMIN")
    session.commit()
    return admin


# -- group accept -------------------------------------------------------------------------

def test_group_accept_creates_every_identity_in_one_transaction_with_a_main_id(
        review_session, ready_fixture):
    c2, o2, a2 = _second_candidate(review_session, ready_fixture)
    reviewer = ready_fixture["reviewer"]
    lecturer_id = ready_fixture["lecturer_id"]
    result = accept_group(review_session, lecturer_id=lecturer_id,
                          items=_items(ready_fixture, c2, o2), reviewer_user_id=reviewer.id,
                          reason="Cùng một người, hai Scopus ID",
                          primary_candidate_id=c2.id)

    assert len(result.results) == 2
    identities = review_session.scalars(select(LecturerScopusIdentity).where(
        LecturerScopusIdentity.lecturer_id == lecturer_id)).all()
    assert sorted(i.status for i in identities) == ["APPROVED", "APPROVED"]
    reasons = review_session.scalars(select(LecturerScopusCandidateReview.reason).where(
        LecturerScopusCandidateReview.action == "ACCEPT")).all()
    assert reasons == ["Cùng một người, hai Scopus ID"] * 2          # the shared reason on each
    # The chosen candidate's identity is the explicit main ID; nothing was merged.
    assert explicit_primary(review_session, lecturer_id) == result.primary_identity_id
    assert result.primary_identity_id == result.results[1].resulting_identity_id
    assert len(identities) == 2


def test_group_accept_is_all_or_nothing(review_session, ready_fixture):
    c2, o2, _ = _second_candidate(review_session, ready_fixture)
    items = _items(ready_fixture, c2, o2)
    stale = [items[0], GroupItem(items[1].candidate_id, items[1].observation_id,
                                 items[1].candidate_version + 7)]       # second member is stale
    with pytest.raises(StaleCandidateVersionError):
        accept_group(review_session, lecturer_id=ready_fixture["lecturer_id"], items=stale,
                     reviewer_user_id=ready_fixture["reviewer"].id, reason="x")
    review_session.rollback()
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 0
    statuses = review_session.scalars(select(LecturerScopusCandidate.status)).all()
    assert statuses == ["PENDING", "PENDING"]                      # the first member was undone
    assert review_session.scalar(text(
        "SELECT count(*) FROM lecturer_scopus_candidate_reviews")) == 0


def test_group_refuses_an_id_that_is_also_proposed_for_another_lecturer(review_session, ready_fixture):
    c2, o2, a2 = _second_candidate(review_session, ready_fixture)
    other = _make_lecturer(review_session, full_name="TS. Namesake")
    review_session.add(LecturerScopusCandidate(
        lecturer_id=other.id, scopus_author_id=a2.id, status="PENDING"))
    review_session.commit()
    with pytest.raises(GroupSharedAuthorError):
        accept_group(review_session, lecturer_id=ready_fixture["lecturer_id"],
                     items=_items(ready_fixture, c2, o2),
                     reviewer_user_id=ready_fixture["reviewer"].id, reason="Cùng một người")
    # nothing was written for the group
    assert review_session.scalars(select(LecturerScopusIdentity)).all() == []


def test_merge_guide_matches_by_email_only_and_is_a_hint(review_session, ready_fixture, tmp_path, monkeypatch):
    lecturer = review_session.get(Lecturer, ready_fixture["lecturer_id"])
    lecturer.email = "Someone@Ictu.edu.vn"
    namesake = _make_lecturer(review_session, full_name=lecturer.full_name)   # same name, other e-mail
    namesake.email = "other@ictu.edu.vn"
    review_session.commit()
    path = tmp_path / "guide.json"
    path.write_text(json.dumps({"source_url": "https://example.invalid/guide", "retrieved_at": "2026-11-02",
                                "entries": [{"email": "someone@ictu.edu.vn", "primary_scopus_id": "57000000002",
                                             "scopus_ids": ["57000000001", "57000000002", "not-an-id"]}]}),
                    encoding="utf-8")
    monkeypatch.setattr(merge_guide.settings, "merge_guide_file", str(path), raising=False)

    guide = merge_guide.load_merge_guide()
    assert guide is not None and guide.source_url == "https://example.invalid/guide"
    found = merge_guide.guides_for_lecturers(review_session, guide, {lecturer.id, namesake.id})
    assert [(g.lecturer_id, g.scopus_ids, g.primary_scopus_id) for g in found] == [
        (lecturer.id, ("57000000001", "57000000002"), "57000000002")]   # matched by e-mail, not by name


def test_review_queue_search_ignores_case_and_diacritics_and_needs_every_word(review_session, ready_fixture):
    from app.api.v1.endpoints.reviews import _queue_statement

    lecturer = review_session.get(Lecturer, ready_fixture["lecturer_id"])
    lecturer.full_name = "TS. Đỗ Đình Cường"
    lecturer.email = "ddcuong@ictu.edu.vn"
    review_session.commit()

    def count(term):
        statement = _queue_statement(candidate_status="PENDING", evidence_category=None,
                                     ambiguity=None, search=term)
        return len(review_session.execute(statement).all())

    assert count(None) == 1
    assert count("do dinh cuong") == 1          # no diacritics, any case
    assert count("CƯỜNG đỗ") == 1               # word order does not matter
    assert count("ddcuong@ictu") == 1           # e-mail
    assert count("do dinh khanh") == 0          # one word missing -> no match
    assert count("%") == 0                      # LIKE wildcards are literal


def test_merge_guide_is_absent_when_the_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(merge_guide.settings, "merge_guide_file", str(tmp_path / "nope.json"), raising=False)
    assert merge_guide.load_merge_guide() is None


def test_group_input_rules(review_session, ready_fixture):
    c2, o2, _ = _second_candidate(review_session, ready_fixture)
    lecturer_id, reviewer = ready_fixture["lecturer_id"], ready_fixture["reviewer"]
    items = _items(ready_fixture, c2, o2)

    def run(**kw):
        args = dict(lecturer_id=lecturer_id, items=items, reviewer_user_id=reviewer.id,
                    reason="lý do")
        args.update(kw)
        with pytest.raises(CandidateReviewError) as exc:
            accept_group(review_session, **args)
        review_session.rollback()
        return type(exc.value)

    assert run(items=items[:1]) is GroupSizeError
    assert run(items=[items[0], items[0]]) is GroupDuplicateError
    assert run(reason="   ") is GroupReasonRequiredError
    assert run(primary_candidate_id=uuid.uuid4()) is GroupPrimaryNotInGroupError
    other = _make_lecturer(review_session, full_name="Giảng viên khác")
    review_session.commit()
    assert run(lecturer_id=other.id) is GroupMismatchError
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 0


# -- main ID label ------------------------------------------------------------------------

def _approved_pair(review_session, ready_fixture):
    c2, o2, a2 = _second_candidate(review_session, ready_fixture)
    result = accept_group(review_session, lecturer_id=ready_fixture["lecturer_id"],
                          items=_items(ready_fixture, c2, o2),
                          reviewer_user_id=ready_fixture["reviewer"].id, reason="nhóm")
    return result, a2


def test_without_a_choice_the_id_with_most_publications_is_only_suggested(
        review_session, ready_fixture):
    result, a2 = _approved_pair(review_session, ready_fixture)
    _link_publications(review_session, a2, 3)
    first_author = review_session.get(
        LecturerScopusCandidate, ready_fixture["candidate"].id).scopus_author_id
    _link_publications(review_session, review_session.get(ScopusAuthor, first_author), 1)
    view = primary_view(review_session, ready_fixture["lecturer_id"])
    assert view.primary_identity_id is None                       # nobody chose yet
    assert view.suggested_identity_id == result.results[1].resulting_identity_id
    assert sorted(view.publication_counts.values()) == [1, 3]


def test_a_reviewer_can_choose_clear_and_rechoose_the_main_id(review_session, ready_fixture):
    result, _ = _approved_pair(review_session, ready_fixture)
    lecturer_id, reviewer = ready_fixture["lecturer_id"], ready_fixture["reviewer"]
    first, second = (r.resulting_identity_id for r in result.results)
    service = PrimaryIdentityService(review_session)

    chosen = service.set_primary(lecturer_id, first, reviewer.id, "ID cũ nhất")
    assert chosen.primary_identity_id == first
    with pytest.raises(PrimaryIdentityError) as dup:
        service.set_primary(lecturer_id, first, reviewer.id, "lặp")
    assert dup.value.code == "ALREADY_PRIMARY"
    rechosen = service.set_primary(lecturer_id, second, reviewer.id, "đổi")
    assert rechosen.primary_identity_id == second
    assert service.clear_primary(lecturer_id, reviewer.id, "bỏ chọn").primary_identity_id is None
    with pytest.raises(PrimaryIdentityError) as none:
        service.clear_primary(lecturer_id, reviewer.id, "lại")
    assert none.value.code == "NO_PRIMARY"
    events = review_session.scalars(select(LecturerPrimaryScopusEvent.action).order_by(
        LecturerPrimaryScopusEvent.seq)).all()
    assert events == ["SET", "SET", "CLEAR"]                       # history is kept
    audit = set(review_session.scalars(select(AuditEvent.action)).all())
    assert {"LECTURER_PRIMARY_SCOPUS_ID_SET", "LECTURER_PRIMARY_SCOPUS_ID_CLEARED"} <= audit


def test_main_id_rules(review_session, ready_fixture):
    result, _ = _approved_pair(review_session, ready_fixture)
    lecturer_id = ready_fixture["lecturer_id"]
    identity = result.results[0].resulting_identity_id
    service = PrimaryIdentityService(review_session)

    def code(call):
        with pytest.raises(PrimaryIdentityError) as exc:
            call()
        review_session.rollback()
        return exc.value.code

    lecturer_user = _make_user(review_session, role="LECTURER")
    admin = _admin(review_session)
    assert code(lambda: service.set_primary(lecturer_id, identity, lecturer_user.id, "x")) == (
        "FORBIDDEN")
    assert code(lambda: service.set_primary(lecturer_id, identity, admin.id, "  ")) == (
        "PRIMARY_REASON_REQUIRED")
    assert code(lambda: service.set_primary(lecturer_id, uuid.uuid4(), admin.id, "x")) == (
        "IDENTITY_NOT_APPROVED_FOR_LECTURER")
    other = _make_lecturer(review_session, full_name="Người khác")
    review_session.commit()
    assert code(lambda: service.set_primary(other.id, identity, admin.id, "x")) == (
        "IDENTITY_NOT_APPROVED_FOR_LECTURER")          # an identity of another lecturer


def test_the_label_lapses_when_its_identity_is_revoked(review_session, ready_fixture):
    from app.services.candidate_review_service import RevokeIdentityCommand

    result, _ = _approved_pair(review_session, ready_fixture)
    lecturer_id = ready_fixture["lecturer_id"]
    admin = _admin(review_session)
    chosen = result.results[0]
    PrimaryIdentityService(review_session).set_primary(
        lecturer_id, chosen.resulting_identity_id, admin.id, "chọn")
    assert explicit_primary(review_session, lecturer_id) == chosen.resulting_identity_id
    candidate = review_session.get(LecturerScopusCandidate, chosen.candidate_id)
    CandidateReviewService(review_session).revoke_identity(RevokeIdentityCommand(
        candidate_id=candidate.id, candidate_version=candidate.version,
        admin_user_id=admin.id, reason="thu hồi"))
    assert explicit_primary(review_session, lecturer_id) is None   # label lapses, history stays
    assert review_session.scalar(text(
        "SELECT count(*) FROM lecturer_primary_scopus_events")) == 1


def test_withdrawn_papers_do_not_count_toward_the_suggestion(review_session, ready_fixture):
    result, a2 = _approved_pair(review_session, ready_fixture)
    lecturer_id = ready_fixture["lecturer_id"]
    admin = _admin(review_session)
    papers = _link_publications(review_session, a2, 3)
    first_author = review_session.get(
        LecturerScopusCandidate, ready_fixture["candidate"].id).scopus_author_id
    _link_publications(review_session, review_session.get(ScopusAuthor, first_author), 2)
    assert primary_view(review_session, lecturer_id).suggested_identity_id == (
        result.results[1].resulting_identity_id)
    for pub in papers[:2]:                                  # withdraw two of the three
        PublicationExclusionService(review_session).exclude(lecturer_id, pub, admin.id, "lẫn")
    assert primary_view(review_session, lecturer_id).suggested_identity_id == (
        result.results[0].resulting_identity_id)


# -- the migration's append-only guard ----------------------------------------------------

def test_migration_makes_the_label_history_append_only(review_engine):
    schema = f"lpse_{uuid.uuid4().hex}"
    with review_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(review_engine.url, future=True, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=30000"})
    try:
        Base.metadata.create_all(bind=engine, tables=[
            t for n, t in Base.metadata.tables.items()
            if n != LecturerPrimaryScopusEvent.__tablename__])
        spec = importlib.util.spec_from_file_location("lpse_mig", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(
                    conn, opts={"target_metadata": Base.metadata})):
                module.upgrade()
        with engine.begin() as conn:
            live = {r[0] for r in conn.execute(text(
                "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = :s "
                "AND t.relname = 'lecturer_primary_scopus_events'"), {"s": schema})}
        model = {str(c.name) for c in LecturerPrimaryScopusEvent.__table__.constraints if c.name}
        assert model <= live, model - live
        with engine.begin() as conn:
            uid, lid = uuid.uuid4(), uuid.uuid4()
            conn.execute(text("INSERT INTO users (id, email, password_hash, display_name, role, "
                              "is_active, version, auth_version) VALUES (:i, :e, 'x', 'x', "
                              "'ADMIN', true, 1, 1)"), {"i": uid, "e": f"{uid.hex}@t.local"})
            conn.execute(text("INSERT INTO lecturers (id, full_name, full_name_normalized, "
                              "version) VALUES (:i, 'L', 'l', 1)"), {"i": lid})
        with pytest.raises(DatabaseError, match="identity_matches_action"), engine.begin() as conn:
            conn.execute(text(                              # SET without an identity is refused
                "INSERT INTO lecturer_primary_scopus_events (lecturer_id, action, reason, "
                "acted_by_user_id) VALUES (:l, 'SET', 'r', :u)"), {"l": lid, "u": uid})
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO lecturer_primary_scopus_events (lecturer_id, action, reason, "
                "acted_by_user_id) VALUES (:l, 'CLEAR', 'r', :u)"), {"l": lid, "u": uid})
        for statement in ("UPDATE lecturer_primary_scopus_events SET reason = 'z'",
                          "DELETE FROM lecturer_primary_scopus_events",
                          "TRUNCATE lecturer_primary_scopus_events"):
            with pytest.raises(DatabaseError, match="append-only"), engine.begin() as conn:
                conn.execute(text(statement))
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(review_engine)
        with review_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_retrying_a_group_after_one_member_was_already_accepted_is_safe(
        review_session, ready_fixture):
    """The single-decision idempotency still applies per member: a retry does not duplicate."""
    c2, o2, _ = _second_candidate(review_session, ready_fixture)
    items = _items(ready_fixture, c2, o2)
    reviewer = ready_fixture["reviewer"]
    first = ready_fixture["candidate"]
    CandidateReviewService(review_session).accept_candidate(AcceptCandidateCommand(
        candidate_id=first.id, observation_id=ready_fixture["observation"].id,
        candidate_version=first.version, reviewer_user_id=reviewer.id, reason="đã duyệt trước"))
    retry = [GroupItem(first.id, ready_fixture["observation"].id, 1), items[1]]
    result = accept_group(review_session, lecturer_id=ready_fixture["lecturer_id"],
                          items=retry, reviewer_user_id=reviewer.id, reason="nhóm")
    assert [r.idempotent for r in result.results] == [True, False]
    assert review_session.scalar(text("SELECT count(*) FROM lecturer_scopus_identities")) == 2
