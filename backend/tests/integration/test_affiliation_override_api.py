"""Priority 2: ADMIN manual affiliation review (needs-review list, create/update/
delete an override), isolated schema per test.

An override never writes to publication_author_affiliation(_resolutions) or
touches raw Scopus data — only its own additive table. CORROBORATED/UNRESOLVED
are the only confidence levels an override can carry; it can never assert
VERIFIED.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.affiliation_override import PublicationAuthorAffiliationOverride
from app.models.base import Base
from app.models.governance import AuditEvent, User
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.services import affiliation_override_service as override_service
from app.services.affiliation_import import AffiliationImportService, ResolutionInput

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_t2_override_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, future=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, future=True, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(), email=f"{role.lower()}-{uuid.uuid4().hex[:6]}@override.test", password_hash="x",
        display_name=role, role=role, lecturer_id=None, is_active=True, version=1, auth_version=1,
        created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def as_role(db: Session):
    def _as(role: str) -> User:
        user = _user(role)
        db.add(user)
        db.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _as


def _pub(eid: str) -> Publication:
    return Publication(
        id=uuid.uuid4(), eid=eid, doi=f"10.1/{eid.lower()}", title=f"Title {eid}", title_normalized=f"title {eid}".casefold(),
        source_title=None, year=2024, volume=None, issue=None, art_no=None, page_start=None, page_end=None,
        cited_by_count=0, document_type="Article", publication_stage="Final", open_access_status=None,
        version=1, created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def world(db: Session) -> dict:
    """E1 has 2 authors: 111 (will be UNRESOLVED), 222 (will be CORROBORATED only).
    E2 has 1 author: 444, never reconciled at all (NOT_RECONCILED, out of needs-review scope)."""

    p1, p2 = _pub("E1"), _pub("E2")
    authors = {sid: ScopusAuthor(scopus_id=sid, preferred_name=f"Author {sid}") for sid in ("111", "222", "444")}
    db.add_all([p1, p2, *authors.values()])
    db.flush()
    pa1 = PublicationAuthor(publication_id=p1.id, scopus_author_id=authors["111"].id, author_order=1)
    pa2 = PublicationAuthor(publication_id=p1.id, scopus_author_id=authors["222"].id, author_order=2)
    pa4 = PublicationAuthor(publication_id=p2.id, scopus_author_id=authors["444"].id, author_order=1)
    db.add_all([pa1, pa2, pa4])
    db.flush()

    H1 = "1" * 64
    H2 = "2" * 64
    AffiliationImportService().apply(
        db,
        [
            ResolutionInput(
                eid="E1", scopus_id="111", author_order=1, source_system="openalex", payload_sha256=H1,
                link_status="UNRESOLVED", unresolved_reason="NAME_MISMATCH", doi="10.1/e1",
            ),
            ResolutionInput(
                eid="E1", scopus_id="222", author_order=2, source_system="openalex", payload_sha256=H2,
                link_status="CORROBORATED", link_method="POSITION_COUNT_NAME",
                evidence={"name_tokens_equal": True}, doi="10.1/e1", source_doi="10.1/e1", source_work_id="w1",
                external_position=2, external_author_name="Ext 222", retrieved_at=NOW, entries=(),
            ),
        ],
    )
    db.commit()
    return {"p1": p1, "p2": p2, "pa1": pa1, "pa2": pa2, "pa4": pa4}


# --------------------------------------------------------------------------- RBAC
@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_use_needs_review_and_overrides(client, as_role, role, world) -> None:
    as_role(role)
    assert client.get("/api/v1/affiliations/needs-review").status_code == 403
    body = {"affiliation_text": "X", "confidence": "CORROBORATED", "evidence_url": "https://x", "reason": "r"}
    assert client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body).status_code == 403


def test_anonymous_is_unauthenticated(client) -> None:
    assert client.get("/api/v1/affiliations/needs-review").status_code == 401


# --------------------------------------------------------------------------- needs-review listing
def test_needs_review_lists_unresolved_and_corroborated_not_not_reconciled(client, as_role, world) -> None:
    as_role("ADMIN")
    resp = client.get("/api/v1/affiliations/needs-review")
    assert resp.status_code == 200
    body = resp.json()
    kinds = {item["eid"]: item["reason_kind"] for item in body["items"]}
    assert kinds == {"E1": "UNRESOLVED"} or set(kinds) == {"E1"}
    # both E1 authors appear (111 UNRESOLVED, 222 CORROBORATED-only); E2/444 never reconciled -> absent
    eids_orders = {(item["eid"], item["author_order"]) for item in body["items"]}
    assert ("E1", 1) in eids_orders  # 111, UNRESOLVED
    assert ("E1", 2) in eids_orders  # 222, CORROBORATED only -> LOW_CONFIDENCE
    assert ("E2", 1) not in eids_orders  # 444, NOT_RECONCILED, out of scope
    item_111 = next(i for i in body["items"] if i["author_order"] == 1)
    item_222 = next(i for i in body["items"] if i["author_order"] == 2)
    assert item_111["reason_kind"] == "UNRESOLVED"
    assert item_222["reason_kind"] == "LOW_CONFIDENCE"
    assert item_111["has_override"] is False


# --------------------------------------------------------------------------- create / update
def test_admin_creates_override_with_evidence_and_reason(client, as_role, db, world) -> None:
    admin = as_role("ADMIN")
    body = {
        "affiliation_text": "Khoa Công nghệ Thông tin, Đại học X",
        "confidence": "CORROBORATED",
        "evidence_url": "https://example.edu.vn/staff/111",
        "reason": "Trang nhân sự chính thức của trường liệt kê đúng tên và chức danh.",
    }
    resp = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == 1
    assert data["created_by_user_id"] == str(admin.id)

    row = db.scalar(select(PublicationAuthorAffiliationOverride))
    assert row.affiliation_text == body["affiliation_text"]
    assert row.confidence == "CORROBORATED"

    audits = db.scalars(select(AuditEvent).where(AuditEvent.action == override_service.CREATED_ACTION)).all()
    assert len(audits) == 1
    assert audits[0].actor_user_id == admin.id
    assert audits[0].before_state is None
    assert audits[0].after_state["affiliation_text"] == body["affiliation_text"]


def test_missing_reason_or_evidence_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    base = {"affiliation_text": "X", "confidence": "CORROBORATED", "evidence_url": "https://x", "reason": "r"}
    for field in ("evidence_url", "reason", "affiliation_text"):
        body = {**base, field: "   "}
        resp = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body)
        assert resp.status_code == 422, f"{field} should be rejected: {resp.text}"


def test_invalid_confidence_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    body = {"affiliation_text": "X", "confidence": "VERIFIED", "evidence_url": "https://x", "reason": "r"}
    resp = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body)
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_CONFIDENCE"


def test_unknown_publication_author_is_404(client, as_role) -> None:
    as_role("ADMIN")
    body = {"affiliation_text": "X", "confidence": "CORROBORATED", "evidence_url": "https://x", "reason": "r"}
    resp = client.put(f"/api/v1/affiliations/overrides/{uuid.uuid4()}", json=body)
    assert resp.status_code == 404
    assert resp.json()["code"] == "PUBLICATION_AUTHOR_NOT_FOUND"


def test_update_requires_correct_expected_version_and_records_before_after(client, as_role, db, world) -> None:
    admin = as_role("ADMIN")
    create_body = {"affiliation_text": "V1", "confidence": "UNRESOLVED", "evidence_url": "https://x/1", "reason": "r1"}
    created = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body).json()
    assert created["version"] == 1

    update_body = {
        "affiliation_text": "V2 updated",
        "confidence": "CORROBORATED",
        "evidence_url": "https://x/2",
        "reason": "r2 - sửa theo bằng chứng mới",
        "expected_version": 1,
    }
    resp = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=update_body)
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["version"] == 2
    assert updated["affiliation_text"] == "V2 updated"

    audits = db.scalars(
        select(AuditEvent).where(AuditEvent.action == override_service.UPDATED_ACTION)
    ).all()
    assert len(audits) == 1
    assert audits[0].before_state["affiliation_text"] == "V1"
    assert audits[0].after_state["affiliation_text"] == "V2 updated"


def test_update_with_stale_version_is_refused(client, as_role, world) -> None:
    as_role("ADMIN")
    create_body = {"affiliation_text": "V1", "confidence": "UNRESOLVED", "evidence_url": "https://x", "reason": "r"}
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)

    stale_body = {
        "affiliation_text": "V2",
        "confidence": "CORROBORATED",
        "evidence_url": "https://x/2",
        "reason": "r2",
        "expected_version": 99,  # wrong
    }
    resp = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=stale_body)
    assert resp.status_code == 409
    assert resp.json()["code"] == "STALE_OVERRIDE_VERSION"


def test_two_admins_editing_same_position_concurrently_second_commit_is_refused(client, as_role, db, world) -> None:
    """Simulates sequential-but-stale edits: both load version 1, ADMIN A
    commits first, ADMIN B's commit (still believing version=1) must be refused,
    never silently overwriting A's edit."""

    admin_a = as_role("ADMIN")
    create_body = {"affiliation_text": "Base", "confidence": "UNRESOLVED", "evidence_url": "https://x", "reason": "r0"}
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)

    a_body = {
        "affiliation_text": "A's edit",
        "confidence": "CORROBORATED",
        "evidence_url": "https://x/a",
        "reason": "A reviewed first",
        "expected_version": 1,
    }
    resp_a = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=a_body)
    assert resp_a.status_code == 200
    assert resp_a.json()["version"] == 2

    b_body = {
        "affiliation_text": "B's edit (stale)",
        "confidence": "CORROBORATED",
        "evidence_url": "https://x/b",
        "reason": "B reviewed, unaware of A",
        "expected_version": 1,  # B still thinks it's version 1
    }
    resp_b = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=b_body)
    assert resp_b.status_code == 409
    assert resp_b.json()["code"] == "STALE_OVERRIDE_VERSION"

    row = db.scalar(select(PublicationAuthorAffiliationOverride))
    assert row.affiliation_text == "A's edit"  # B's write never applied


