"""NO-JSON closure: ADMIN manual affiliation review with MULTIPLE independent
overrides per author position (add/update/revoke), isolated schema per test.

An override never writes to publication_author_affiliation(_resolutions) or
touches raw Scopus data — only its own additive table. CORROBORATED/UNRESOLVED
are the only confidence levels an override can carry; it can never assert
VERIFIED. A position may carry several ACTIVE overrides at once (dual
appointment); each has its own add/update/revoke lifecycle, scoped to that
one row only.
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

NOW = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_nojson_override_{uuid.uuid4().hex}"
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


def _add(client, publication_author_id, **overrides) -> dict:
    body = {
        "publication_author_id": str(publication_author_id),
        "affiliation_text": "X",
        "confidence": "CORROBORATED",
        "evidence_url": "https://x",
        "reason": "r",
    }
    body.update(overrides)
    resp = client.post("/api/v1/affiliations/overrides", json=body)
    return resp


# --------------------------------------------------------------------------- RBAC
@pytest.mark.parametrize("role", ["LECTURER", "REVIEWER"])
def test_only_admin_can_use_needs_review_and_overrides(client, as_role, role, world) -> None:
    as_role(role)
    assert client.get("/api/v1/affiliations/needs-review").status_code == 403
    assert _add(client, world["pa1"].id).status_code == 403


def test_anonymous_is_unauthenticated(client) -> None:
    assert client.get("/api/v1/affiliations/needs-review").status_code == 401


# --------------------------------------------------------------------------- needs-review listing
def test_needs_review_lists_unresolved_and_corroborated_not_not_reconciled(client, as_role, world) -> None:
    as_role("ADMIN")
    resp = client.get("/api/v1/affiliations/needs-review")
    assert resp.status_code == 200
    body = resp.json()
    eids_orders = {(item["eid"], item["author_order"]) for item in body["items"]}
    assert ("E1", 1) in eids_orders  # 111, UNRESOLVED
    assert ("E1", 2) in eids_orders  # 222, CORROBORATED only -> LOW_CONFIDENCE
    assert ("E2", 1) not in eids_orders  # 444, NOT_RECONCILED, out of scope
    item_111 = next(i for i in body["items"] if i["author_order"] == 1)
    item_222 = next(i for i in body["items"] if i["author_order"] == 2)
    assert item_111["reason_kind"] == "UNRESOLVED"
    assert item_222["reason_kind"] == "LOW_CONFIDENCE"
    assert item_111["has_override"] is False
    assert item_111["overrides"] == []


# --------------------------------------------------------------------------- add
def test_admin_adds_override_with_evidence_and_reason(client, as_role, db, world) -> None:
    admin = as_role("ADMIN")
    resp = _add(
        client, world["pa1"].id,
        affiliation_text="Khoa Công nghệ Thông tin, Đại học X",
        confidence="CORROBORATED",
        evidence_url="https://example.edu.vn/staff/111",
        reason="Trang nhân sự chính thức của trường liệt kê đúng tên và chức danh.",
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["version"] == 1
    assert data["status"] == "ACTIVE"
    assert data["created_by_user_id"] == str(admin.id)

    row = db.scalar(select(PublicationAuthorAffiliationOverride))
    assert row.affiliation_text == "Khoa Công nghệ Thông tin, Đại học X"
    assert row.confidence == "CORROBORATED"
    assert row.status == "ACTIVE"

    audits = db.scalars(select(AuditEvent).where(AuditEvent.action == override_service.CREATED_ACTION)).all()
    assert len(audits) == 1
    assert audits[0].actor_user_id == admin.id
    assert audits[0].before_state is None


def test_missing_reason_or_evidence_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    for field in ("evidence_url", "reason", "affiliation_text"):
        resp = _add(client, world["pa1"].id, **{field: "   "})
        assert resp.status_code == 422, f"{field} should be rejected: {resp.text}"


def test_invalid_confidence_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    resp = _add(client, world["pa1"].id, confidence="VERIFIED")
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_CONFIDENCE"


def test_unknown_publication_author_is_404(client, as_role) -> None:
    as_role("ADMIN")
    resp = _add(client, uuid.uuid4())
    assert resp.status_code == 404
    assert resp.json()["code"] == "PUBLICATION_AUTHOR_NOT_FOUND"


# --------------------------------------------------------------------------- MULTIPLE overrides per position
def test_one_position_can_have_two_independent_active_overrides(client, as_role, db, world) -> None:
    """Dual appointment: the same author position gets two ACTIVE overrides
    with different unit text. Both must coexist."""

    as_role("ADMIN")
    first = _add(client, world["pa1"].id, affiliation_text="University A", reason="Primary appointment")
    second = _add(client, world["pa1"].id, affiliation_text="Institute B", reason="Secondary appointment")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    rows = db.scalars(select(PublicationAuthorAffiliationOverride)).all()
    assert len(rows) == 2
    assert {r.affiliation_text for r in rows} == {"University A", "Institute B"}
    assert all(r.status == "ACTIVE" for r in rows)

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert {o["affiliation_text"] for o in author_1["affiliation_overrides"]} == {"University A", "Institute B"}


def test_duplicate_active_text_on_same_position_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    first = _add(client, world["pa1"].id, affiliation_text="University A")
    assert first.status_code == 201
    second = _add(client, world["pa1"].id, affiliation_text="University A")
    assert second.status_code == 409
    assert second.json()["code"] == "DUPLICATE_ACTIVE_OVERRIDE"


def test_revoke_then_readd_identical_text_is_allowed(client, as_role, world) -> None:
    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="University A").json()
    revoke_resp = client.post(
        f"/api/v1/affiliations/overrides/{created['id']}/revoke",
        json={"reason": "No longer accurate", "expected_version": created["version"]},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"

    readd = _add(client, world["pa1"].id, affiliation_text="University A")
    assert readd.status_code == 201, readd.text


def test_editing_one_override_never_touches_a_sibling_override(client, as_role, db, world) -> None:
    as_role("ADMIN")
    a = _add(client, world["pa1"].id, affiliation_text="University A").json()
    b = _add(client, world["pa1"].id, affiliation_text="Institute B").json()

    update_resp = client.put(
        f"/api/v1/affiliations/overrides/{a['id']}",
        json={
            "affiliation_text": "University A (renamed)",
            "confidence": "CORROBORATED",
            "evidence_url": "https://x/new",
            "reason": "typo fix",
            "expected_version": a["version"],
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["affiliation_text"] == "University A (renamed)"

    b_unchanged = db.get(PublicationAuthorAffiliationOverride, uuid.UUID(b["id"]))
    assert b_unchanged.affiliation_text == "Institute B"
    assert b_unchanged.version == 1


def test_revoking_one_override_never_touches_a_sibling_override(client, as_role, db, world) -> None:
    as_role("ADMIN")
    a = _add(client, world["pa1"].id, affiliation_text="University A").json()
    b = _add(client, world["pa1"].id, affiliation_text="Institute B").json()

    revoke_resp = client.post(
        f"/api/v1/affiliations/overrides/{a['id']}/revoke",
        json={"reason": "Ended appointment", "expected_version": a["version"]},
    )
    assert revoke_resp.status_code == 200

    a_row = db.get(PublicationAuthorAffiliationOverride, uuid.UUID(a["id"]))
    b_row = db.get(PublicationAuthorAffiliationOverride, uuid.UUID(b["id"]))
    assert a_row.status == "REVOKED"
    assert b_row.status == "ACTIVE"  # sibling untouched

    # revoked row is kept for audit, not deleted
    assert db.scalar(select(PublicationAuthorAffiliationOverride).where(PublicationAuthorAffiliationOverride.id == a_row.id)) is not None

    # the public-safe publication detail only shows the still-active one
    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert [o["affiliation_text"] for o in author_1["affiliation_overrides"]] == ["Institute B"]


def test_revoked_override_history_survives_in_audit_and_admin_view(client, as_role, db, world) -> None:
    as_role("ADMIN")
    a = _add(client, world["pa1"].id, affiliation_text="University A").json()
    client.post(
        f"/api/v1/affiliations/overrides/{a['id']}/revoke",
        json={"reason": "Ended appointment", "expected_version": a["version"]},
    )

    audits = db.scalars(
        select(AuditEvent).where(AuditEvent.action == override_service.REVOKED_ACTION)
    ).all()
    assert len(audits) == 1
    assert audits[0].before_state["status"] == "ACTIVE"
    assert audits[0].after_state["status"] == "REVOKED"

    resp = client.get("/api/v1/affiliations/needs-review")
    item_1 = next(i for i in resp.json()["items"] if i["author_order"] == 1)
    statuses = {o["status"] for o in item_1["overrides"]}
    assert statuses == {"REVOKED"}
    assert item_1["has_override"] is False  # no ACTIVE override remains


# --------------------------------------------------------------------------- update / revoke errors
def test_update_requires_correct_expected_version_and_records_before_after(client, as_role, db, world) -> None:
    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="V1", confidence="UNRESOLVED", evidence_url="https://x/1", reason="r1").json()
    assert created["version"] == 1

    resp = client.put(
        f"/api/v1/affiliations/overrides/{created['id']}",
        json={
            "affiliation_text": "V2 updated", "confidence": "CORROBORATED",
            "evidence_url": "https://x/2", "reason": "r2 - sửa theo bằng chứng mới",
            "expected_version": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["version"] == 2
    assert updated["affiliation_text"] == "V2 updated"

    audits = db.scalars(select(AuditEvent).where(AuditEvent.action == override_service.UPDATED_ACTION)).all()
    assert len(audits) == 1
    assert audits[0].before_state["affiliation_text"] == "V1"
    assert audits[0].after_state["affiliation_text"] == "V2 updated"


def test_update_with_stale_version_is_refused(client, as_role, world) -> None:
    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="V1", confidence="UNRESOLVED").json()
    resp = client.put(
        f"/api/v1/affiliations/overrides/{created['id']}",
        json={
            "affiliation_text": "V2", "confidence": "CORROBORATED",
            "evidence_url": "https://x/2", "reason": "r2", "expected_version": 99,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "STALE_OVERRIDE_VERSION"


def test_two_admins_editing_same_override_concurrently_second_commit_is_refused(client, as_role, db, world) -> None:
    """Simulates sequential-but-stale edits: both load version 1, ADMIN A
    commits first, ADMIN B's commit (still believing version=1) must be refused,
    never silently overwriting A's edit."""

    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="Base", confidence="UNRESOLVED").json()

    resp_a = client.put(
        f"/api/v1/affiliations/overrides/{created['id']}",
        json={
            "affiliation_text": "A's edit", "confidence": "CORROBORATED",
            "evidence_url": "https://x/a", "reason": "A reviewed first", "expected_version": 1,
        },
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["version"] == 2

    resp_b = client.put(
        f"/api/v1/affiliations/overrides/{created['id']}",
        json={
            "affiliation_text": "B's edit (stale)", "confidence": "CORROBORATED",
            "evidence_url": "https://x/b", "reason": "B reviewed, unaware of A", "expected_version": 1,
        },
    )
    assert resp_b.status_code == 409
    assert resp_b.json()["code"] == "STALE_OVERRIDE_VERSION"

    row = db.get(PublicationAuthorAffiliationOverride, uuid.UUID(created["id"]))
    assert row.affiliation_text == "A's edit"  # B's write never applied


def test_revoking_already_revoked_override_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="V1").json()
    first = client.post(
        f"/api/v1/affiliations/overrides/{created['id']}/revoke",
        json={"reason": "r", "expected_version": created["version"]},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/affiliations/overrides/{created['id']}/revoke",
        json={"reason": "r2", "expected_version": first.json()["version"]},
    )
    assert second.status_code == 409
    assert second.json()["code"] == "OVERRIDE_ALREADY_REVOKED"


