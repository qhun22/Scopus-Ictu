"""Task 11: affiliation tables, importer and publication-detail API (isolated schema per test)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.affiliation import (
    Organization,
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.base import Base
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.services.affiliation_import import (
    AffiliationImportService,
    EntryInput,
    OrgInput,
    ResolutionInput,
)

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
H = {n: format(n, "x").rjust(64, "0") for n in range(1, 10)}  # distinct 64-hex payload hashes


@pytest.fixture
def db() -> Generator[Session, None, None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if make_url(url).database in {"scopus_ictu_acceptance_v2", "scopus_ictu_ui_clean"}:
        pytest.fail("never target an acceptance database")
    schema = f"test_t11_aff_{uuid.uuid4().hex}"
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
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
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def _pub(eid: str, doi: str | None) -> Publication:
    return Publication(
        id=uuid.uuid4(), eid=eid, doi=doi, title=f"Title {eid}", title_normalized=f"title {eid}".casefold(),
        source_title=None, year=2024, volume=None, issue=None, art_no=None, page_start=None, page_end=None,
        cited_by_count=0, document_type="Article", publication_stage="Final", open_access_status=None,
        version=1, created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def world(db: Session) -> dict:
    p1, p2, p3 = _pub("E1", "10.1/one"), _pub("E2", "10.1/two"), _pub("E3", None)
    authors = {sid: ScopusAuthor(scopus_id=sid, preferred_name=f"Author {sid}") for sid in ("111", "222", "333", "444")}
    db.add_all([p1, p2, p3, *authors.values()])
    db.flush()
    for pub, sids in ((p1, ("111", "222", "333")), (p2, ("444",)), (p3, ("111",))):
        for order, sid in enumerate(sids, start=1):
            db.add(PublicationAuthor(publication_id=pub.id, scopus_author_id=authors[sid].id, author_order=order))
    db.commit()
    return {"p1": p1, "p2": p2, "p3": p3}


def org(n: int, name: str | None = None, source: str = "openalex", ror: str | None = None) -> OrgInput:
    return OrgInput(source, f"https://openalex.org/I{n}", name or f"Org {n}", ror, "VN")


def trusted(eid, sid, order, source, status, payload, entries=(), **kw) -> ResolutionInput:
    verified = status == "VERIFIED"
    return ResolutionInput(
        eid=eid, scopus_id=sid, author_order=order, source_system=source, payload_sha256=payload, link_status=status,
        doi={"E1": "10.1/one", "E2": "10.1/two"}.get(eid), link_method="ORCID_SCOPUS_ID_BRIDGE" if verified else "POSITION_COUNT_NAME",
        evidence={"orcid": "0000-0001-0000-0001"} if verified else {"name_tokens_equal": True},
        source_doi={"E1": "10.1/one", "E2": "10.1/two"}.get(eid), source_work_id=f"{source}:{eid}",
        external_position=order, external_author_name=f"Ext {sid}",
        external_author_orcid="0000-0001-0000-0001" if verified else None, retrieved_at=NOW, entries=tuple(entries), **kw,
    )


def unresolved(eid, sid, order, source, payload, reason="NAME_MISMATCH") -> ResolutionInput:
    return ResolutionInput(eid=eid, scopus_id=sid, author_order=order, source_system=source, payload_sha256=payload,
                           link_status="UNRESOLVED", unresolved_reason=reason, doi={"E1": "10.1/one"}.get(eid))


def sample_inputs() -> list[ResolutionInput]:
    multi = [  # one author, TWO raw affiliations; the first is normalized to two organizations
        EntryInput(1, "Dept A, University X", org(1, "University X", ror="https://ror.org/aaa")),
        EntryInput(1, "Dept A, University X", org(2, "Consortium Y")),
        EntryInput(2, "Lab Z, no organization"),
    ]
    return [
        trusted("E1", "111", 1, "openalex", "VERIFIED", H[1], multi),
        trusted("E1", "222", 2, "openalex", "CORROBORATED", H[1], [EntryInput(1, "Univ Q", org(3))]),
        trusted("E1", "333", 3, "openalex", "CORROBORATED", H[1], []),  # source lists no unit -> ABSENT
        trusted("E1", "111", 1, "crossref", "CORROBORATED", H[2], [EntryInput(1, "University X (Crossref text)")]),
        unresolved("E1", "222", 2, "crossref", H[2]),
        unresolved("E1", "333", 3, "crossref", H[2], "AUTHOR_COUNT_MISMATCH"),
        unresolved("E2", "444", 1, "openalex", H[3], "NO_EXTERNAL_WORK"),
    ]


def counts(db: Session) -> dict[str, int]:
    return {
        t: db.scalar(text(f"select count(*) from {t}"))
        for t in ("publications", "scopus_authors", "publication_authors", "lecturers", "lecturer_scopus_identities",
                  "lecturer_scopus_candidates", "organizations", "publication_author_affiliation_resolutions",
                  "publication_author_affiliations")
    }


# ----------------------------------------------------------------- importer
def test_preview_writes_nothing_and_apply_matches_preview(db, world) -> None:
    before = counts(db)
    preview = AffiliationImportService().preview(db, sample_inputs())
    db.rollback()
    assert counts(db) == before
    assert (preview.resolutions_to_insert, preview.affiliations_to_insert, preview.organizations_to_insert) == (7, 5, 3)

    report = AffiliationImportService().apply(db, sample_inputs())
    after = counts(db)
    assert report.as_dict() == preview.as_dict()
    assert after["publication_author_affiliation_resolutions"] == 7 and after["publication_author_affiliations"] == 5
    assert after["organizations"] == 3
    for table in ("publications", "scopus_authors", "publication_authors", "lecturers", "lecturer_scopus_identities", "lecturer_scopus_candidates"):
        assert after[table] == before[table]  # nothing else is created or changed
    stats = report.as_dict()["by_source_and_confidence"]
    assert stats["openalex/VERIFIED"] == {"inserted": 1}
    assert stats["openalex/CORROBORATED"] == {"inserted": 2}
    assert stats["crossref/UNRESOLVED"] == {"inserted": 2}


def test_second_apply_is_idempotent(db, world) -> None:
    AffiliationImportService().apply(db, sample_inputs())
    first = counts(db)
    again = AffiliationImportService().apply(db, sample_inputs())
    assert counts(db) == first
    assert again.resolutions_to_insert == 0 and again.affiliations_to_insert == 0 and again.organizations_to_insert == 0
    assert all(set(c) == {"reused"} for c in again.by_source_status.values())


def test_confidence_levels_are_stored_distinct_and_absent_is_not_unresolved(db, world) -> None:
    AffiliationImportService().apply(db, sample_inputs())
    rows = {
        (r.source_system, r.link_status, r.affiliation_presence)
        for r in db.scalars(select(PublicationAuthorAffiliationResolution))
    }
    assert ("openalex", "VERIFIED", "PRESENT") in rows
    assert ("openalex", "CORROBORATED", "ABSENT") in rows  # trusted link, source has no unit
    assert ("crossref", "UNRESOLVED", None) in rows  # could not reconcile: presence unknown
    orgs = {o.display_name: o for o in db.scalars(select(Organization))}
    assert orgs["University X"].ror == "https://ror.org/aaa" and orgs["Consortium Y"].ror is None


def test_changed_payload_is_a_new_version_not_an_overwrite(db, world) -> None:
    AffiliationImportService().apply(db, sample_inputs())
    newer = [replace(sample_inputs()[0], payload_sha256=H[4], entries=(EntryInput(1, "Moved to Univ N", org(9)),))]
    report = AffiliationImportService().apply(db, newer)
    assert report.as_dict()["by_source_and_confidence"]["openalex/VERIFIED"] == {"inserted": 1}
    n = db.scalar(select(func.count()).select_from(PublicationAuthorAffiliationResolution).where(
        PublicationAuthorAffiliationResolution.source_payload_sha256.in_([H[1], H[4]]),
        PublicationAuthorAffiliationResolution.link_status == "VERIFIED"))
    assert n == 2  # history kept


def test_conflicts_fail_closed_and_write_nothing(db, world) -> None:
    base = sample_inputs()
    AffiliationImportService().apply(db, base)
    n0 = counts(db)
    bad = [
        replace(trusted("E1", "222", 2, "openalex", "CORROBORATED", H[5], [EntryInput(1, "X")]), author_order=3),  # order mismatch
        replace(trusted("E1", "222", 2, "openalex", "CORROBORATED", H[6], [EntryInput(1, "X")]), doi="10.9/other"),  # DOI mismatch
        trusted("E404", "111", 1, "openalex", "CORROBORATED", H[5], []),  # unknown publication
        trusted("E1", "999", 1, "openalex", "CORROBORATED", H[5], []),  # author not on the paper
        replace(base[0], entries=(EntryInput(1, "Changed text for the same payload"),)),  # same key, different content
    ]
    report = AffiliationImportService().apply(db, bad)
    assert counts(db) == n0
    assert report.conflict_reasons == {"AUTHOR_ORDER_MISMATCH": 1, "DOI_MISMATCH": 1, "AUTHOR_POSITION_NOT_FOUND": 2, "EXISTING_DIFFERENT_CONTENT": 1}


def test_duplicate_inputs_and_invalid_inputs_are_skipped(db, world) -> None:
    one = trusted("E1", "222", 2, "openalex", "CORROBORATED", H[7], [EntryInput(1, "A")])
    conflicting = replace(one, entries=(EntryInput(1, "B"),))
    invalid = [
        replace(one, link_method="ORCID_SCOPUS_ID_BRIDGE"),  # wrong method for the status
        replace(unresolved("E1", "333", 3, "openalex", H[7]), entries=(EntryInput(1, "must not exist"),)),
        replace(trusted("E1", "111", 1, "openalex", "VERIFIED", H[7]), external_author_orcid=None),  # VERIFIED needs an identifier
    ]
    report = AffiliationImportService().apply(db, [one, one, conflicting, *invalid])
    assert report.skipped_reasons == {
        "DUPLICATE_INPUT": 1, "INVALID_LINK_METHOD": 1, "UNRESOLVED_WITH_AFFILIATION": 1, "VERIFIED_WITHOUT_IDENTIFIER": 1,
    }
    assert report.conflict_reasons == {"DUPLICATE_KEY_DIFFERENT_CONTENT": 1}
    assert counts(db)["publication_author_affiliation_resolutions"] == 1


def test_cross_source_identifier_conflict_withholds_other_sources(db, world) -> None:
    inputs = [
        unresolved("E1", "111", 1, "openalex", H[1], "ID_CONFLICT"),
        trusted("E1", "111", 1, "crossref", "CORROBORATED", H[2], [EntryInput(1, "Would be imported")]),
        trusted("E1", "222", 2, "crossref", "CORROBORATED", H[2], [EntryInput(1, "Unrelated author is fine")]),
    ]
    report = AffiliationImportService().apply(db, inputs)
    stored = {
        (r.source_system, r.publication_author_id): r for r in db.scalars(select(PublicationAuthorAffiliationResolution))
    }
    withheld = [r for r in stored.values() if r.unresolved_reason == "WITHHELD_SOURCE_CONFLICT"]
    assert len(withheld) == 1 and withheld[0].evidence["withheld_link_status"] == "CORROBORATED"
    assert counts(db)["publication_author_affiliations"] == 1  # only the unrelated author's affiliation
    assert report.as_dict()["by_source_and_confidence"]["crossref/CORROBORATED"] == {"conflicted": 1, "inserted": 1}


# ----------------------------------------------------------------- database guarantees
def _res(db, pa_id, **kw) -> PublicationAuthorAffiliationResolution:
    values = dict(
        publication_author_id=pa_id, source_system="openalex", source_payload_sha256=H[8], link_status="CORROBORATED",
        link_method="POSITION_COUNT_NAME", affiliation_presence="PRESENT", external_position=1, retrieved_at=NOW,
        importer_version="t", evidence={},
    )
    values.update(kw)
    return PublicationAuthorAffiliationResolution(**values)


def test_database_constraints_make_invalid_states_unrepresentable(db, world) -> None:
    pa_id = db.scalar(select(PublicationAuthor.id).limit(1))
    for kw in (
        {"link_status": "VERIFIED"},  # method / ORCID mismatch
        {"link_status": "UNRESOLVED", "link_method": None, "affiliation_presence": None},  # reason missing
        {"unresolved_reason": "X"},  # trusted link cannot carry a reason
        {"affiliation_presence": None},  # trusted link must say PRESENT/ABSENT
        {"external_position": None},
        {"retrieved_at": None},
        {"source_payload_sha256": "not-a-hash"},
    ):
        with pytest.raises(IntegrityError):
            db.add(_res(db, pa_id, **kw))
            db.flush()
        db.rollback()

    unresolved_row = _res(db, pa_id, link_status="UNRESOLVED", link_method=None, affiliation_presence=None,
                          unresolved_reason="NAME_MISMATCH", external_position=None, retrieved_at=None)
    db.add(unresolved_row)
    db.flush()
    # an affiliation can not hang on an UNRESOLVED resolution: neither claiming UNRESOLVED nor a trusted status
    for status in ("UNRESOLVED", "VERIFIED"):
        with pytest.raises(IntegrityError):
            db.add(PublicationAuthorAffiliation(resolution_id=unresolved_row.id, link_status=status, ord=1,
                                                raw_index=1, raw_affiliation_text="x"))
            db.flush()
        db.rollback()


def test_organizations_are_not_merged_by_name(db, world) -> None:
    db.add_all([Organization(source_system="openalex", source_org_id="I1", display_name="Thai Nguyen University"),
                Organization(source_system="openalex", source_org_id="I2", display_name="Thai Nguyen University"),
                Organization(source_system="crossref", source_org_id="I1", display_name="Thai Nguyen University")])
    db.flush()  # same name / same id in another source are different organizations
    db.add(Organization(source_system="openalex", source_org_id="I1", display_name="Other"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ----------------------------------------------------------------- API
@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    now = datetime.now(UTC)
    admin = User(id=uuid.uuid4(), email="admin@t11.test", password_hash="x", display_name="A", role="ADMIN",
                 is_active=True, version=1, auth_version=1, created_at=now, updated_at=now)
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_detail_before_any_import_reports_not_reconciled(client, world) -> None:
    body = client.get("/api/v1/publications/E1").json()
    assert [a["author_order"] for a in body["authors"]] == [1, 2, 3]
    assert {a["affiliation_status"] for a in body["authors"]} == {"NOT_RECONCILED"}
    assert body["affiliation_summary"]["not_reconciled"] == 3
    assert all(a["affiliations"] == [] and a["source_has_affiliation"] is None for a in body["authors"])


def test_detail_reports_per_author_affiliations_without_changing_authors(client, db, world) -> None:
    plain = client.get("/api/v1/publications/E1").json()["authors"]
    AffiliationImportService().apply(db, sample_inputs())
    body = client.get("/api/v1/publications/E1").json()
    authors = body["authors"]
    # author count / order / identity untouched by the many joined affiliations
    assert [(a["author_order"], a["scopus_id"], a["preferred_name"]) for a in authors] == [
        (a["author_order"], a["scopus_id"], a["preferred_name"]) for a in plain
    ]
    first, second, third = authors
    assert first["affiliation_status"] == "VERIFIED" and first["source_has_affiliation"] is True
    texts = [(a["source_system"], a["link_status"], a["raw_affiliation_text"], [o["display_name"] for o in a["organizations"]])
             for a in first["affiliations"]]
    assert texts == [
        ("openalex", "VERIFIED", "Dept A, University X", ["University X", "Consortium Y"]),  # one raw string, 2 orgs
        ("openalex", "VERIFIED", "Lab Z, no organization", []),  # raw string the source could not normalize
        ("crossref", "CORROBORATED", "University X (Crossref text)", []),  # other source keeps its own confidence
    ]
    assert first["affiliations"][0]["scope"] == "AUTHOR_ON_PUBLICATION_EXTERNAL_SOURCE"
    assert first["affiliations"][0]["provenance"]["link_method"] == "ORCID_SCOPUS_ID_BRIDGE"
    assert second["affiliation_status"] == "CORROBORATED" and second["source_has_affiliation"] is True
    assert {r["source_system"]: r["link_status"] for r in second["affiliation_resolutions"]} == {
        "openalex": "CORROBORATED", "crossref": "UNRESOLVED"}
    # CORROBORATED link whose source lists no unit: known "no unit", not unresolved
    assert third["affiliation_status"] == "CORROBORATED" and third["source_has_affiliation"] is False
    assert third["affiliations"] == []
    summary = body["affiliation_summary"]
    assert summary["verified_with_affiliation"] == 1 and summary["corroborated_with_affiliation"] == 1
    assert summary["corroborated_without_affiliation"] == 1
    assert summary["verified_without_affiliation"] == summary["unresolved"] == summary["not_reconciled"] == 0
    assert summary["all_authors_verified_with_affiliation"] is False
    assert summary["all_authors_verified_or_corroborated_with_affiliation"] is False  # author 3 has no unit
    unresolved_only = client.get("/api/v1/publications/E2").json()["authors"][0]
    assert unresolved_only["affiliation_status"] == "UNRESOLVED" and unresolved_only["affiliations"] == []
    assert unresolved_only["source_has_affiliation"] is None
    assert unresolved_only["affiliation_resolutions"][0]["unresolved_reason"] == "NO_EXTERNAL_WORK"


def test_detail_serializes_no_internal_ids_and_uses_newest_version(client, db, world) -> None:
    AffiliationImportService().apply(db, sample_inputs())
    newer = replace(sample_inputs()[0], payload_sha256=H[4], entries=(EntryInput(1, "Newest text", org(9, "Univ N")),))
    AffiliationImportService().apply(db, [newer])
    body = client.get("/api/v1/publications/E1").json()
    openalex = [a for a in body["authors"][0]["affiliations"] if a["source_system"] == "openalex"]
    assert [a["raw_affiliation_text"] for a in openalex] == ["Newest text"]
    blob = str(body)
    assert "resolution_id" not in blob and "publication_author_id" not in blob
    assert all("id" not in a for a in body["authors"])