# --------------------------------------------------------------------------- delete
def test_delete_override_removes_row_and_audits_without_touching_automated_resolution(
    client, as_role, db, world
) -> None:
    from app.models.affiliation import PublicationAuthorAffiliationResolution

    admin = as_role("ADMIN")
    before_resolution = db.scalar(select(PublicationAuthorAffiliationResolution)).unresolved_reason
    create_body = {"affiliation_text": "V1", "confidence": "UNRESOLVED", "evidence_url": "https://x", "reason": "r"}
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)

    resp = client.request(
        "DELETE", f"/api/v1/affiliations/overrides/{world['pa1'].id}?expected_version=1"
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert db.scalar(select(PublicationAuthorAffiliationOverride)) is None

    # the automated (system) resolution underneath is untouched
    after_resolution = db.scalar(select(PublicationAuthorAffiliationResolution)).unresolved_reason
    assert after_resolution == before_resolution == "NAME_MISMATCH"

    audits = db.scalars(select(AuditEvent).where(AuditEvent.action == override_service.DELETED_ACTION)).all()
    assert len(audits) == 1


def test_delete_with_wrong_version_is_refused(client, as_role, world) -> None:
    as_role("ADMIN")
    create_body = {"affiliation_text": "V1", "confidence": "UNRESOLVED", "evidence_url": "https://x", "reason": "r"}
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)
    resp = client.request(
        "DELETE", f"/api/v1/affiliations/overrides/{world['pa1'].id}?expected_version=99"
    )
    assert resp.status_code == 409


