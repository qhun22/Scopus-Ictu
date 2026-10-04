"""Unit tests for M2.6B author parser.

Covers:
- 1 author / multiple authors
- spaces around semicolons
- mismatched list lengths
- missing ID
- non-numeric ID
- embedded full-name ID mismatch
- duplicate same ID in one publication
- Unicode normalization
- full name stripping "(ID)"
- empty fields
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.scopus_raw import RawScopusRecord
from app.services.normalization.scopus_author_normalizer import (
    _split_semicolon,
    normalize_name,
    parse_author_occurrences,
)


def _make_raw_record(
    authors: str,
    full_names: str,
    author_ids: str,
    row_number: int = 1,
) -> RawScopusRecord:
    """Helper: build a RawScopusRecord with the given author fields."""
    return RawScopusRecord(
        id=uuid.uuid4(),
        import_id=uuid.uuid4(),
        row_number=row_number,
        row_hash="fakehash",
        eid_raw="2-s2.0-12345",
        doi_raw=None,
        raw_payload={
            "Authors": authors,
            "Author full names": full_names,
            "Author(s) ID": author_ids,
        },
        validation_status="VALID",
        validation_errors=None,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# _split_semicolon
# ---------------------------------------------------------------------------

class TestSplitSemicolon:
    def test_single_value(self):
        assert _split_semicolon("Nguyen T.") == ["Nguyen T."]

    def test_multiple_values(self):
        assert _split_semicolon("Nguyen T.; Dao H.-D.; Le Q.") == [
            "Nguyen T.",
            "Dao H.-D.",
            "Le Q.",
        ]

    def test_spaces_trimmed(self):
        assert _split_semicolon("  Nguyen T.  ;  Dao H.  ;  ") == [
            "Nguyen T.",
            "Dao H.",
        ]

    def test_trailing_semicolon_dropped(self):
        assert _split_semicolon("Nguyen T.; Dao H.;") == ["Nguyen T.", "Dao H."]

    def test_empty_string(self):
        assert _split_semicolon("") == []

    def test_whitespace_only(self):
        assert _split_semicolon("   ") == []

    def test_mixed_spacing(self):
        assert _split_semicolon("  A ; B ; C  ") == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_basic_lowercase(self):
        assert normalize_name("NGUYEN") == "nguyen"

    def test_whitespace_collapsed(self):
        assert normalize_name("Nguyen   T.") == "nguyen t."

    def test_nfkc_normalization(self):
        # Common Unicode ligature/normalization cases
        # ½ full-width 2
        assert normalize_name("  Hello World  ") == "hello world"

    def test_empty(self):
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""


# ---------------------------------------------------------------------------
# parse_author_occurrences
# ---------------------------------------------------------------------------

class TestParseAuthorOccurrences:
    def test_single_author(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, Thanh-Tung (58035626100)",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert len(occurrences) == 1
        assert occurrences[0].scopus_id == "58035626100"
        assert occurrences[0].display_name == "Nguyen T."
        assert occurrences[0].full_name == "Nguyen, Thanh-Tung"
        assert occurrences[0].author_order == 1
        assert occurrences[0].embedded_id_matches is True

    def test_multiple_authors(self):
        record = _make_raw_record(
            authors="Nguyen T.-T.; Dao H.-D.; Le Q.",
            full_names="Nguyen, Thanh-Tung (58035626100); Dao, Huy-Du (58035840500); Le, Quan (58035999999)",
            author_ids="58035626100; 58035840500; 58035999999",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert len(occurrences) == 3
        assert occurrences[0].scopus_id == "58035626100"
        assert occurrences[0].author_order == 1
        assert occurrences[1].scopus_id == "58035840500"
        assert occurrences[1].author_order == 2
        assert occurrences[2].scopus_id == "58035999999"
        assert occurrences[2].author_order == 3

    def test_spaces_around_semicolons(self):
        record = _make_raw_record(
            authors="  Nguyen T.  ;  Dao H.  ",
            full_names="Nguyen, T. (1); Dao, H. (2)",
            author_ids="1; 2",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert len(occurrences) == 2
        assert occurrences[0].display_name == "Nguyen T."
        assert occurrences[1].display_name == "Dao H."

    def test_mismatched_list_lengths_full_names(self):
        record = _make_raw_record(
            authors="Nguyen T.; Dao H.; Le Q.",
            full_names="Nguyen, T. (1)",  # only 1 full name for 3 authors
            author_ids="1; 2; 3",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_LIST_LENGTH_MISMATCH"
        # All three lists must be exactly equal — fail closed, no partial processing
        assert len(occurrences) == 0

    def test_mismatched_list_lengths_ids(self):
        record = _make_raw_record(
            authors="Nguyen T.; Dao H.",
            full_names="Nguyen, T. (1); Dao, H. (2)",
            author_ids="1",  # only 1 ID for 2 authors
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_LIST_LENGTH_MISMATCH"
        # Fail closed: no partial processing when lists are unequal
        assert len(occurrences) == 0

    def test_missing_scopus_id(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, T.",
            author_ids="",  # empty string → empty list after split
        )
        occurrences, errors = parse_author_occurrences(record)
        # Empty IDs → 0-length list; lists unequal → fail closed
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_LIST_LENGTH_MISMATCH"
        assert len(occurrences) == 0

    def test_non_numeric_id(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, T.",
            author_ids="ABC123",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 1
        assert errors[0]["code"] == "NON_NUMERIC_SCOPUS_ID"
        assert len(occurrences) == 0

    def test_embedded_id_mismatch(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, Thanh-Tung (99999999999)",  # embedded ID ≠ Author(s) ID
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_ID_MISMATCH"
        # Do NOT create occurrence for identity-inconsistent row
        assert len(occurrences) == 0

    def test_duplicate_id_in_one_publication(self):
        record = _make_raw_record(
            authors="Nguyen T.; Dao H.",
            full_names="Nguyen, T. (1); Dao, H. (1)",  # same ID twice
            author_ids="1; 1",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 1
        assert errors[0]["code"] == "DUPLICATE_SCOPUS_ID_IN_PUBLICATION"
        # First author is accepted, second is rejected as duplicate
        assert len(occurrences) == 1
        assert occurrences[0].scopus_id == "1"
        assert occurrences[0].author_order == 1

    def test_full_name_strips_embedded_id(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, Thanh-Tung (58035626100)",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert occurrences[0].full_name == "Nguyen, Thanh-Tung"
        assert "(58035626100)" not in occurrences[0].full_name

    def test_full_name_no_embedded_id(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="Nguyen, Thanh-Tung",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert occurrences[0].full_name == "Nguyen, Thanh-Tung"

    def test_empty_full_name(self):
        record = _make_raw_record(
            authors="Unknown Author",
            full_names="",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        # Empty full_names → length mismatch → fail closed, no processing
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_LIST_LENGTH_MISMATCH"
        assert len(occurrences) == 0

    def test_unicode_vietnamese_names(self):
        record = _make_raw_record(
            authors="Nguyễn T.",
            full_names="Nguyễn, Thị Minh (58035626100)",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert len(errors) == 0
        assert len(occurrences) == 1
        assert occurrences[0].scopus_id == "58035626100"

    def test_empty_authors_field(self):
        record = _make_raw_record(
            authors="",
            full_names="",
            author_ids="",
        )
        occurrences, errors = parse_author_occurrences(record)
        # List length mismatch errors for the counts, but 0 occurrences
        assert len(occurrences) == 0

    def test_author_order_is_1_based(self):
        record = _make_raw_record(
            authors="A; B; C",
            full_names="A (1); B (2); C (3)",
            author_ids="1; 2; 3",
        )
        occurrences, errors = parse_author_occurrences(record)
        assert [o.author_order for o in occurrences] == [1, 2, 3]

    def test_trailing_semicolon_in_ids(self):
        record = _make_raw_record(
            authors="A; B",
            full_names="A (1); B (2)",
            author_ids="1; 2;",
        )
        occurrences, errors = parse_author_occurrences(record)
        # Split should handle trailing semicolon gracefully
        assert len(occurrences) == 2

    def test_no_author_full_names_column_present_but_empty(self):
        record = _make_raw_record(
            authors="Nguyen T.",
            full_names="",
            author_ids="58035626100",
        )
        occurrences, errors = parse_author_occurrences(record)
        # Length mismatch → fail closed, no partial processing
        assert len(errors) == 1
        assert errors[0]["code"] == "AUTHOR_LIST_LENGTH_MISMATCH"
        assert len(occurrences) == 0
