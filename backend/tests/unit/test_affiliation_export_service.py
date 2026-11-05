"""Week-7 affiliation export and gap list against synthetic data on in-memory SQLite.

No application database. Covers what the pure-rule tests cannot: that the right rows are
read (current resolution only, ACTIVE overrides only, APPROVED links only), that the JSON
export, the CSV and the gap list agree, and that every position lands in exactly one group.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.affiliation import (
    Organization,
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.affiliation_override import PublicationAuthorAffiliationOverride
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor
from app.services.affiliation_export import CSV_COLUMNS, load_positions
from app.services.affiliation_gaps import gaps_csv, list_gaps
from app.services.publication_export import export_publications, export_publications_csv
from tests.source_staging_fixtures import make_sqlite_engine

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
ACTOR = uuid.UUID(int=999)


def uid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def sha(n: int) -> str:
    return f"{n:064x}"


class World:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._n = 1000
        self.positions: dict[str, uuid.UUID] = {}
        self.pubs: dict[str, uuid.UUID] = {}

    def nid(self) -> uuid.UUID:
        self._n += 1
        return uid(self._n)

    def pub(self, key, eid, year, doi):
        row = Publication(
            id=self.nid(), eid=eid, doi=doi, title=f"Title {key}", title_normalized=key,
            source_title="Journal", year=year, document_type="Article", version=1,
            created_at=NOW, updated_at=NOW,
        )
        self.db.add(row)
        self.pubs[key] = row.id
        return row

    def author(self, key, pub_key, order):
        sa = ScopusAuthor(id=self.nid(), scopus_id=f"57{order:02d}{abs(hash(key)) % 10**7:07d}",
                          preferred_name=f"Name {key}", created_at=NOW, updated_at=NOW)
        pa = PublicationAuthor(id=self.nid(), publication_id=self.pubs[pub_key],
                               scopus_author_id=sa.id, author_order=order, created_at=NOW)
        self.db.add_all([sa, pa])
        self.positions[key] = pa.id
        return sa, pa

    def resolution(self, key, source, status, *, reason=None, presence=None, age_days=0,
                   work_id=None, doi=None, units=()):
        link_method = {"VERIFIED": "ORCID_SCOPUS_ID_BRIDGE",
                       "CORROBORATED": "POSITION_COUNT_NAME"}.get(status)
        res = PublicationAuthorAffiliationResolution(
            id=self.nid(), publication_author_id=self.positions[key], source_system=source,
            source_payload_sha256=sha(self._n), link_status=status, link_method=link_method,
            unresolved_reason=reason, affiliation_presence=presence, evidence={},
            source_doi=doi, source_work_id=work_id, importer_version="test",
            created_at=NOW - timedelta(days=age_days), retrieved_at=NOW,
        )
        self.db.add(res)
        self.db.flush()
        for i, (raw, org) in enumerate(units, start=1):
            org_id = None
            if org:
                o = Organization(id=self.nid(), source_system=source,
                                 source_org_id=f"{source}-{org[0]}", display_name=org[0],
                                 country_code=org[1])
                self.db.add(o)
                self.db.flush()
                org_id = o.id
            self.db.add(PublicationAuthorAffiliation(
                id=self.nid(), resolution_id=res.id, link_status=status, ord=i,
                raw_index=i if raw else None, raw_affiliation_text=raw, organization_id=org_id))
        return res

    def override(self, key, text, confidence="CORROBORATED", status="ACTIVE", age_days=0):
        revoked = status == "REVOKED"
        row = PublicationAuthorAffiliationOverride(
            id=self.nid(), publication_author_id=self.positions[key], affiliation_text=text,
            confidence=confidence, status=status, evidence_url=f"https://example.invalid/{text}",
            reason="internal note", created_by_user_id=ACTOR, updated_by_user_id=ACTOR,
            revoked_by_user_id=ACTOR if revoked else None,
            revoked_at=NOW if revoked else None, version=1,
            created_at=NOW - timedelta(days=age_days), updated_at=NOW)
        self.db.add(row)
        return row

    def link(self, scopus_author, name, status="APPROVED"):
        lec = Lecturer(id=self.nid(), full_name=name, full_name_normalized=name.casefold(),
                       is_active=True, version=1, created_at=NOW, updated_at=NOW)
        self.db.add(lec)
        self.db.flush()
        self.db.add(LecturerScopusIdentity(id=self.nid(), lecturer_id=lec.id,
                                           scopus_author_id=scopus_author.id, status=status,
                                           created_at=NOW, updated_at=NOW))


@pytest.fixture
def world():
    engine = make_sqlite_engine()
    with Session(engine, autoflush=False) as db:
        w = World(db)
        w.pub("A", "E-A", 2024, "10.1/a")
        w.pub("B", "E-B", 2023, None)
        w.pub("C", "E-C", 2022, "10.1/c")  # no authors at all

        # a1: both sources have the same text; an OLDER openalex row must be ignored.
        sa1, _ = w.author("a1", "A", 1)
        w.resolution("a1", "crossref", "VERIFIED", presence="PRESENT", work_id="10.1/a",
                     units=[("Faculty X, Univ X", ("Univ X", "VN"))])
        w.resolution("a1", "openalex", "CORROBORATED", presence="PRESENT",
                     work_id="https://openalex.org/W1",
                     units=[("Faculty X, Univ X", ("Univ X", "VN"))])
        w.resolution("a1", "openalex", "CORROBORATED", presence="PRESENT", age_days=30,
                     work_id="https://openalex.org/W0", units=[("OLD TEXT", None)])
        w.link(sa1, "Lecturer One")
        # a2: automatic unit exists but an ADMIN typed another one -> only the typed one.
        sa2, _ = w.author("a2", "A", 2)
        w.resolution("a2", "crossref", "UNRESOLVED", reason="NAME_MISMATCH")
        w.resolution("a2", "openalex", "CORROBORATED", presence="PRESENT",
                     work_id="https://openalex.org/W2", units=[("Inst Y", None)])
        w.override("a2", "Manual Z")
        w.link(sa2, "Not Approved", status="CANDIDATE")
        # a3: nothing usable; a REVOKED typed unit must not count.
        w.author("a3", "A", 3)
        w.resolution("a3", "crossref", "UNRESOLVED", reason="AUTHOR_COUNT_MISMATCH")
        w.resolution("a3", "openalex", "UNRESOLVED", reason="NAME_MISMATCH")
        w.override("a3", "Revoked unit", status="REVOKED")
        # publication B: five different kinds of gap
        w.author("a4", "B", 1)
        w.resolution("a4", "crossref", "UNRESOLVED", reason="NO_EXTERNAL_WORK")
        w.resolution("a4", "openalex", "UNRESOLVED", reason="NO_EXTERNAL_WORK")
        w.author("a5", "B", 2)
        w.resolution("a5", "crossref", "VERIFIED", presence="ABSENT", work_id="10.1/b")
        w.resolution("a5", "openalex", "UNRESOLVED", reason="NO_EXTERNAL_WORK")
        w.author("a6", "B", 3)  # never reconciled
        w.author("a7", "B", 4)
        w.override("a7", "Not sure", confidence="UNRESOLVED")
        db.commit()
        yield w
    engine.dispose()


def by_key(world):
    positions = load_positions(world.db, list(world.pubs.values()))
    inverse = {v: k for k, v in world.positions.items()}
    return {inverse[p.publication_author_id]: p for ps in positions.values() for p in ps}


# ----------------------------------------------------------------------------- loading rules
def test_only_current_resolution_is_used_and_each_unit_keeps_its_own_source(world):
    a1 = by_key(world)["a1"].decision
    assert [(u.source, u.confidence, u.text) for u in a1.units] == [
        ("crossref", "VERIFIED", "Faculty X, Univ X"),
        ("openalex", "CORROBORATED", "Faculty X, Univ X"),
    ]
    assert "OLD TEXT" not in [u.text for u in a1.units]
    assert a1.units[0].organizations == (("Univ X", "VN"),)
    assert a1.units[0].evidence_url == "https://doi.org/10.1/a"
    assert a1.units[1].evidence_url == "https://openalex.org/W1"


def test_typed_unit_replaces_automatic_ones_and_revoked_is_ignored(world):
    got = by_key(world)
    a2, a3 = got["a2"].decision, got["a3"].decision
    assert [(u.text, u.confidence, u.source) for u in a2.units] == [("Manual Z", "MANUAL_REVIEW", "admin")]
    assert a2.affiliation_status == "CORROBORATED"  # automatic status not raised by the override
    assert a3.units == () and a3.gap_reason == "NAME_MISMATCH" and not a3.admin_reviewed
    assert len(got["a3"].overrides) == 1  # the revoked row is kept for the ADMIN screen


def test_gap_reasons_for_each_kind_of_position(world):
    got = by_key(world)
    assert {k: got[k].decision.gap_reason for k in ("a1", "a2", "a3", "a4", "a5", "a6", "a7")} == {
        "a1": None, "a2": None, "a3": "NAME_MISMATCH", "a4": "NO_EXTERNAL_WORK",
        "a5": "SOURCE_HAS_NO_AFFILIATION", "a6": "NOT_RECONCILED", "a7": "ADMIN_MARKED_UNRESOLVED",
    }
    assert got["a7"].decision.admin_reviewed and got["a7"].decision.units == ()


def test_every_position_is_in_exactly_one_group(world):
    for key, pos in by_key(world).items():
        assert bool(pos.decision.units) != (pos.decision.gap_reason is not None), key


def test_only_approved_links_name_an_ictu_lecturer(world):
    got = by_key(world)
    assert got["a1"].ictu_lecturers == ("Lecturer One",)
    assert got["a2"].ictu_lecturers == ()  # a CANDIDATE identity is not a confirmed link


# ----------------------------------------------------------------------------- JSON export
def test_json_export_adds_count_status_reason_and_units_without_dropping_old_fields(world):
    items, _ = export_publications(world.db)
    assert [i.eid for i in items] == ["E-A", "E-B", "E-C"]
    a, b, c = items
    assert (a.author_count, b.author_count, c.author_count) == (3, 4, 0)
    assert c.authors == []
    first = a.authors[0]
    assert (first.author_order, first.affiliation_status, first.gap_reason) == (1, "VERIFIED", None)
    assert [(x.source, x.confidence) for x in first.affiliations] == [
        ("crossref", "VERIFIED"), ("openalex", "CORROBORATED"),
    ]
    assert first.affiliations[0].organizations[0].name == "Univ X"
    assert [x.source for x in a.authors[1].affiliations] == ["admin"]
    assert a.authors[2].gap_reason == "NAME_MISMATCH" and a.authors[2].affiliations == []
    assert [link.full_name for link in a.approved_lecturer_links] == ["Lecturer One"]
    dumped = a.model_dump(mode="json")
    for old in ("eid", "doi", "title", "authors", "approved_lecturer_links", "cited_by_count"):
        assert old in dumped


def test_json_export_never_exposes_internal_ids_or_override_notes(world):
    items, _ = export_publications(world.db)
    text = "".join(i.model_dump_json() for i in items)
    assert "internal note" not in text
    assert "publication_author_id" not in text and "created_by_user_id" not in text


# ----------------------------------------------------------------------------- CSV export
def test_csv_has_one_row_per_position_and_agrees_with_the_json(world):
    content, record_count, row_count, _ = export_publications_csv(world.db)
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")))
    assert rows[0] == list(CSV_COLUMNS)
    assert (record_count, row_count, len(rows) - 1) == (3, 8, 8)  # 3 + 4 + 1 (no authors)
    table = [dict(zip(rows[0], r)) for r in rows[1:]]
    a1 = next(r for r in table if r["eid"] == "E-A" and r["author_order"] == "1")
    assert a1["author_count"] == "3" and a1["ictu_lecturer"] == "Lecturer One"
    assert a1["confidence"] == "VERIFIED | CORROBORATED" and a1["source"] == "crossref | openalex"
    a2 = next(r for r in table if r["eid"] == "E-A" and r["author_order"] == "2")
    assert (a2["affiliation"], a2["confidence"], a2["source"]) == ("Manual Z", "MANUAL_REVIEW", "admin")
    empty = next(r for r in table if r["eid"] == "E-C")
    assert empty["author_count"] == "0" and empty["author_order"] == ""
    assert all(r["gap_reason"] == "" for r in table if r["affiliation"])
    assert all(r["gap_reason"] != "" for r in table if r["author_order"] and not r["affiliation"])


def test_csv_respects_the_publication_filters(world):
    content, record_count, row_count, applied = export_publications_csv(world.db, year=2023)
    assert (record_count, row_count, applied) == (1, 4, {"year": 2023})


# ----------------------------------------------------------------------------- gap list
def test_gap_list_counts_and_summary(world):
    out = list_gaps(world.db)
    assert out.summary.total_positions == 7 and out.summary.total_gaps == 5
    assert out.summary.publications_with_gaps == 2
    assert out.summary.by_reason == {
        "NAME_MISMATCH": 1, "NO_EXTERNAL_WORK": 1, "SOURCE_HAS_NO_AFFILIATION": 1,
        "NOT_RECONCILED": 1, "ADMIN_MARKED_UNRESOLVED": 1,
    }
    assert out.total == 5 and [i.author_order for i in out.items] == [3, 1, 2, 3, 4]
    assert [i.eid for i in out.items] == ["E-A", "E-B", "E-B", "E-B", "E-B"]


def test_reason_filter_changes_total_but_not_the_summary(world):
    out = list_gaps(world.db, reason="NO_EXTERNAL_WORK")
    assert out.total == 1 and out.items[0].eid == "E-B" and out.items[0].author_order == 1
    assert out.summary.total_gaps == 5 and out.summary.by_reason["NAME_MISMATCH"] == 1


def test_year_and_eid_filters_narrow_the_scope_including_total_positions(world):
    out = list_gaps(world.db, year=2024)
    assert (out.summary.total_positions, out.summary.total_gaps, out.total) == (3, 1, 1)
    out = list_gaps(world.db, eid="E-B")
    assert (out.summary.total_positions, out.summary.total_gaps) == (4, 4)


def test_ictu_only_keeps_positions_with_an_approved_lecturer(world):
    out = list_gaps(world.db, ictu_only=True)
    assert (out.summary.total_positions, out.summary.total_gaps, out.items) == (1, 0, [])


def test_pagination_does_not_lose_or_repeat_rows(world):
    seen = []
    for page in (1, 2, 3):
        out = list_gaps(world.db, page=page, page_size=2)
        assert out.total == 5 and out.page == page
        seen += [(i.eid, i.author_order) for i in out.items]
    assert len(seen) == len(set(seen)) == 5
    assert list_gaps(world.db, page=4, page_size=2).items == []


def test_gap_item_carries_every_override_and_the_per_source_outcome(world):
    first = list_gaps(world.db).items[0]  # a3: has a revoked override
    assert [(o.status, o.affiliation_text) for o in first.overrides] == [("REVOKED", "Revoked unit")]
    assert first.overrides[0].version == 1 and first.admin_reviewed is False
    assert [(s.source, s.reason) for s in first.by_source] == [
        ("crossref", "AUTHOR_COUNT_MISMATCH"), ("openalex", "NAME_MISMATCH"),
    ]
    marked = next(i for i in list_gaps(world.db).items if i.reason == "ADMIN_MARKED_UNRESOLVED")
    assert marked.admin_reviewed is True and marked.overrides[0].confidence == "UNRESOLVED"


def test_gap_csv_matches_the_list_and_leaves_out_internal_data(world):
    content, row_count = gaps_csv(world.db)
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")))
    assert row_count == 5 and len(rows) == 6
    text = content.decode("utf-8-sig")
    assert "internal note" not in text and "overrides" not in rows[0]
    table = [dict(zip(rows[0], r)) for r in rows[1:]]
    assert table[0]["by_source"] == "crossref:AUTHOR_COUNT_MISMATCH | openalex:NAME_MISMATCH"
    assert {r["admin_reviewed"] for r in table} == {"true", "false"}
    assert len(gaps_csv(world.db, reason="NOT_RECONCILED")[0].splitlines()) == 2
