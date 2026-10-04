"""M2.7A-4 — Targeted unit tests for the KnownPublicationIngestionService.

Tests cover the explicit regression scenarios required by the task brief
plus the pure-function normalization contract. We mock at the
SQLAlchemy ``Session.execute`` boundary using lightweight fakes so the
service's real SELECT queries are exercised against a stubbed result.
"""
from __future__ import annotations

import re
import uuid

import pytest

from app.services.lecturer_dataset import known_publication_ingestion as kpi
from app.services.lecturer_dataset.known_publication_ingestion import (
    CrawLecturerSource,
    CrawPublicationAttribution,
    KnownPublicationIngestionService,
    normalize_doi_n0,
    normalize_title_t0,
)


# ---------------------------------------------------------------------------
# Pure-function normalization tests
# ---------------------------------------------------------------------------
class TestNormalizeDoiN0:
    def test_basic(self):
        assert normalize_doi_n0("10.1234/ABC") == "10.1234/abc"

    def test_trim_and_lowercase(self):
        assert normalize_doi_n0("  10.1234/Abc  ") == "10.1234/abc"

    def test_strips_https_doi_org(self):
        assert normalize_doi_n0("https://doi.org/10.1234/Abc") == "10.1234/abc"

    def test_strips_http_doi_org(self):
        assert normalize_doi_n0("http://doi.org/10.1234/Abc") == "10.1234/abc"

    def test_strips_dx_doi_org(self):
        assert normalize_doi_n0("https://dx.doi.org/10.1234/Abc") == "10.1234/abc"

    def test_strips_doi_prefix(self):
        assert normalize_doi_n0("doi:10.1234/Abc") == "10.1234/abc"

    def test_does_not_strip_non_prefix(self):
        # No fuzzy repair; only known prefixes are stripped
        assert normalize_doi_n0("DOI 10.1234/Abc") == "doi 10.1234/abc"

    def test_empty(self):
        assert normalize_doi_n0("") is None
        assert normalize_doi_n0(None) is None
        assert normalize_doi_n0("   ") is None


class TestNormalizeTitleT0:
    def test_basic(self):
        assert normalize_title_t0("Hello World") == "hello world"

    def test_trim_and_collapse(self):
        assert normalize_title_t0("  Hello   World  ") == "hello world"

    def test_empty(self):
        assert normalize_title_t0("") == ""
        assert normalize_title_t0(None) == ""


# ---------------------------------------------------------------------------
# Hash determinism
# ---------------------------------------------------------------------------
class TestHash:
    def test_hash_deterministic(self):
        a = {"a": 1, "b": [1, 2, 3]}
        b = {"b": [1, 2, 3], "a": 1}
        assert kpi._hash_payload(a) == kpi._hash_payload(b)

    def test_hash_format(self):
        h = kpi._hash_payload({"name": "Nguyen Van A", "year": 2024})
        assert len(h) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", h)


