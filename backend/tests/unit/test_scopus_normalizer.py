"""Unit tests for the Scopus publication normalizer — M2.6A."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.normalization.scopus_normalizer import (
    CANONICAL_COMPARABLE_FIELDS,
    BATCH_SIZE,
    NormalizationCounters,
    NormalizationResult,
    Normalizer,
    ProvenanceConflict,
    _nullable_int_equal,
    _nullable_str_equal,
    compare_metadata,
    create_publication_from_raw,
    is_eid_valid,
    is_publication_eid_unique_violation,
    is_unrelated_integrity_error,
    link_provenance,
    normalize_batch,
    normalize_eid,
    normalize_single_raw,
)


# ---------------------------------------------------------------------------
# EID normalization
# ---------------------------------------------------------------------------

class TestNormalizeEid:
    def test_strips_whitespace(self) -> None:
        assert normalize_eid("  2-s2.0-123456789  ") == "2-s2.0-123456789"

    def test_returns_none_for_empty_string(self) -> None:
        assert normalize_eid("") is None

    def test_returns_none_for_whitespace_only(self) -> None:
        assert normalize_eid("   \t  ") is None

    def test_returns_none_for_none(self) -> None:
        assert normalize_eid(None) is None

    def test_returns_none_for_non_string(self) -> None:
        assert normalize_eid(123) is None

    def test_rejects_eid_with_internal_whitespace(self) -> None:
        assert normalize_eid("2-s2.0-123 456789") is None

    def test_rejects_eid_with_tab(self) -> None:
        assert normalize_eid("2-s2.0-\t123456789") is None

    def test_preserves_valid_eid_exactly(self) -> None:
        eid = "2-s2.0-85160473847"
        assert normalize_eid(eid) == eid

    def test_empty_after_strip_is_invalid(self) -> None:
        assert normalize_eid("   ") is None

    def test_leading_zero_stripped_values(self) -> None:
        assert normalize_eid("  2-s2.0-000000001") == "2-s2.0-000000001"


class TestIsEidValid:
    def test_valid_eid(self) -> None:
        assert is_eid_valid("2-s2.0-85160473847") is True

    def test_none_invalid(self) -> None:
        assert is_eid_valid(None) is False

    def test_empty_invalid(self) -> None:
        assert is_eid_valid("") is False

    def test_whitespace_invalid(self) -> None:
        assert is_eid_valid("   ") is False


# ---------------------------------------------------------------------------
# NormalizationCounters
# ---------------------------------------------------------------------------

class TestNormalizationCounters:
    def test_invariant_holds(self) -> None:
        c = NormalizationCounters(
            canonical_new=10,
            canonical_existing=20,
            canonical_metadata_changed=5,
            canonical_failed=2,
            canonical_intra_duplicate=3,
        )
        assert c.invariant_holds() is True
        assert c.canonical_processed == 37
        assert c.canonical_intra_duplicate == 3

    def test_intra_duplicate_less_than_processed(self) -> None:
        c = NormalizationCounters(
            canonical_new=10,
            canonical_existing=20,
            canonical_metadata_changed=5,
            canonical_failed=2,
            canonical_intra_duplicate=37,
        )
        assert c.invariant_holds() is True  # equal is allowed

    def test_to_dict(self) -> None:
        c = NormalizationCounters(
            canonical_new=5,
            canonical_existing=10,
            canonical_metadata_changed=2,
            canonical_failed=1,
            canonical_intra_duplicate=3,
        )
        d = c.to_dict()
        assert d["canonical_new"] == 5
        assert d["canonical_processed"] == 18
        assert d["canonical_intra_duplicate"] == 3

    def test_empty_counters(self) -> None:
        c = NormalizationCounters()
        assert c.canonical_new == 0
        assert c.canonical_processed == 0
        assert c.invariant_holds() is True


# ---------------------------------------------------------------------------
# Metadata comparison
# ---------------------------------------------------------------------------

class TestCompareMetadata:
    def _mock_pub(self, **kwargs) -> MagicMock:
        pub = MagicMock()
        defaults = dict(
            title="Original Title",
            title_normalized="original title",
            doi="10.1234/test",
            source_title="Journal A",
            year=2024,
            volume="10",
            issue="1",
            art_no=None,
            page_start="1",
            page_end="10",
            cited_by_count=5,
            document_type="Article",
            publication_stage="Final",
            open_access_status="Open Access",
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(pub, k, v)
        return pub

    def test_no_changes_returns_empty_list(self) -> None:
        pub = self._mock_pub()
        payload = {
            "Title": "Original Title",
            "Source": "Scopus",  # data provider, NOT the publication source
            "Source title": "Journal A",
            "Year": "2024",
            "Volume": "10",
            "Issue": "1",
            "Page start": "1",
            "Page end": "10",
            "Cited by": "5",
            "Document Type": "Article",
            "Publication Stage": "Final",
            "Open Access": "Open Access",
            "DOI": "10.1234/test",  # matches mock DOI
        }
        changed = compare_metadata(pub, {}, payload)
        assert changed == []

    def test_title_changed(self) -> None:
        pub = self._mock_pub()
        payload = {"Title": "Different Title"}
        changed = compare_metadata(pub, {}, payload)
        assert "title" in changed

    def test_year_changed(self) -> None:
        pub = self._mock_pub(year=2024)
        payload = {"Year": "2025"}
        changed = compare_metadata(pub, {}, payload)
        assert "year" in changed

    def test_doi_changed(self) -> None:
        pub = self._mock_pub(doi="10.1234/old")
        payload = {"DOI": "10.1234/new"}
        changed = compare_metadata(pub, {}, payload)
        assert "doi" in changed

    def test_null_vs_new_value(self) -> None:
        pub = self._mock_pub(doi=None)
        payload = {"DOI": "10.1234/new"}
        changed = compare_metadata(pub, {}, payload)
        assert "doi" in changed

    def test_whitespace_trimmed_in_comparison(self) -> None:
        pub = self._mock_pub(title="Title")
        payload = {"Title": "  Title  "}
        changed = compare_metadata(pub, {}, payload)
        assert "title" not in changed

    # -- source_title: ``Source title`` is the publication source, ``Source`` is the provider --

    def test_source_title_compares_against_source_title_column_not_source(self) -> None:
        pub = self._mock_pub(source_title="Journal A")
        payload = {"Source": "Scopus", "Source title": "Journal A"}
        assert "source_title" not in compare_metadata(pub, {}, payload)

    def test_provider_value_is_not_a_valid_source_title(self) -> None:
        """A row stored with the provider name ("Scopus") is a mapping defect."""
        pub = self._mock_pub(source_title="Scopus")
        payload = {"Source": "Scopus", "Source title": "Journal A"}
        assert "source_title" in compare_metadata(pub, {}, payload)

    def test_source_title_whitespace_is_trimmed_in_comparison(self) -> None:
        pub = self._mock_pub(source_title="Journal A")
        payload = {"Source": "Scopus", "Source title": "  Journal A  "}
        assert "source_title" not in compare_metadata(pub, {}, payload)

    def test_missing_source_title_is_not_filled_from_source(self) -> None:
        pub = self._mock_pub(source_title=None)
        payload = {"Source": "Scopus"}
        assert "source_title" not in compare_metadata(pub, {}, payload)


# ---------------------------------------------------------------------------
# Helper equality functions
# ---------------------------------------------------------------------------

class TestNullableHelpers:
    def test_nullable_str_equal_both_none(self) -> None:
        assert _nullable_str_equal(None, None) is True

    def test_nullable_str_equal_both_same(self) -> None:
        assert _nullable_str_equal("hello", "hello") is True

    def test_nullable_str_equal_trims_whitespace(self) -> None:
        assert _nullable_str_equal("  hello  ", "hello") is True

    def test_nullable_str_equal_diff(self) -> None:
        assert _nullable_str_equal("hello", "world") is False

    def test_nullable_str_equal_one_none(self) -> None:
        assert _nullable_str_equal("hello", None) is False

    def test_nullable_int_equal(self) -> None:
        assert _nullable_int_equal(5, 5) is True
        assert _nullable_int_equal(None, None) is True
        assert _nullable_int_equal(5, None) is False
        assert _nullable_int_equal(5, 6) is False


# ---------------------------------------------------------------------------
# Publication creation
# ---------------------------------------------------------------------------

class TestCreatePublicationFromRaw:
    def _mock_raw(self, eid: str | None = "2-s2.0-123", **kwargs) -> MagicMock:
        raw = MagicMock()
        defaults = dict(
            id=uuid.uuid4(),
            eid_raw=eid,
            validation_status="VALID",
            raw_payload={
                "Title": "Test Paper",
                "DOI": "10.1000/test",
                "Source": "Scopus",  # data provider, NOT the publication source
                "Source title": "Test Journal",
                "Year": "2025",
                "Volume": "1",
                "Issue": "2",
                "Art. No.": "A1",
                "Page start": "10",
                "Page end": "20",
                "Cited by": "3",
                "Document Type": "Article",
                "Publication Stage": "Final",
                "Open Access": "Open Access",
            },
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(raw, k, v)
        return raw

    def test_creates_publication_with_eid(self) -> None:
        raw = self._mock_raw(eid="2-s2.0-999")
        pub = create_publication_from_raw(raw)
        assert pub.eid == "2-s2.0-999"
        assert pub.title == "Test Paper"
        assert pub.doi == "10.1000/test"
        assert pub.year == 2025
        assert pub.version == 1

    def test_title_normalized_is_set(self) -> None:
        raw = self._mock_raw()
        pub = create_publication_from_raw(raw)
        assert pub.title_normalized == "test paper"

    def test_handles_missing_optional_fields(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload = {"Title": "Minimal Paper"}
        pub = create_publication_from_raw(raw)
        assert pub.title == "Minimal Paper"
        assert pub.doi is None
        assert pub.year is None

    def test_source_title_comes_from_source_title_column_not_source(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Source"] = "Scopus"
        raw.raw_payload["Source title"] = "Lecture Notes in Networks and Systems"
        pub = create_publication_from_raw(raw)
        assert pub.source_title == "Lecture Notes in Networks and Systems"
        assert pub.source_title != "Scopus"

    def test_source_title_whitespace_is_trimmed(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Source title"] = "  Journal of Tests \n"
        assert create_publication_from_raw(raw).source_title == "Journal of Tests"

    def test_missing_source_title_stays_none_and_is_not_filled_from_source(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Source"] = "Scopus"
        del raw.raw_payload["Source title"]
        assert create_publication_from_raw(raw).source_title is None

    @pytest.mark.parametrize("blank", ["", "   ", "\t\n", None])
    def test_blank_source_title_stays_none(self, blank) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Source"] = "Scopus"
        raw.raw_payload["Source title"] = blank
        assert create_publication_from_raw(raw).source_title is None

    def test_creation_and_comparison_agree_so_reruns_are_idempotent(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Source title"] = "  Journal A  "
        pub = create_publication_from_raw(raw)
        assert compare_metadata(pub, {}, raw.raw_payload) == []

    def test_bounded_canonical_fields_keep_reruns_idempotent(self) -> None:
        raw = self._mock_raw()
        raw.raw_payload["Open Access"] = (
            "All Open Access; Gold Open Access; Green Open Access"
        )
        pub = create_publication_from_raw(raw)

        assert len(pub.open_access_status) == 50
        assert compare_metadata(pub, {}, raw.raw_payload) == []


# ---------------------------------------------------------------------------
# Re-running normalization on an EID that already exists
# ---------------------------------------------------------------------------

class TestRerunOnExistingEid:
    """An existing canonical row is compared, never overwritten (invariant 3)."""

    def _existing(self, source_title: str | None) -> MagicMock:
        pub = MagicMock()
        pub.id = uuid.uuid4()
        pub.eid = "2-s2.0-555"
        for key, value in dict(
            title="Paper", title_normalized="paper", doi=None, source_title=source_title,
            year=2025, volume=None, issue=None, art_no=None, page_start=None,
            page_end=None, cited_by_count=0, document_type=None,
            publication_stage=None, open_access_status=None,
        ).items():
            setattr(pub, key, value)
        return pub

    def _raw(self, payload: dict) -> MagicMock:
        raw = MagicMock()
        raw.id = uuid.uuid4()
        raw.eid_raw = "2-s2.0-555"
        raw.validation_status = "VALID"
        raw.raw_payload = {"Title": "Paper", "Year": "2025", "Cited by": "0", **payload}
        return raw

    def _run(self, pub: MagicMock, raw: MagicMock):
        link = MagicMock()
        link.publication_id = pub.id
        db = MagicMock()
        result = normalize_single_raw(db, raw, {"2-s2.0-555": pub}, {raw.id: link})
        return result, db

    def test_wrong_stored_source_title_is_reported_but_not_overwritten(self) -> None:
        pub = self._existing("Scopus")
        raw = self._raw({"Source": "Scopus", "Source title": "Journal A"})
        result, db = self._run(pub, raw)
        assert result.outcome == "EXISTING_METADATA_CHANGED"
        assert result.changed_fields == ["source_title"]
        assert pub.source_title == "Scopus"  # untouched: correction is a separate, audited step
        db.add.assert_not_called()

    def test_correct_stored_source_title_is_unchanged(self) -> None:
        pub = self._existing("Journal A")
        raw = self._raw({"Source": "Scopus", "Source title": " Journal A "})
        result, db = self._run(pub, raw)
        assert result.outcome == "EXISTING_UNCHANGED"
        assert result.changed_fields == []
        assert pub.source_title == "Journal A"
        db.add.assert_not_called()

    def test_missing_source_title_does_not_change_an_empty_value(self) -> None:
        pub = self._existing(None)
        raw = self._raw({"Source": "Scopus"})
        result, _ = self._run(pub, raw)
        assert result.outcome == "EXISTING_UNCHANGED"
        assert pub.source_title is None


# ---------------------------------------------------------------------------
# Integrity error classification
# ---------------------------------------------------------------------------

class TestIsPublicationEidUniqueViolation:
    def _make_psycopg2_orig(self, pgcode: str, constname: str) -> MagicMock:
        orig = MagicMock()
        orig.pgcode = pgcode
        orig.constname = constname
        return orig

    def _make_diag_mock(self, constraint_name: str) -> MagicMock:
        diag = MagicMock()
        diag.constraint_name = constraint_name
        return diag

    def _make_exc_with_diag(self, orig: MagicMock, diag: MagicMock) -> MagicMock:
        exc = MagicMock()
        exc.orig = orig
        exc.orig.diag = diag
        return exc

    def _make_exc(self, orig: MagicMock) -> MagicMock:
        exc = MagicMock()
        exc.orig = orig
        return exc

    def test_23505_eid_constraint_is_true_via_constname(self) -> None:
        """When constname is explicitly 'uq_publications_eid' (some SQLAlchemy/driver versions)."""
        orig = self._make_psycopg2_orig("23505", "uq_publications_eid")
        exc = self._make_exc_with_diag(orig, self._make_diag_mock("uq_publications_eid"))
        assert is_publication_eid_unique_violation(exc) is True

    def test_23505_eid_constraint_is_true_via_diag(self) -> None:
        """When constname is 'N/A' but diag.constraint_name is correct (actual psycopg2 behavior)."""
        orig = self._make_psycopg2_orig("23505", "N/A")
        exc = self._make_exc_with_diag(orig, self._make_diag_mock("uq_publications_eid"))
        assert is_publication_eid_unique_violation(exc) is True

    def test_23505_different_constraint_is_false(self) -> None:
        orig = self._make_psycopg2_orig("23505", "uq_raw_scopus_records_import_row")
        diag = self._make_diag_mock("uq_raw_scopus_records_import_row")
        exc = self._make_exc_with_diag(orig, diag)
        assert is_publication_eid_unique_violation(exc) is False

    def test_different_pgcode_is_false(self) -> None:
        orig = self._make_psycopg2_orig("23503", "uq_publications_eid")  # FK violation
        diag = self._make_diag_mock("uq_publications_eid")
        exc = self._make_exc_with_diag(orig, diag)
        assert is_publication_eid_unique_violation(exc) is False

    def test_no_orig_is_false(self) -> None:
        exc = MagicMock()
        exc.orig = None
        assert is_publication_eid_unique_violation(exc) is False

    def test_unrelated_integrity_error(self) -> None:
        orig = self._make_psycopg2_orig("23503", "fk_some_fk")
        diag = self._make_diag_mock("fk_some_fk")
        exc = self._make_exc_with_diag(orig, diag)
        assert is_unrelated_integrity_error(exc) is True


# ---------------------------------------------------------------------------
# Normalizer class
# ---------------------------------------------------------------------------

class TestNormalizerClass:
    def test_record_new(self) -> None:
        n = Normalizer()
        n.record(NormalizationResult(outcome="NEW", publication=MagicMock()))
        assert n.counters.canonical_new == 1
        assert n.counters.canonical_processed == 1

    def test_record_existing_unchanged(self) -> None:
        n = Normalizer()
        n.record(NormalizationResult(outcome="EXISTING_UNCHANGED", publication=MagicMock()))
        assert n.counters.canonical_existing == 1

    def test_record_existing_changed(self) -> None:
        n = Normalizer()
        n.record(
            NormalizationResult(
                outcome="EXISTING_METADATA_CHANGED",
                publication=MagicMock(),
                changed_fields=["title"],
            )
        )
        assert n.counters.canonical_metadata_changed == 1

    def test_record_invalid_eid(self) -> None:
        n = Normalizer()
        n.record(NormalizationResult(outcome="INVALID_EID", publication=None))
        assert n.counters.canonical_failed == 1

    def test_record_error(self) -> None:
        n = Normalizer()
        n.record(
            NormalizationResult(
                outcome="NORMALIZATION_ERROR",
                publication=None,
                error_message="RAW_SOURCE_CANONICAL_CONFLICT",
            )
        )
        assert n.counters.canonical_failed == 1
        assert len(n.errors) == 1

    def test_invariant_maintained(self) -> None:
        n = Normalizer()
        n.record(NormalizationResult(outcome="NEW", publication=MagicMock()))
        n.record(NormalizationResult(outcome="EXISTING_UNCHANGED", publication=MagicMock()))
        n.record(NormalizationResult(outcome="EXISTING_METADATA_CHANGED", publication=MagicMock(), changed_fields=[]))
        n.record(NormalizationResult(outcome="INVALID_EID", publication=None))
        assert n.counters.invariant_holds() is True


# ---------------------------------------------------------------------------
# Provenance linking
# ---------------------------------------------------------------------------

class TestLinkProvenance:
    def test_idempotent_when_link_exists_same_pub(self) -> None:
        db = MagicMock()
        raw_id = uuid.uuid4()
        pub_id = uuid.uuid4()
        existing = MagicMock()
        existing.publication_id = pub_id
        db.query.return_value.filter.return_value.first.return_value = existing

        raw = MagicMock()
        raw.id = raw_id
        pub = MagicMock()
        pub.id = pub_id

        result = link_provenance(db, pub, raw)
        assert result is True

    def test_conflict_when_different_pub(self) -> None:
        db = MagicMock()
        raw_id = uuid.uuid4()
        pub_id_a = uuid.uuid4()
        pub_id_b = uuid.uuid4()
        existing = MagicMock()
        existing.publication_id = pub_id_a
        db.query.return_value.filter.return_value.first.return_value = existing

        raw = MagicMock()
        raw.id = raw_id
        pub = MagicMock()
        pub.id = pub_id_b

        with pytest.raises(ProvenanceConflict) as exc_info:
            link_provenance(db, pub, raw)
        assert exc_info.value.existing_pub_id == pub_id_a
        assert exc_info.value.attempted_pub_id == pub_id_b