def test_revoke_missing_reason_is_rejected(client, as_role, world) -> None:
    as_role("ADMIN")
    created = _add(client, world["pa1"].id, affiliation_text="V1").json()
    resp = client.post(
        f"/api/v1/affiliations/overrides/{created['id']}/revoke",
        json={"reason": "   ", "expected_version": created["version"]},
    )
    assert resp.status_code == 422


def test_update_unknown_override_is_404(client, as_role, world) -> None:
    as_role("ADMIN")
    resp = client.put(
        f"/api/v1/affiliations/overrides/{uuid.uuid4()}",
        json={"affiliation_text": "X", "confidence": "CORROBORATED", "evidence_url": "https://x", "reason": "r", "expected_version": 1},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "OVERRIDE_NOT_FOUND"


# --------------------------------------------------------------------------- publication detail surfaces overrides, public-safe
def test_publication_detail_shows_overrides_without_leaking_internal_ids(client, as_role, world) -> None:
    admin = as_role("ADMIN")
    _add(
        client, world["pa1"].id, affiliation_text="Khoa CNTT", confidence="CORROBORATED",
        evidence_url="https://example.edu.vn/111", reason="Xác nhận qua trang nhân sự",
    )

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert len(author_1["affiliation_overrides"]) == 1
    assert author_1["affiliation_overrides"][0]["affiliation_text"] == "Khoa CNTT"
    assert author_1["affiliation_overrides"][0]["confidence"] == "CORROBORATED"
    blob = str(detail)
    assert "publication_author_id" not in blob
    assert str(world["pa1"].id) not in blob
    assert str(admin.id) not in blob  # created_by/updated_by not leaked either


def test_override_never_appears_as_verified_in_affiliation_status(client, as_role, world) -> None:
    """Adding an override must not change author.affiliation_status computed
    from the automated resolutions — it is a parallel, clearly-labeled layer,
    never promoted into the VERIFIED/CORROBORATED pipeline status itself."""

    as_role("ADMIN")
    _add(client, world["pa1"].id, confidence="CORROBORATED")

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
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
        confidence="VERIFIED",  # bypasses override_service._validate_text entirely
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


def test_db_check_constraint_rejects_inconsistent_revoked_state(db, world, as_role) -> None:
    """Defense in depth: status=REVOKED without revoked_at/revoked_by, or
    status=ACTIVE with them set, must be rejected by the DB directly."""

    from sqlalchemy.exc import IntegrityError

    admin = as_role("ADMIN")
    bad = PublicationAuthorAffiliationOverride(
        publication_author_id=world["pa1"].id,
        affiliation_text="X",
        confidence="CORROBORATED",
        status="REVOKED",  # but revoked_at/revoked_by_user_id left NULL
        evidence_url="https://x",
        reason="r",
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- compatibility with re-collection
def test_re_applying_automated_resolutions_never_touches_existing_overrides(client, as_role, db, world) -> None:
    """A later online-enrichment or offline-bundle apply() run (simulated here
    by calling AffiliationImportService().apply again with a new payload for
    the same author position) must leave the ADMIN's overrides completely
    untouched — the two layers are stored in different tables and the
    automated writer never references publication_author_affiliation_overrides."""

    as_role("ADMIN")
    _add(
        client, world["pa1"].id, affiliation_text="Khoa CNTT (ADMIN xác nhận thủ công)",
        confidence="CORROBORATED", evidence_url="https://example.edu.vn/111",
        reason="Xác nhận qua hồ sơ nhân sự trước khi có nguồn tự động mới",
    )

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

    detail = client.get("/api/v1/publications/E1").json()
    author_1 = next(a for a in detail["authors"] if a["author_order"] == 1)
    assert author_1["affiliation_overrides"][0]["affiliation_text"] == "Khoa CNTT (ADMIN xác nhận thủ công)"
    sources = {r["source_system"] for r in author_1["affiliation_resolutions"]}
    assert "crossref" in sources


# --------------------------------------------------------------------------- needs-review AFTER overrides exist
def test_needs_review_still_works_after_overrides_exist(client, as_role, world) -> None:
    """Regression test: list_needs_review must correctly read back overrides
    grouped by publication_author_id, without crashing, once rows exist."""

    as_role("ADMIN")
    _add(client, world["pa1"].id, affiliation_text="Khoa CNTT", confidence="CORROBORATED")

    resp = client.get("/api/v1/affiliations/needs-review")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    item_1 = next(i for i in body["items"] if i["author_order"] == 1)
    item_2 = next(i for i in body["items"] if i["author_order"] == 2)
    assert item_1["has_override"] is True
    assert item_2["has_override"] is False


def test_needs_review_returns_full_overrides_for_prefilling_the_edit_form(client, as_role, world) -> None:
    """The ADMIN review UI needs the full override list (text/confidence/
    evidence/reason/version/status per row) to pre-fill edit forms without a
    second round-trip."""

    as_role("ADMIN")
    _add(client, world["pa1"].id, affiliation_text="Khoa CNTT", confidence="UNRESOLVED", evidence_url="https://x/evidence", reason="ly do ban dau")

    resp = client.get("/api/v1/affiliations/needs-review")
    item_1 = next(i for i in resp.json()["items"] if i["author_order"] == 1)
    assert len(item_1["overrides"]) == 1
    o = item_1["overrides"][0]
    assert o["affiliation_text"] == "Khoa CNTT"
    assert o["confidence"] == "UNRESOLVED"
    assert o["evidence_url"] == "https://x/evidence"
    assert o["version"] == 1
    assert o["status"] == "ACTIVE"

    item_2 = next(i for i in resp.json()["items"] if i["author_order"] == 2)
    assert item_2["overrides"] == []