def test_delete_unknown_override_is_404(client, as_role, world) -> None:
    as_role("ADMIN")
    resp = client.request(
        "DELETE", f"/api/v1/affiliations/overrides/{world['pa1'].id}?expected_version=1"
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "OVERRIDE_NOT_FOUND"


# --------------------------------------------------------------------------- publication detail surfaces the override, public-safe
def test_publication_detail_shows_override_without_leaking_internal_ids(client, as_role, world) -> None:
    admin = as_role("ADMIN")
    body = {
        "affiliation_text": "Khoa CNTT",
        "confidence": "CORROBORATED",
        "evidence_url": "https://example.edu.vn/111",
        "reason": "Xác nhận qua trang nhân sự",
    }
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body)

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert author_1["affiliation_override"] is not None
    assert author_1["affiliation_override"]["affiliation_text"] == "Khoa CNTT"
    assert author_1["affiliation_override"]["confidence"] == "CORROBORATED"
    blob = str(detail)
    assert "publication_author_id" not in blob
    assert str(world["pa1"].id) not in blob
    assert str(admin.id) not in blob  # created_by/updated_by not leaked either


def test_override_never_appears_as_verified_in_affiliation_status(client, as_role, world) -> None:
    """Creating an override must not change author.affiliation_status computed
    from the automated resolutions — it is a parallel, clearly-labeled layer,
    never promoted into the VERIFIED/CORROBORATED pipeline status itself."""

    as_role("ADMIN")
    body = {"affiliation_text": "X", "confidence": "CORROBORATED", "evidence_url": "https://x", "reason": "r"}
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=body)

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    # the automated resolution for author 1 is UNRESOLVED; an override must not change that
    assert author_1["affiliation_status"] == "UNRESOLVED"


