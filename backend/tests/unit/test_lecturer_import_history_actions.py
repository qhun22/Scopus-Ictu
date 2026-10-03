from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import APIError
from app.models.governance import AuditEvent
from app.services.lecturer_dataset.rollback import (
    LecturerRollbackError,
    LecturerRollbackService,
)
from app.services.scopus_import_service import (
    delete_lecturer_import_history,
    list_imports,
)


class _Query:
    def __init__(self, result: object | None) -> None:
        self.result = result

    def filter(self, *_args: object) -> _Query:
        return self

    def first(self) -> object | None:
        return self.result

    def order_by(self, *_args: object) -> _Query:
        return self

    def limit(self, _value: int) -> _Query:
        return self

    def all(self) -> list[object]:
        return self.result if isinstance(self.result, list) else []


class _Session:
    def __init__(self, *results: object | None) -> None:
        self.results = list(results)
        self.added: list[object] = []
        self.committed = False

    def query(self, _model: object) -> _Query:
        return _Query(self.results.pop(0))

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.committed = True


def _import_audit(import_id: uuid.UUID, entity_id: uuid.UUID) -> AuditEvent:
    return AuditEvent(
        id=import_id,
        entity_type="lecturer_dataset",
        entity_id=entity_id,
        action="LECTURER_DATASET_IMPORTED",
        event_metadata={"filename": "ictu_lecturers.json"},
    )


def test_delete_history_requires_rollback() -> None:
    import_id = uuid.uuid4()
    audit = _import_audit(import_id, uuid.uuid4())
    session = _Session(audit, None)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    with pytest.raises(APIError) as exc_info:
        delete_lecturer_import_history(session, import_id=import_id, actor=actor)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "LECTURER_IMPORT_NOT_ROLLED_BACK"
    assert session.added == []
    assert session.committed is False


def test_delete_history_adds_marker_after_rollback() -> None:
    import_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    audit = _import_audit(import_id, entity_id)
    rolled_back = SimpleNamespace(action="LECTURER_DATASET_ROLLED_BACK")
    session = _Session(audit, rolled_back, None)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    assert delete_lecturer_import_history(
        session,
        import_id=import_id,
        actor=actor,
    )

    assert session.committed is True
    assert len(session.added) == 1
    marker = session.added[0]
    assert isinstance(marker, AuditEvent)
    assert marker.action == "LECTURER_DATASET_HISTORY_DELETED"
    assert marker.entity_id == entity_id
    assert marker.event_metadata["import_id"] == str(import_id)


def test_deleted_history_marker_hides_import_from_history() -> None:
    import_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    audit = _import_audit(import_id, entity_id)
    marker = AuditEvent(
        id=uuid.uuid4(),
        entity_type="lecturer_dataset",
        entity_id=entity_id,
        action="LECTURER_DATASET_HISTORY_DELETED",
        event_metadata={"import_id": str(import_id)},
    )
    session = _Session([], [audit], [], [marker])

    assert list_imports(session) == []


def test_delete_history_is_idempotent() -> None:
    import_id = uuid.uuid4()
    audit = _import_audit(import_id, uuid.uuid4())
    rolled_back = SimpleNamespace(action="LECTURER_DATASET_ROLLED_BACK")
    already_deleted = SimpleNamespace(action="LECTURER_DATASET_HISTORY_DELETED")
    session = _Session(audit, rolled_back, already_deleted)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    assert delete_lecturer_import_history(
        session,
        import_id=import_id,
        actor=actor,
    )
    assert session.added == []
    assert session.committed is False


def test_rollback_detects_existing_event_linked_by_batch_entity_id() -> None:
    import_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    audit = _import_audit(import_id, entity_id)
    rolled_back = AuditEvent(
        id=uuid.uuid4(),
        entity_type="lecturer_dataset",
        entity_id=entity_id,
        action="LECTURER_DATASET_ROLLED_BACK",
    )
    session = _Session(audit, rolled_back)
    actor = SimpleNamespace(id=uuid.uuid4(), display_name="Admin")

    with pytest.raises(LecturerRollbackError) as exc_info:
        LecturerRollbackService().rollback_import(
            session,
            import_id=import_id,
            actor=actor,
        )

    assert exc_info.value.code == "LECTURER_IMPORT_ALREADY_ROLLED_BACK"
    assert session.added == []
