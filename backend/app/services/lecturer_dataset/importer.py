"""Preview (read-only) and import (transactional) for M2.5A §27-§35.

This module is the single authoritative writer for the lecturer dataset
import pipeline. It follows the same pattern as
``app.services.scopus_import_service`` but writes to the lecturer
master-data tables (``lecturers``, ``lecturer_source_snapshots``,
``lecturer_known_publications``) and **never** touches ``users``.

Identity resolution
-------------------
Two records are considered the same lecturer when:

* they share a non-null ``staff_code`` (deterministic, primary key),
* OR — when ``staff_code`` is null on both — they share a
  case-insensitive ``institutional_email``,
* OR — when both of the above are null — they share the lower-cased
  full name AND the same department (a softer fallback that is
  flagged as a duplicate candidate rather than merged silently).

The first matching rule wins; tie-breaks always flag a conflict.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.governance import AuditEvent, User
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.services.lecturer_dataset.parser import parse_and_validate


class LecturerDatasetError(RuntimeError):
    """Raised by the import pipeline on hard failure (rollback path)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclasses.dataclass(frozen=True)
class LecturerPreviewSummary:
    total: int
    valid: int
    create: int
    update: int
    unchanged: int
    conflicts: int
    conflict_samples: list[dict]
    dataset: dict
    filename: str
    parser_version: str


@dataclasses.dataclass(frozen=True)
class LecturerImportSummary:
    total: int
    created: int
    updated: int
    unchanged: int
    conflicts: int
    conflict_samples: list[dict]
    snapshot_ids: list[str]
    dataset: dict
    filename: str
    parser_version: str


def _email_key(value: str | None) -> str:
    return (value or "").strip().lower()


def _staff_code_key(value: str | None) -> str | None:
    return value if value else None


def _name_department_key(full_name: str, department: str | None) -> tuple[str, str]:
    return (full_name.casefold().strip(), (department or "").casefold().strip())


