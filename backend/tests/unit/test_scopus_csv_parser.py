from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.parser.scopus_csv_parser import ScopusCsvError, ScopusCsvParser
from app.services.scopus_import_service import validate_upload_filename

FIXTURE = Path(__file__).parents[1] / "fixtures" / "scopus_sample.csv"


def test_valid_csv_preserves_source_values_and_hash_contract() -> None:
    parsed = ScopusCsvParser().parse_bytes(FIXTURE.read_bytes())

    assert len(parsed.rows) == 2
    first = parsed.rows[0]
    assert first.raw_payload["Authors"] == "Author A, Author B"
    assert first.raw_payload["Title"] == "A synthetic, quoted title"
    assert first.raw_payload["Year"] == "2025"
    assert first.eid_raw == "2-s2.0-000000001"
    assert first.doi_raw == "10.0000/example.1"
    expected = hashlib.sha256(
        json.dumps(
            [
                "Author A, Author B",
                "A synthetic, quoted title",
                "2025",
                "2-s2.0-000000001",
                "10.0000/example.1",
            ],
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert first.row_hash == expected


def test_utf8_bom_quoted_newline_and_blank_rows() -> None:
    content = (
        "\ufeffAuthors,Title,EID\r\n"
        'Author A,"Title on line one\r\nand line two",EID-1\r\n'
        ",,\r\n"
        "Author B,Second,EID-2\r\n"
    ).encode("utf-8")

    parsed = ScopusCsvParser().parse_bytes(content)

    assert parsed.headers[0] == "Authors"
    assert len(parsed.rows) == 2
    assert parsed.rows[0].raw_payload["Title"] == "Title on line one\r\nand line two"
    assert [row.eid_raw for row in parsed.rows] == ["EID-1", "EID-2"]


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "EMPTY_IMPORT_FILE"),
        (b"Authors,Title\n", "INVALID_CSV"),
        (b"Authors,,EID\nA,T,E\n", "INVALID_CSV_HEADER"),
        (b"Authors,Title,Authors\nA,T,B\n", "INVALID_CSV_HEADER"),
        (b'Authors,Title\nA,"unterminated\n', "INVALID_CSV"),
        (b"\xff\xfe\x00", "INVALID_CSV"),
    ],
)
def test_invalid_csv_is_rejected(content: bytes, code: str) -> None:
    with pytest.raises(ScopusCsvError) as exc_info:
        ScopusCsvParser().parse_bytes(content)
    assert exc_info.value.code == code


def test_duplicate_eid_is_valid_raw_provenance() -> None:
    content = b"EID,Title\nEID-1,First\nEID-1,Second\n"
    first = ScopusCsvParser().parse_bytes(content)
    second = ScopusCsvParser().parse_bytes(content)
    assert len(first.rows) == len(second.rows) == 2
    assert first.duplicate_candidates == 1
    assert first.duplicate_row_numbers == (3,)


def test_bad_row_is_recoverable_and_does_not_drop_other_rows() -> None:
    parsed = ScopusCsvParser().parse_bytes(
        b"Authors,Title\nA,Good\nB,Bad,extra\nC,Also good\n"
    )

    assert parsed.total_records == 3
    assert [row.row_number for row in parsed.rows] == [2, 4]
    assert len(parsed.row_errors) == 1
    assert parsed.row_errors[0].row_number == 3
    assert parsed.row_errors[0].code == "COLUMN_COUNT_MISMATCH"


@pytest.mark.parametrize(
    "filename",
    ["../sample.csv", "..\\sample.csv", "C:\\sample.csv", "NUL.csv", "sample.xlsx", ""],
)
def test_unsafe_or_unsupported_filename_is_rejected(filename: str) -> None:
    with pytest.raises(ValueError):
        validate_upload_filename(filename)


def test_csv_filename_is_accepted_case_insensitively() -> None:
    assert validate_upload_filename("Scopus Export.CSV") == "Scopus Export.CSV"
