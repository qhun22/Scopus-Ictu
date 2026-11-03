"""Before/after normalisation view: raw CSV value vs stored value vs canonical form.

Synthetic rows only (``example.invalid``); nothing here is a real publication.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import text

from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization_compare import build_compare
from tests.conftest import disable_append_only_triggers
from tests.db_safety_guard import assert_safe_for_destructive_test
from tests.integration.test_candidate_review_service import (  # noqa: F401  (fixtures)
    review_engine,
    review_session,
    session_factory,
)


@pytest.fixture(autouse=True)
def _clean(review_engine):
    def wipe():
        assert_safe_for_destructive_test(review_engine)
        with review_engine.begin() as conn:
            with disable_append_only_triggers(conn):
                conn.execute(text("TRUNCATE publications, scopus_imports CASCADE"))

    wipe()
    yield
    wipe()


def _seed(session, *, raw_doi: str, stored_doi: str, raw_title: str, stored_title: str):
    imp = ScopusImport(
        file_name="synthetic-example.csv",
        file_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        total_records=1, valid_records=1, invalid_records=0, status="VALIDATED",
    )
    session.add(imp)
    session.flush()
    raw = RawScopusRecord(
        import_id=imp.id, row_number=2, row_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        eid_raw="2-s2.0-000000000001", doi_raw=raw_doi, validation_status="VALID",
        raw_payload={
            "EID": "2-s2.0-000000000001", "DOI": raw_doi, "Title": raw_title,
            "Source title": "Synthetic Journal", "Year": "2025", "Document Type": "Article",
            "Cited by": "3",
        },
    )
    session.add(raw)
    pub = Publication(
        eid="2-s2.0-000000000001", doi=stored_doi, title=stored_title,
        title_normalized=stored_title.lower(), source_title="Synthetic Journal", year=2025,
        document_type="Article", cited_by_count=3,
    )
    session.add(pub)
    session.flush()
    session.add(PublicationRawSource(publication_id=pub.id, raw_record_id=raw.id))
    session.commit()
    return pub


def _by_field(result):
    return {f.field: f for f in result.fields}


def test_a_doi_stored_as_received_is_flagged_as_cleaned_with_its_canonical_form(review_session):
    _seed(review_session, raw_doi="https://doi.org/10.1000/ABC.1", stored_doi="https://doi.org/10.1000/ABC.1",
          raw_title="A Synthetic Title", stored_title="A Synthetic Title")
    result = build_compare(review_session, "2-s2.0-000000000001")

    assert result is not None
    assert [(s.file_name, s.row_number) for s in result.sources] == [("synthetic-example.csv", 2)]
    doi = _by_field(result)["doi"]
    assert doi.raw == "https://doi.org/10.1000/ABC.1" and doi.stored == doi.raw
    assert doi.canonical == "10.1000/abc.1"            # resolver prefix removed, lower-cased
    assert doi.status == "CLEANED"
    assert _by_field(result)["source_title"].status == "SAME"
    assert _by_field(result)["year"].status == "SAME"


def test_a_stored_value_that_differs_from_the_raw_text_is_flagged_as_changed(review_session):
    _seed(review_session, raw_doi="10.1000/x", stored_doi="10.1000/x",
          raw_title="Original Title", stored_title="Edited Title")
    title = _by_field(build_compare(review_session, "2-s2.0-000000000001"))["title"]
    assert title.status == "CHANGED"
    assert title.raw == "Original Title" and title.stored == "Edited Title"


def test_an_unknown_eid_has_no_comparison(review_session):
    assert build_compare(review_session, "2-s2.0-999999999999") is None