def _ambiguous_name_candidate(
    candidates: list[tuple[uuid.UUID, str]],
    email: str | None,
    *,
    current_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Return a same-name candidate that email cannot disambiguate."""
    incoming_email = _email_key(email)
    for candidate_id, candidate_email in candidates:
        if current_id is not None and candidate_id == current_id:
            continue
        if incoming_email and candidate_email and incoming_email != candidate_email:
            continue
        return candidate_id
    return None


def _canonical_fields(record: dict) -> dict:
    """Return only the fields the import pipeline considers for equality
    (everything except provenance and timestamps)."""
    return {
        "full_name": record["full_name"],
        "staff_code": _staff_code_key(record.get("staff_code")),
        "institutional_email": _email_key(record.get("institutional_email")),
        "academic_degree": record.get("academic_degree"),
        "academic_rank": record.get("academic_rank"),
        "position": record.get("position"),
        "faculty": record.get("faculty"),
        "department": record.get("department"),
        "orcid": record.get("orcid"),
        "profile_url": record.get("profile_url"),
        "is_active": record.get("is_active", True),
    }


def _hash_payload(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _existing_index(db: Session, lecturer_ids: list[uuid.UUID]) -> dict[uuid.UUID, Lecturer]:
    if not lecturer_ids:
        return {}
    rows = db.query(Lecturer).filter(Lecturer.id.in_(lecturer_ids)).all()
    return {row.id: row for row in rows}


def _find_existing_lecturer(
    db: Session, record: dict, *,
    by_staff_code: dict[str, uuid.UUID],
    by_email: dict[str, uuid.UUID],
    by_name_dept: dict[tuple[str, str], list[tuple[uuid.UUID, str]]],
) -> tuple[Lecturer | None, str | None]:
    staff_code = _staff_code_key(record.get("staff_code"))
    email = _email_key(record.get("institutional_email"))
    if staff_code and staff_code in by_staff_code:
        return db.query(Lecturer).filter(Lecturer.id == by_staff_code[staff_code]).first(), "staff_code"
    if email and email in by_email:
        return db.query(Lecturer).filter(Lecturer.id == by_email[email]).first(), "email"
    return None, None


def _build_index(db: Session) -> dict[str, dict]:
    """Pre-index existing lecturers for O(1) lookups."""
    by_staff_code: dict[str, uuid.UUID] = {}
    by_email: dict[str, uuid.UUID] = {}
    by_name_dept: dict[tuple[str, str], list[tuple[uuid.UUID, str]]] = {}
    for row in db.query(Lecturer).all():
        if row.staff_code:
            by_staff_code.setdefault(row.staff_code, row.id)
        if row.email:
            by_email.setdefault(row.email.lower(), row.id)
        key = (row.full_name.casefold().strip(), (row.department or "").casefold().strip())
        by_name_dept.setdefault(key, []).append((row.id, _email_key(row.email)))
    return {
        "by_staff_code": by_staff_code,
        "by_email": by_email,
        "by_name_dept": by_name_dept,
    }


class LecturerPreviewService:
    """Compute the diff between an uploaded dataset and current DB state.

    The preview is read-only — it never mutates the database.
    """

    def __init__(self) -> None:
        self.dataset_meta: dict | None = None

    def preview(
        self,
        db: Session,
        *,
        filename: str,
        content: bytes,
    ) -> LecturerPreviewSummary:
        envelope = parse_and_validate(content, filename=filename)
        self.dataset_meta = envelope["dataset"]
        index = _build_index(db)

        existing_by_staff_code = dict(index["by_staff_code"])
        existing_by_email = dict(index["by_email"])
        existing_by_name_dept = {
            key: list(candidates) for key, candidates in index["by_name_dept"].items()
        }

        create = update = unchanged = conflicts = 0
        conflict_samples: list[dict] = []
        for record in envelope["lecturers"]:
            existing, identity_used = _find_existing_lecturer(
                db,
                record,
                by_staff_code=existing_by_staff_code,
                by_email=existing_by_email,
                by_name_dept=existing_by_name_dept,
            )
            canonical = _canonical_fields(record)
            name_dept_key = _name_department_key(record["full_name"], record.get("department"))
            collision_id = _ambiguous_name_candidate(
                existing_by_name_dept.get(name_dept_key, []),
                canonical["institutional_email"],
                current_id=existing.id if existing is not None else None,
            )
            has_name_collision = bool(name_dept_key[0] and collision_id is not None)

            if existing is None:
                create += 1
                if has_name_collision:
                    conflicts += 1
                    if len(conflict_samples) < 20:
                        conflict_samples.append({
                            "record_full_name": record["full_name"],
                            "matched_by": "name_department",
                            "existing_id": str(collision_id),
                            "existing_full_name": record["full_name"],
                            "existing_email": record.get("institutional_email"),
                        })
                dummy_id = uuid.uuid4()
                if canonical["staff_code"]:
                    existing_by_staff_code[canonical["staff_code"]] = dummy_id
                if canonical["institutional_email"]:
                    existing_by_email[canonical["institutional_email"]] = dummy_id
                existing_by_name_dept.setdefault(name_dept_key, []).append(
                    (dummy_id, canonical["institutional_email"])
                )
                continue

            current = {
                "full_name": existing.full_name,
                "staff_code": existing.staff_code,
                "institutional_email": (existing.email or "").lower(),
                "academic_degree": existing.academic_degree,
                "academic_rank": existing.academic_rank,
                "position": existing.position,
                "faculty": existing.faculty,
                "department": existing.department,
                "orcid": existing.orcid,
                "profile_url": existing.repository_profile_url,
                "is_active": existing.is_active,
            }
            if canonical == current:
                unchanged += 1
            else:
                update += 1
            if has_name_collision:
                conflicts += 1
                if len(conflict_samples) < 20:
                    conflict_samples.append({
                        "record_full_name": record["full_name"],
                        "matched_by": "name_department",
                        "existing_id": str(collision_id),
                        "existing_full_name": existing.full_name,
                        "existing_email": existing.email,
                    })
        return LecturerPreviewSummary(
            total=len(envelope["lecturers"]),
            valid=len(envelope["lecturers"]),
            create=create,
            update=update,
            unchanged=unchanged,
            conflicts=conflicts,
            conflict_samples=conflict_samples,
            dataset=envelope["dataset"],
            filename=filename,
            parser_version=envelope["dataset"].get("parser_version") or "unknown",
        )


class LecturerImportService:
    """Apply a previewed dataset to the lecturer master tables."""

    def __init__(self) -> None:
        self.dataset_meta: dict | None = None

    def import_dataset(
        self,
        db: Session,
        *,
        filename: str,
        content: bytes,
        actor: User,
        correlation_id: str | None = None,
    ) -> LecturerImportSummary:
        envelope = parse_and_validate(content, filename=filename)
        self.dataset_meta = envelope["dataset"]
        index = _build_index(db)
        now = datetime.now(UTC)
        snapshot_records: list[LecturerSourceSnapshot] = []
        created = updated = unchanged = conflicts = 0
        conflict_samples: list[dict] = []
        created_snapshot_ids: list[str] = []
        created_lecturer_ids: list[str] = []

        try:
            for record in envelope["lecturers"]:
                existing, identity_used = _find_existing_lecturer(
                    db,
                    record,
                    by_staff_code=index["by_staff_code"],
                    by_email=index["by_email"],
                    by_name_dept=index["by_name_dept"],
                )
                canonical = _canonical_fields(record)
                name_dept_key = _name_department_key(record["full_name"], record.get("department"))
                collision_id = _ambiguous_name_candidate(
                    index["by_name_dept"].get(name_dept_key, []),
                    canonical["institutional_email"],
                    current_id=existing.id if existing is not None else None,
                )
                has_name_collision = bool(name_dept_key[0] and collision_id is not None)
                provenance = record["provenance"]
                source_url = provenance["source_urls"][0] if provenance["source_urls"] else "unknown"
                if existing is None:
                    lecturer = Lecturer(
                        id=uuid.uuid4(),
                        staff_code=canonical["staff_code"],
                        full_name=canonical["full_name"],
                        full_name_normalized=record["full_name_normalized"],
                        email=canonical["institutional_email"],
                        academic_degree=canonical["academic_degree"],
                        academic_rank=canonical["academic_rank"],
                        position=canonical["position"],
                        faculty=canonical["faculty"],
                        department=canonical["department"],
                        repository_profile_url=canonical["profile_url"],
                        orcid=canonical["orcid"],
                        is_active=canonical["is_active"],
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(lecturer)
                    db.flush()
                    created_lecturer_ids.append(str(lecturer.id))
                    # Maintain the index so duplicates within the same
                    # dataset can be detected before flush.
                    if canonical["staff_code"]:
                        index["by_staff_code"][canonical["staff_code"]] = lecturer.id
                    if canonical["institutional_email"]:
                        index["by_email"][canonical["institutional_email"]] = lecturer.id
                    if has_name_collision:
                        conflicts += 1
                        if len(conflict_samples) < 20:
                            conflict_samples.append({
                                "record_full_name": record["full_name"],
                                "matched_by": "name_department",
                                "existing_id": str(collision_id),
                                "existing_full_name": record["full_name"],
                                "existing_email": record.get("institutional_email"),
                            })
                    index["by_name_dept"].setdefault(name_dept_key, []).append(
                        (lecturer.id, canonical["institutional_email"])
                    )
                    created += 1
                    lecturer_id = lecturer.id
                else:
                    current = {
                        "full_name": existing.full_name,
                        "staff_code": existing.staff_code,
                        "institutional_email": (existing.email or "").lower(),
                        "academic_degree": existing.academic_degree,
                        "academic_rank": existing.academic_rank,
                        "position": existing.position,
                        "faculty": existing.faculty,
                        "department": existing.department,
                        "orcid": existing.orcid,
                        "profile_url": existing.repository_profile_url,
                        "is_active": existing.is_active,
                    }
                    if canonical == current:
                        unchanged += 1
                        lecturer_id = existing.id
                    else:
                        existing.full_name = canonical["full_name"]
                        existing.full_name_normalized = record["full_name_normalized"]
                        existing.staff_code = canonical["staff_code"]
                        existing.email = canonical["institutional_email"]
                        existing.academic_degree = canonical["academic_degree"]
                        existing.academic_rank = canonical["academic_rank"]
                        existing.position = canonical["position"]
                        existing.faculty = canonical["faculty"]
                        existing.department = canonical["department"]
                        existing.repository_profile_url = canonical["profile_url"]
                        existing.orcid = canonical["orcid"]
                        existing.is_active = canonical["is_active"]
                        # Optimistic-lock semantics. The version is
                        # bumped by SQLAlchemy on flush; we do not
                        # touch updated_at here so unchanged records
                        # keep their original timestamps (M2.5A §32).
                        db.flush()
                        updated += 1
                        lecturer_id = existing.id
                    if has_name_collision:
                        conflicts += 1
                        if len(conflict_samples) < 20:
                            conflict_samples.append({
                                "record_full_name": record["full_name"],
                                "matched_by": "name_department",
                                "existing_id": str(collision_id),
                                "existing_full_name": existing.full_name,
                                "existing_email": existing.email,
                            })

                # Per-record snapshot (append-only).
                snapshot = LecturerSourceSnapshot(
                    id=uuid.uuid4(),
                    lecturer_id=lecturer_id,
                    source_system=provenance["source_system"],
                    source_url=source_url,
                    snapshot_hash=_hash_payload(canonical),
                    raw_payload={
                        "canonical": canonical,
                        "provenance": provenance,
                    },
                    parser_version=envelope["dataset"].get("parser_version") or "unknown",
                    validation_status="VALID",
                    validation_errors=[],
                    fetched_at=now,
                    created_at=now,
                )
                db.add(snapshot)
                db.flush()
                snapshot_records.append(snapshot)
                created_snapshot_ids.append(str(snapshot.id))
                for pub in record.get("known_publications") or []:
                    kp = LecturerKnownPublication(
                        id=uuid.uuid4(),
                        lecturer_id=lecturer_id,
                        snapshot_id=snapshot.id,
                        title_raw=pub["title_raw"],
                        title_normalized=pub["title_normalized"],
                        doi_raw=pub.get("doi_raw"),
                        doi_normalized=pub.get("doi_normalized"),
                        source_title_raw=pub.get("source_title_raw"),
                        published_year=pub.get("published_year"),
                        created_at=now,
                    )
                    db.add(kp)

            # Audit the entire batch in a single event.
            audit_metadata: dict[str, Any] = {
                "dataset_name": envelope["dataset"].get("name"),
                "dataset_schema_version": envelope["dataset"].get("schema_version"),
                "filename": filename,
                "record_count": len(envelope["lecturers"]),
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "conflicts": conflicts,
                "warnings": conflicts,
                "snapshot_ids": created_snapshot_ids,
                "created_lecturer_ids": created_lecturer_ids,
                "parser_version": envelope["dataset"].get("parser_version") or "unknown",
            }
            audit_entity_id = uuid.uuid4()  # batch aggregate id
            audit = AuditEvent(
                entity_type="lecturer_dataset",
                entity_id=audit_entity_id,
                action="LECTURER_DATASET_IMPORTED",
                actor_type="USER",
                actor_user_id=actor.id,
                before_state=None,
                after_state={
                    "status": "IMPORTED",
                    "created": created,
                    "updated": updated,
                    "unchanged": unchanged,
                    "conflicts": conflicts,
                    "warnings": conflicts,
                    "record_count": len(envelope["lecturers"]),
                    "snapshot_ids": created_snapshot_ids,
                    "created_lecturer_ids": created_lecturer_ids,
                },
                event_metadata=audit_metadata,
                correlation_id=correlation_id,
            )
            db.add(audit)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise LecturerDatasetError(
                "LECTURER_IMPORT_FAILED",
                "Không thể ghi dữ liệu giảng viên vào cơ sở dữ liệu.",
            ) from exc

        return LecturerImportSummary(
            total=len(envelope["lecturers"]),
            created=created,
            updated=updated,
            unchanged=unchanged,
            conflicts=conflicts,
            conflict_samples=conflict_samples,
            snapshot_ids=created_snapshot_ids,
            dataset=envelope["dataset"],
            filename=filename,
            parser_version=envelope["dataset"].get("parser_version") or "unknown",
        )


__all__ = [
    "LecturerDatasetError",
    "LecturerImportService",
    "LecturerImportSummary",
    "LecturerPreviewService",
    "LecturerPreviewSummary",
]
