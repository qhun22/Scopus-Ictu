from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.governance import AuditEvent
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.parser.scopus_csv_parser import ScopusCsvParser
from app.services.scopus_import_service import (
    ImportAlreadyFinished,
    ImportAlreadyProcessing,
    _raw_records,
    cancel_import,
    is_import_eligible_for_normalization,
    to_import_response,
)


def make_import(status: str = "RECEIVED") -> ScopusImport:
    now = datetime.now(UTC)
    return ScopusImport(
        id=uuid.uuid4(),
        file_name="sample.csv",
        file_sha256="a" * 64,
        total_records=4,
        valid_records=2,
        invalid_records=1,
        status=status,
        error_summary=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


class FakeQuery:
    def __init__(self, item: ScopusImport | None) -> None:
        self.item = item

    def filter(self, *_args: object) -> FakeQuery:
        return self

    def first(self) -> ScopusImport | None:
        return self.item


class FakeSession:
    def __init__(self, item: ScopusImport | None) -> None:
        self.item = item
        self.added: list[object] = []
        self.commits = 0

    def query(self, _model: object) -> FakeQuery:
        return FakeQuery(self.item)

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


def test_response_uses_processed_count_and_never_claims_false_completion() -> None:
    item = make_import("VALIDATED")
    result = to_import_response(item, performed_by="Admin")

    assert result.processed_records == 3
    assert result.progress_percent == 75
    assert result.is_terminal is False
    assert result.finished_at is None


def test_duplicate_and_invalid_raw_rows_are_all_preserved() -> None:
    parsed = ScopusCsvParser().parse_bytes(
        b"EID,Title\nEID-1,One\nEID-1,Two\nEID-2,Bad,extra\n"
    )
    records = _raw_records(uuid.uuid4(), parsed)

    assert len(records) == 3
    assert [record.row_number for record in records] == [2, 3, 4]
    assert [record.validation_status for record in records] == ["VALID", "VALID", "INVALID"]
    assert records[0].eid_raw == records[1].eid_raw == "EID-1"


def test_cancel_is_terminal_audited_and_does_not_delete_raw_data() -> None:
    item = make_import("PARSING")
    db = FakeSession(item)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    result = cancel_import(db, item.id, actor)  # type: ignore[arg-type]

    assert result is not None and result.status == "CANCELLED"
    assert db.commits == 1
    assert any(
        isinstance(value, AuditEvent) and value.action == "SCOPUS_IMPORT_CANCELLED"
        for value in db.added
    )
    assert not any(isinstance(value, RawScopusRecord) for value in db.added)


def test_cancel_completed_import_is_rejected() -> None:
    item = make_import("STAGED")
    db = FakeSession(item)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    with pytest.raises(ImportAlreadyFinished):
        cancel_import(db, item.id, actor)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "eligible"),
    [("RECEIVED", False), ("VALIDATED", False), ("CANCELLED", False), ("STAGED", True)],
)
def test_downstream_guard_requires_completed_import(status: str, eligible: bool) -> None:
    assert is_import_eligible_for_normalization(make_import(status)) is eligible


def test_active_duplicate_exception_exposes_existing_id() -> None:
    identifier = uuid.uuid4()
    error = ImportAlreadyProcessing(identifier)
    assert error.existing_import_id == identifier
