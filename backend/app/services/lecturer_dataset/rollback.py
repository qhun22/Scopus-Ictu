"""Transactional rollback service for lecturer dataset imports.

Enforces provenance-driven ownership rules (M2.5A §35):
- Manual lecturers are always preserved.
- Lecturers created solely by this import are safely removed.
- Pre-existing lecturers updated by this import are preserved and restored
  to their prior state if earlier snapshot provenance exists.
- Multi-source lecturers retain non-import provenance and are preserved.
- Lecturers linked to user accounts or downstream Scopus identities BLOCK
  rollback with LECTURER_IMPORT_IN_USE (409) without deleting or unlinking users.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.governance import AuditEvent, User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)


class LecturerRollbackError(RuntimeError):
    """Raised when import rollback is blocked or fails."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 409,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data or {}


@dataclasses.dataclass(frozen=True)
class LecturerRollbackSummary:
    import_id: uuid.UUID
    filename: str
    actor_user_id: uuid.UUID
    created_records_removed: int
    updated_records_restored: int
    manual_records_preserved: int
    multi_source_records_preserved: int
    blocked_records: int
    rolled_back_at: datetime


class LecturerRollbackService:
    """Execute atomic rollback of a lecturer dataset import."""

    def rollback_import(
        self,
        db: Session,
        *,
        import_id: uuid.UUID,
        actor: User,
    ) -> LecturerRollbackSummary:
        now = datetime.now(UTC)

        # 1. Locate the import audit event. The public history ID is the audit
        # event ID, while rollback events are linked by the batch entity ID.
        audit = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == "lecturer_dataset",
                AuditEvent.action == "LECTURER_DATASET_IMPORTED",
                (AuditEvent.id == import_id) | (AuditEvent.entity_id == import_id),
            )
            .first()
        )

        if audit is None:
            raise LecturerRollbackError(
                "LECTURER_IMPORT_NOT_FOUND",
                "Không tìm thấy đợt nhập giảng viên cần hoàn tác.",
                status_code=404,
            )

        # 2. Check rollback state using the canonical batch entity ID. Checking
        # only against ``import_id`` misses events when audit.id != audit.entity_id.
        batch_entity_id = audit.entity_id or audit.id
        rolled_back_audit = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == "lecturer_dataset",
                AuditEvent.action == "LECTURER_DATASET_ROLLED_BACK",
                (AuditEvent.entity_id == batch_entity_id)
                | (AuditEvent.entity_id == audit.id),
            )
            .first()
        )
        if rolled_back_audit is not None:
            raise LecturerRollbackError(
                "LECTURER_IMPORT_ALREADY_ROLLED_BACK",
                "Đợt nhập này đã được hoàn tác trước đó.",
                status_code=409,
            )

        meta = audit.event_metadata or {}
        after = audit.after_state or {}

        # 3. Extract recorded snapshot IDs and created lecturer IDs (Authoritative Ownership)
        snapshot_ids_raw = meta.get("snapshot_ids") or after.get("snapshot_ids") or []
        batch_snapshot_ids: set[uuid.UUID] = set()
        for s in snapshot_ids_raw:
            try:
                batch_snapshot_ids.add(uuid.UUID(str(s)))
            except (ValueError, TypeError):
                pass

        created_lecturer_ids_raw = (
            meta.get("created_lecturer_ids")
            or after.get("created_lecturer_ids")
            or []
        )
        batch_created_lecturer_ids: set[uuid.UUID] = set()
        for lid in created_lecturer_ids_raw:
            try:
                batch_created_lecturer_ids.add(uuid.UUID(str(lid)))
            except (ValueError, TypeError):
                pass

        # Load snapshots belonging to this batch
        snapshots: list[LecturerSourceSnapshot] = []
        if batch_snapshot_ids:
            snapshots = (
                db.query(LecturerSourceSnapshot)
                .filter(LecturerSourceSnapshot.id.in_(batch_snapshot_ids))
                .all()
            )

        all_batch_lecturer_ids = {
            s.lecturer_id for s in snapshots if s.lecturer_id is not None
        }.union(batch_created_lecturer_ids)

        # 4. Categorize every touched lecturer
        to_delete_lecturer_ids: set[uuid.UUID] = set()
        to_restore_lecturers: list[tuple[Lecturer, dict]] = []
        manual_preserved_count = 0
        multi_source_count = 0

        for lecturer_id in all_batch_lecturer_ids:
            lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
            if lecturer is None:
                continue

            # Check all snapshots for this lecturer
            all_snapshots = (
                db.query(LecturerSourceSnapshot)
                .filter(LecturerSourceSnapshot.lecturer_id == lecturer_id)
                .order_by(LecturerSourceSnapshot.created_at.asc())
                .all()
            )

            other_snaps = [s for s in all_snapshots if s.id not in batch_snapshot_ids]

            if len(other_snaps) > 0:
                # CASE B & C: Pre-existing / Multi-source with prior snapshot
                multi_source_count += 1
                prev_snap = other_snaps[-1]
                prev_canonical = prev_snap.raw_payload.get("canonical")
                if prev_canonical and isinstance(prev_canonical, dict):
                    to_restore_lecturers.append((lecturer, prev_canonical))
                # Other provenance owns this lecturer too, so this import may
                # restore it but must never delete it.
            elif lecturer_id in batch_created_lecturer_ids:
                # CASE A: Explicitly recorded as created by this batch via
                # created_lecturer_ids (authoritative source). Queued for removal;
                # the blocker check below will raise 409 if a user or identity
                # has been linked since the import.
                to_delete_lecturer_ids.add(lecturer_id)
            else:
                # CASE D: Lecturer was only touched by this batch (no other
                # snapshots) and is not recorded as created by this batch.
                # Treat as a manually-created lecturer — preserve it.
                manual_preserved_count += 1

        # 5. Enforce Blockers BEFORE Mutating Database
        # Check User account linkage blocker
        if to_delete_lecturer_ids:
            linked_users = (
                db.query(User)
                .filter(User.lecturer_id.in_(to_delete_lecturer_ids))
                .all()
            )
            if linked_users:
                raise LecturerRollbackError(
                    "LECTURER_IMPORT_IN_USE",
                    f"Có {len(linked_users)} hồ sơ trong đợt nhập đang được liên kết "
                    "với tài khoản hệ thống. Vui lòng xử lý các liên kết trước.",
                    status_code=409,
                    data={"linked_accounts": len(linked_users)},
                )

            # Check downstream Scopus identities blocker
            linked_identities = (
                db.query(LecturerScopusIdentity)
                .filter(LecturerScopusIdentity.lecturer_id.in_(to_delete_lecturer_ids))
                .all()
            )
            if linked_identities:
                raise LecturerRollbackError(
                    "LECTURER_IMPORT_IN_USE",
                    "Không thể hoàn tác đợt nhập vì có "
                    f"{len(linked_identities)} hồ sơ đã phát sinh liên kết Scopus "
                    "hoặc dữ liệu downstream.",
                    status_code=409,
                    data={"dependent_identities": len(linked_identities)},
                )

        # 6. Atomic Rollback Execution
        created_removed_count = len(to_delete_lecturer_ids)
        updated_restored_count = 0

        try:
            # A. Restore fields of updated records from prior snapshot
            for lecturer, prev_canonical in to_restore_lecturers:
                new_full_name = prev_canonical.get("full_name", lecturer.full_name)
                lecturer.full_name = new_full_name
                lecturer.full_name_normalized = new_full_name.casefold().strip()
                lecturer.staff_code = prev_canonical.get("staff_code")
                lecturer.email = prev_canonical.get("institutional_email")
                lecturer.academic_degree = prev_canonical.get("academic_degree")
                lecturer.academic_rank = prev_canonical.get("academic_rank")
                lecturer.position = prev_canonical.get("position")
                lecturer.faculty = prev_canonical.get("faculty")
                lecturer.department = prev_canonical.get("department")
                lecturer.repository_profile_url = prev_canonical.get("profile_url")
                lecturer.orcid = prev_canonical.get("orcid")
                lecturer.is_active = prev_canonical.get("is_active", True)
                updated_restored_count += 1

            # B. Delete known publications belonging to this batch
            if batch_snapshot_ids:
                db.query(LecturerKnownPublication).filter(
                    LecturerKnownPublication.snapshot_id.in_(batch_snapshot_ids)
                ).delete(synchronize_session=False)

            # C. Delete snapshots belonging to this batch
            if batch_snapshot_ids:
                db.query(LecturerSourceSnapshot).filter(
                    LecturerSourceSnapshot.id.in_(batch_snapshot_ids)
                ).delete(synchronize_session=False)

            # D. Delete lecturers created only by this batch
            if to_delete_lecturer_ids:
                db.query(Lecturer).filter(
                    Lecturer.id.in_(to_delete_lecturer_ids)
                ).delete(synchronize_session=False)

            # E. Append-only: Record rollback audit event without deleting the original import audit
            filename = meta.get("filename", "ictu_lecturers.json")
            rollback_audit = AuditEvent(
                entity_type="lecturer_dataset",
                entity_id=audit.entity_id or audit.id,
                action="LECTURER_DATASET_ROLLED_BACK",
                actor_type="USER",
                actor_user_id=actor.id,
                actor_service=None,
                before_state=audit.after_state,
                after_state={"status": "ROLLED_BACK"},
                event_metadata={
                    "import_id": str(import_id),
                    "filename": filename,
                    "actor_user_id": str(actor.id),
                    "created_records_removed": created_removed_count,
                    "updated_records_restored": updated_restored_count,
                    "manual_records_preserved": manual_preserved_count,
                    "multi_source_records_preserved": multi_source_count,
                    "blocked_records": 0,
                    "rolled_back_at": now.isoformat(),
                },
            )
            db.add(rollback_audit)
            db.commit()

        except SQLAlchemyError as exc:
            db.rollback()
            raise LecturerRollbackError(
                "LECTURER_IMPORT_ROLLBACK_FAILED",
                "Không thể hoàn tất hoàn tác đợt nhập giảng viên do lỗi cơ sở dữ liệu.",
                status_code=500,
            ) from exc

        return LecturerRollbackSummary(
            import_id=import_id,
            filename=meta.get("filename", "ictu_lecturers.json"),
            actor_user_id=actor.id,
            created_records_removed=created_removed_count,
            updated_records_restored=updated_restored_count,
            manual_records_preserved=manual_preserved_count,
            multi_source_records_preserved=multi_source_count,
            blocked_records=0,
            rolled_back_at=now,
        )


__all__ = [
    "LecturerRollbackError",
    "LecturerRollbackService",
    "LecturerRollbackSummary",
]