# ---------------------------------------------------------------------------
# Lightweight SQLAlchemy Session fake
# ---------------------------------------------------------------------------
class _FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        # Return a fresh object whose ``.all()`` is also callable, mirroring
        # the SQLAlchemy ``ScalarResult`` interface used by the service.
        return _FakeScalarResult(self._rows)

    def all(self):
        return list(self._rows)


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    """Minimal stub for SQLAlchemy ``Session`` consumed by the service.

    The service issues exactly three kinds of SELECTs:

    * ``SELECT id, repository_profile_url FROM lecturers WHERE url IS NOT NULL``
    * ``SELECT * FROM lecturer_source_snapshots WHERE snapshot_hash IN``
    * ``SELECT * FROM lecturer_known_publications WHERE snapshot_id IN``

    We dispatch on the substring of the compiled statement and return
    rows from the appropriate in-memory list.
    """

    def __init__(
        self,
        *,
        lecturer_index: dict[str, uuid.UUID] | None = None,
        existing_snapshots: list | None = None,
        existing_kps: list | None = None,
    ):
        self._lecturer_index = lecturer_index or {}
        self.snapshots: list = list(existing_snapshots or [])
        self.kps: list = list(existing_kps or [])
        self.added: list = []

    def execute(self, stmt):
        from sqlalchemy import Select
        if not isinstance(stmt, Select):
            return _FakeResult([])
        desc = str(stmt).lower()
        if "repository_profile_url" in desc:
            # SELECT id, repository_profile_url ...
            rows = [
                (lid, url) for url, lid in self._lecturer_index.items()
            ]
            return _FakeResult(rows)
        if "lecturer_known_publications" in desc:
            return _FakeResult(self.kps)
        if "lecturer_source_snapshots" in desc and "snapshot_hash" in desc:
            return _FakeResult(self.snapshots)
        return _FakeResult([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, kpi.LecturerKnownPublication):
            self.kps.append(obj)
        elif isinstance(obj, kpi.LecturerSourceSnapshot):
            self.snapshots.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


# ---------------------------------------------------------------------------
# Ingestion contract tests
# ---------------------------------------------------------------------------
class TestIngestionContract:
    def _service(self):
        return KnownPublicationIngestionService()

    def test_two_lecturers_same_publication_each_gets_own_row(self):
        lid_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
        lid_b = uuid.UUID("22222222-2222-2222-2222-222222222222")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/1": lid_a,
            "https://ictu.example/u/2": lid_b,
        })
        shared_pub = "https://ictu.example/p/shared"
        s1 = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/1",
            craw_full_name="Lecturer A",
            raw_payload={"full_name": "Lecturer A", "id": 1},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url=shared_pub,
                title_raw="Shared Paper",
                doi_raw="10.1234/shared",
                published_year=2023,
            ),),
        )
        s2 = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/2",
            craw_full_name="Lecturer B",
            raw_payload={"full_name": "Lecturer B", "id": 2},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url=shared_pub,
                title_raw="Shared Paper",
                doi_raw="10.1234/shared",
                published_year=2023,
            ),),
        )
        result = self._service().apply(sess, [s1, s2])
        assert result.snapshots_created == 2
        assert result.known_publications_created == 2
        lecturer_ids = sorted(str(k.lecturer_id) for k in sess.kps)
        assert lecturer_ids == [str(lid_a), str(lid_b)]

    def test_duplicate_source_record_collapsed(self):
        lid = uuid.UUID("33333333-3333-3333-3333-333333333333")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/3": lid,
        })
        pub = "https://ictu.example/p/dup"
        s = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/3",
            craw_full_name="Lecturer C",
            raw_payload={"full_name": "Lecturer C", "id": 3},
            publication_attributions=(
                CrawPublicationAttribution(
                    source_publication_url=pub,
                    title_raw="Dup",
                    doi_raw="10.1/dup",
                    published_year=2022,
                ),
                CrawPublicationAttribution(
                    source_publication_url=pub,
                    title_raw="Dup",
                    doi_raw="10.1/dup",
                    published_year=2022,
                ),
            ),
        )
        result = self._service().apply(sess, [s])
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        assert result.source_duplicates_collapsed == 1

    def test_no_doi_publication_ingested(self):
        lid = uuid.UUID("44444444-4444-4444-4444-444444444444")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/4": lid,
        })
        s = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/4",
            craw_full_name="Lecturer D",
            raw_payload={"full_name": "Lecturer D", "id": 4},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/no-doi",
                title_raw="A study without DOI",
                doi_raw=None,
                published_year=2021,
            ),),
        )
        result = self._service().apply(sess, [s])
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        kp = sess.kps[0]
        assert kp.doi_raw is None
        assert kp.doi_normalized is None
        assert kp.title_normalized == normalize_title_t0("A study without DOI")

    def test_malformed_doi_not_repaired(self):
        lid = uuid.UUID("55555555-5555-5555-5555-555555555555")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/5": lid,
        })
        bad = "not-a-doi-but-says-it-is"
        s = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/5",
            craw_full_name="Lecturer E",
            raw_payload={"full_name": "Lecturer E", "id": 5},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/bad-doi",
                title_raw="Bad DOI",
                doi_raw=bad,
                published_year=2020,
            ),),
        )
        result = self._service().apply(sess, [s])
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        kp = sess.kps[0]
        assert kp.doi_raw == bad
        # Conservative: only normalize, never guess
        assert kp.doi_normalized == bad.lower()

    def test_source_change_creates_new_snapshot(self):
        lid = uuid.UUID("66666666-6666-6666-6666-666666666666")
        old_snap = kpi.LecturerSourceSnapshot(
            id=uuid.UUID("77777777-7777-7777-7777-777777777777"),
            lecturer_id=lid,
            source_system="ictu_craw",
            source_url="https://ictu.example/u/6",
            snapshot_hash="0" * 64,  # different from any real hash
            raw_payload={"full_name": "Lecturer F v1"},
            parser_version="ictu_harvester/1.4-full",
            validation_status="VALID",
            validation_errors=[],
            fetched_at=None,
            created_at=None,
        )
        sess = _FakeSession(
            lecturer_index={"https://ictu.example/u/6": lid},
            existing_snapshots=[old_snap],
        )
        s_payload = {"full_name": "Lecturer F v2 — changed"}
        src = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/6",
            craw_full_name="Lecturer F",
            raw_payload=s_payload,
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/6-1",
                title_raw="Changed Capture",
                doi_raw="10.1/6",
                published_year=2024,
            ),),
        )
        result = self._service().apply(sess, [src])
        assert result.snapshots_created == 1
        # The old snapshot is still present, plus a new one.
        assert len(sess.snapshots) == 2
        assert result.known_publications_created == 1

    def test_idempotency_rerun_creates_zero_rows(self):
        lid = uuid.UUID("88888888-8888-8888-8888-888888888888")
        raw = {"full_name": "Lecturer G", "id": 7}
        src = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/7",
            craw_full_name="Lecturer G",
            raw_payload=raw,
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/g-1",
                title_raw="G's paper",
                doi_raw="10.1/g1",
                published_year=2024,
            ),),
        )
        # First run: empty session
        sess1 = _FakeSession(lecturer_index={
            "https://ictu.example/u/7": lid,
        })
        result1 = self._service().apply(sess1, [src])
        assert result1.snapshots_created == 1
        assert result1.known_publications_created == 1
        # Second run: the first session now has the snapshot and KP.
        # Apply again with the same source.
        result2 = self._service().apply(sess1, [src])
        assert result2.snapshots_created == 0
        assert result2.known_publications_created == 0
        assert result2.snapshots_reused == 1
        assert result2.known_publications_reused == 1
        # Database state has not grown.
        assert len(sess1.snapshots) == 1
        assert len(sess1.kps) == 1

    def test_unmapped_lecturer_reported(self):
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/known": uuid.UUID(
                "99999999-9999-9999-9999-999999999999"
            ),
        })
        s_known = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/known",
            craw_full_name="Known",
            raw_payload={"full_name": "Known", "id": 1},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/1",
                title_raw="P",
                doi_raw=None,
                published_year=2020,
            ),),
        )
        s_unknown = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/unknown",
            craw_full_name="Unknown",
            raw_payload={"full_name": "Unknown", "id": 2},
            publication_attributions=(CrawPublicationAttribution(
                source_publication_url="https://ictu.example/p/2",
                title_raw="P",
                doi_raw=None,
                published_year=2020,
            ),),
        )
        result = self._service().apply(sess, [s_known, s_unknown])
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        assert "https://ictu.example/u/unknown" in result.unmapped_lecturers

    def test_invalid_year_skipped(self):
        lid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/8": lid,
        })
        s = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/8",
            craw_full_name="Lecturer H",
            raw_payload={"full_name": "Lecturer H", "id": 8},
            publication_attributions=(
                CrawPublicationAttribution(
                    source_publication_url="https://ictu.example/p/h1",
                    title_raw="Good",
                    doi_raw=None,
                    published_year=2020,
                ),
                CrawPublicationAttribution(
                    source_publication_url="https://ictu.example/p/h2",
                    title_raw="Bad year",
                    doi_raw=None,
                    published_year=99,
                ),
            ),
        )
        result = self._service().apply(sess, [s])
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        assert result.invalid_records == 1

    def test_within_snapshot_doi_collision_recorded_in_validation_errors(self):
        """When two distinct source URLs point to the same canonical
        Scopus publication (same DOI), the second URL must NOT be
        silently lost. The snapshot's validation_errors JSONB must
        contain a SOURCE_URL_COLLISION entry listing all colliding URLs.
        """
        lid = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        sess = _FakeSession(lecturer_index={
            "https://ictu.example/u/9": lid,
        })
        s = CrawLecturerSource(
            craw_source_id="https://ictu.example/u/9",
            craw_full_name="Lecturer I",
            raw_payload={"full_name": "Lecturer I", "id": 9},
            publication_attributions=(
                CrawPublicationAttribution(
                    source_publication_url="https://ictu.example/p/same-paper",
                    title_raw="Same Paper",
                    doi_raw="10.1234/same",
                    published_year=2024,
                ),
                CrawPublicationAttribution(
                    source_publication_url="https://ictu.example/p/same-paper-2",
                    title_raw="Same Paper",
                    doi_raw="10.1234/same",
                    published_year=2024,
                ),
            ),
        )
        result = self._service().apply(sess, [s])
        # One snapshot, one KP (idempotent on doi)
        assert result.snapshots_created == 1
        assert result.known_publications_created == 1
        snap = sess.snapshots[0]
        # The snapshot must surface the collision in validation_errors
        codes = [e.get("code") for e in (snap.validation_errors or [])]
        assert "SOURCE_URL_COLLISION" in codes
        # Find the collision entry
        collision_entries = [
            e for e in (snap.validation_errors or [])
            if e.get("code") == "SOURCE_URL_COLLISION"
        ]
        assert len(collision_entries) == 1
        assert collision_entries[0]["match_kind"] == "doi"
        assert collision_entries[0]["match_value"] == "10.1234/same"
        assert sorted(collision_entries[0]["source_publication_urls"]) == [
            "https://ictu.example/p/same-paper",
            "https://ictu.example/p/same-paper-2",
        ]
        # Both URLs are also in snapshot.raw_payload.public_publication_links
        # (because raw_payload is the entire Craw lecturer JSON — for
        # this synthetic test we provided a minimal payload that does
        # NOT contain the URLs. In production, raw_payload is the full
        # Craw lecturer record.)