"""Unit tests for the lecturer-dataset parser (stdlib-friendly, no DB)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.lecturer_dataset.parser import (
    DatasetValidationError,
    parse_and_validate,
)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ictu_lecturers_fixture.json"


def _load_fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def _fixture_envelope() -> dict[str, Any]:
    return json.loads(_load_fixture_bytes().decode("utf-8"))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_parse_fixture_returns_envelope() -> None:
    envelope = parse_and_validate(_load_fixture_bytes(), filename="ictu_lecturers_fixture.json")
    assert envelope["dataset"]["schema_version"] == "1.0"
    assert envelope["dataset"]["record_count"] == len(envelope["lecturers"]) == 5
    for record in envelope["lecturers"]:
        assert record["full_name"]
        assert record["faculty"]
        assert record["department"]
        assert record["provenance"]["source_urls"]


def test_parse_normalises_full_name_whitespace() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][0]["full_name"] = "   Nguyen    Van   Test A  "
    raw = json.dumps(payload).encode("utf-8")
    envelope = parse_and_validate(raw)
    assert envelope["lecturers"][0]["full_name"] == "Nguyen Van Test A"


def test_parse_lowercases_institutional_email() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][0]["institutional_email"] = "TEST.A@EXAMPLE.INVALID"
    raw = json.dumps(payload).encode("utf-8")
    envelope = parse_and_validate(raw)
    assert envelope["lecturers"][0]["institutional_email"] == "test.a@example.invalid"


# ---------------------------------------------------------------------------
# Hard failures
# ---------------------------------------------------------------------------

def test_parse_rejects_invalid_json() -> None:
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(b"{ this is not json", filename="bad.json")
    assert exc.value.code == "INVALID_LECTURER_DATASET"


def test_parse_rejects_unsupported_schema_version() -> None:
    payload = _fixture_envelope()
    payload["dataset"]["schema_version"] = "2.0"
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "UNSUPPORTED_DATASET_SCHEMA"


def test_parse_rejects_duplicate_emails() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][1]["institutional_email"] = payload["lecturers"][0]["institutional_email"]
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "DUPLICATE_LECTURER_IDENTITY"


def test_parse_rejects_duplicate_staff_codes() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][1]["staff_code"] = payload["lecturers"][0]["staff_code"]
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "DUPLICATE_LECTURER_IDENTITY"


def test_parse_rejects_invalid_orcid() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][0]["orcid"] = "not-an-orcid"
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "INVALID_LECTURER_DATASET"


def test_parse_rejects_invalid_email() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][0]["institutional_email"] = "not-an-email"
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "INVALID_LECTURER_DATASET"


def test_parse_rejects_record_count_mismatch() -> None:
    payload = _fixture_envelope()
    payload["dataset"]["record_count"] = 999
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "INVALID_LECTURER_DATASET"


def test_parse_rejects_empty_lecturers() -> None:
    payload = _fixture_envelope()
    payload["lecturers"] = []
    payload["dataset"]["record_count"] = 0
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "INVALID_LECTURER_DATASET"


def test_parse_rejects_invalid_known_publication() -> None:
    payload = _fixture_envelope()
    payload["lecturers"][0]["known_publications"] = [{"title_raw": ""}]
    raw = json.dumps(payload).encode("utf-8")
    with pytest.raises(DatasetValidationError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "INVALID_LECTURER_DATASET"


# ---------------------------------------------------------------------------
# Idempotency-relevant: ensure canonical equality captures identity fields
# ---------------------------------------------------------------------------

def test_two_identical_records_yield_same_canonical_payload() -> None:
    payload_a = _fixture_envelope()
    payload_b = _fixture_envelope()
    raw_a = json.dumps(payload_a).encode("utf-8")
    raw_b = json.dumps(payload_b).encode("utf-8")
    a = parse_and_validate(raw_a)
    b = parse_and_validate(raw_b)
    assert a["lecturers"][0]["full_name"] == b["lecturers"][0]["full_name"]
    assert a["lecturers"][0]["staff_code"] == b["lecturers"][0]["staff_code"]
    assert a["lecturers"][0]["institutional_email"] == b["lecturers"][0]["institutional_email"]
