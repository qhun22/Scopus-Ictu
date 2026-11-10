"""Read retained JSON Scopus references without confirming any identity links."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer, LecturerSourceSnapshot
from app.models.publication import ScopusAuthor
from app.services.lecturer_dataset.exporter import ICTU_SOURCE_SYSTEM
from app.services.primary_scopus_identity import explicit_primary


def pending_scopus_imports(db: Session, lecturer_id: uuid.UUID | None = None) -> list[dict]:
    statement = (
        select(LecturerSourceSnapshot, Lecturer)
        .join(Lecturer, Lecturer.id == LecturerSourceSnapshot.lecturer_id)
        .where(LecturerSourceSnapshot.source_system == ICTU_SOURCE_SYSTEM,
               LecturerSourceSnapshot.validation_status == "VALID")
        .order_by(LecturerSourceSnapshot.created_at.desc(), LecturerSourceSnapshot.id.desc())
    )
    if lecturer_id is not None:
        statement = statement.where(Lecturer.id == lecturer_id)
    references: dict[uuid.UUID, dict] = {}
    for snapshot, lecturer in db.execute(statement).all():
        payload = snapshot.raw_payload
        if lecturer.id in references or "scopus_ids" not in payload:
            continue
        references[lecturer.id] = {
            "lecturer_id": str(lecturer.id), "full_name": lecturer.full_name,
            "institutional_email": lecturer.email, "scopus_ids": payload["scopus_ids"],
            "primary_scopus_id": payload.get("primary_scopus_id"),
        }
    if not references:
        return []
    saved: dict[uuid.UUID, dict[str, uuid.UUID]] = {}
    for lid, scopus_id, identity_id in db.execute(
        select(
            LecturerScopusIdentity.lecturer_id, ScopusAuthor.scopus_id, LecturerScopusIdentity.id,
        )
        .join(ScopusAuthor, ScopusAuthor.id == LecturerScopusIdentity.scopus_author_id)
        .where(LecturerScopusIdentity.lecturer_id.in_(list(references)),
               LecturerScopusIdentity.status == "APPROVED")
    ).all():
        saved.setdefault(lid, {})[scopus_id] = identity_id
    pending = []
    for lid, item in references.items():
        if not item["scopus_ids"]:
            continue
        approved = saved.get(lid, {})
        missing = any(sid not in approved for sid in item["scopus_ids"])
        primary = item["primary_scopus_id"]
        if missing or (primary and explicit_primary(db, lid) != approved.get(primary)):
            pending.append(item)
    return sorted(pending, key=lambda item: (item["full_name"], item["lecturer_id"]))