# --------------------------------------------------------------------------- DB-level constraint, transaction rollback
def test_db_check_constraint_rejects_verified_confidence_bypassing_the_service(db, world, as_role) -> None:
    """Defense in depth: even a direct ORM insert that skips the service's own
    validation must be rejected by the DB CHECK constraint — confidence can
    never be VERIFIED at the database level, not just the API level."""

    from sqlalchemy.exc import IntegrityError

    admin = as_role("ADMIN")
    bad = PublicationAuthorAffiliationOverride(
        publication_author_id=world["pa1"].id,
        affiliation_text="X",
        confidence="VERIFIED",  # bypasses override_service._validate entirely
        evidence_url="https://x",
        reason="r",
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    assert db.scalar(select(PublicationAuthorAffiliationOverride)) is None  # no partial row left behind


# --------------------------------------------------------------------------- compatibility with re-collection
def test_re_applying_automated_resolutions_never_touches_an_existing_override(client, as_role, db, world) -> None:
    """A later online-enrichment or offline-bundle apply() run (simulated here
    by calling AffiliationImportService().apply again with a new payload for
    the same author position) must leave the ADMIN's override completely
    untouched — the two layers are stored in different tables and the
    automated writer never references publication_author_affiliation_overrides."""

    admin = as_role("ADMIN")
    override_body = {
        "affiliation_text": "Khoa CNTT (ADMIN xác nhận thủ công)",
        "confidence": "CORROBORATED",
        "evidence_url": "https://example.edu.vn/111",
        "reason": "Xác nhận qua hồ sơ nhân sự trước khi có nguồn tự động mới",
    }
    created = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=override_body)
    assert created.status_code == 200

    # Simulate a new automated collection run (e.g. the online enrichment job
    # from Priority 1) producing a DIFFERENT payload for the same author/source.
    H_NEW = "9" * 64
    AffiliationImportService().apply(
        db,
        [
            ResolutionInput(
                eid="E1", scopus_id="111", author_order=1, source_system="crossref", payload_sha256=H_NEW,
                link_status="CORROBORATED", link_method="POSITION_COUNT_NAME",
                evidence={"name_tokens_equal": True}, doi="10.1/e1", source_doi="10.1/e1", source_work_id="w2",
                external_position=1, external_author_name="Ext 111", retrieved_at=NOW, entries=(),
            ),
        ],
    )

    override_after = db.scalar(select(PublicationAuthorAffiliationOverride))
    assert override_after is not None
    assert override_after.version == 1  # untouched — still exactly what the ADMIN entered
    assert override_after.affiliation_text == "Khoa CNTT (ADMIN xác nhận thủ công)"

    # the publication detail still shows BOTH layers side by side, not merged/overwritten
    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert author_1["affiliation_override"]["affiliation_text"] == "Khoa CNTT (ADMIN xác nhận thủ công)"
    # the new automated resolution is visible too, as a separate resolution entry
    sources = {r["source_system"] for r in author_1["affiliation_resolutions"]}
    assert "crossref" in sources


# --------------------------------------------------------------------------- regression: needs-review AFTER an override exists
def test_needs_review_still_works_after_an_override_was_created(client, as_role, world) -> None:
    """Regression test: list_needs_review must correctly read back the set of
    publication_author_ids that already have an override (has_override=True),
    without crashing, once at least one override row exists in the table."""

    as_role("ADMIN")
    create_body = {
        "affiliation_text": "Khoa CNTT", "confidence": "CORROBORATED",
        "evidence_url": "https://x", "reason": "r",
    }
    created = client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)
    assert created.status_code == 200

    resp = client.get("/api/v1/affiliations/needs-review")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    item_1 = next(i for i in body["items"] if i["author_order"] == 1)
    item_2 = next(i for i in body["items"] if i["author_order"] == 2)
    assert item_1["has_override"] is True
    assert item_2["has_override"] is False


def test_needs_review_returns_full_override_for_prefilling_the_edit_form(client, as_role, world) -> None:
    """The ADMIN review UI needs the full override (text/confidence/evidence/
    reason/version) to pre-fill the edit form without a second round-trip."""

    as_role("ADMIN")
    create_body = {
        "affiliation_text": "Khoa CNTT", "confidence": "UNRESOLVED",
        "evidence_url": "https://x/evidence", "reason": "ly do ban dau",
    }
    client.put(f"/api/v1/affiliations/overrides/{world['pa1'].id}", json=create_body)

    resp = client.get("/api/v1/affiliations/needs-review")
    item_1 = next(i for i in resp.json()["items"] if i["author_order"] == 1)
    assert item_1["override"] is not None
    assert item_1["override"]["affiliation_text"] == "Khoa CNTT"
    assert item_1["override"]["confidence"] == "UNRESOLVED"
    assert item_1["override"]["evidence_url"] == "https://x/evidence"
    assert item_1["override"]["version"] == 1

    item_2 = next(i for i in resp.json()["items"] if i["author_order"] == 2)
    assert item_2["override"] is None
