"""Preview (read-only) and import (transactional) for M2.5A §27-§35.

This module is the single authoritative writer for the lecturer dataset
import pipeline. It follows the same pattern as
``app.services.scopus_import_service`` but writes to the lecturer
master-data tables (``lecturers``, ``lecturer_source_snapshots``,
``lecturer_known_publications``). The only ``users`` rows it ever writes are the
login accounts carried by the dataset's optional ``account`` block, and only
when the e-mail is unused (existing accounts are never overwritten).

Identity resolution
-------------------
``source_id`` is the identity assigned by the *source* (for the ICTU
repository: the profile URL). It is distinct from ``lecturers.id`` (the
internal UUID) and is never replaced by it. A lecturer's verified source
identities are

* ``lecturers.repository_profile_url``, and
* the ``source_id`` / ``provenance.source_record_id`` recorded in the
  lecturer's own import snapshots for the same ``source_system``.

A record is matched to an existing lecturer in this order:

1. its ``source_id`` (so an e-mail / staff-code change is still recognised),
2. a non-null ``staff_code``,
3. a case-insensitive ``institutional_email``.

Name matching is never used to merge records: a same-name/same-department
candidate is only surfaced as a (non-blocking) warning.

Fail-closed rules — any of these is a *blocking* conflict, reported by the
preview and rejected by the import **before** anything is written:

* ``source_id`` resolves to lecturer A but the staff code or the (changed)
  e-mail already belongs to lecturer B;
* staff code resolves to A and e-mail to B;
* the matched lecturer is already bound to a different ``source_id``;
* a new ORCID / profile URL already belongs to another lecturer.

A lecturer that is absent from the file is never deleted or deactivated.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import UTC, date, datetime
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

MAX_CONFLICT_SAMPLES = 20


class LecturerDatasetError(RuntimeError):
    """Raised by the import pipeline on hard failure (rollback path)."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        conflicts: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.conflicts = conflicts or []


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
    blocking_conflicts: int = 0
    absent_from_file: int = 0


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
    blocking_conflicts: int = 0
    absent_from_file: int = 0


def _email_key(value: str | None) -> str:
    return (value or "").strip().lower()


def _staff_code_key(value: str | None) -> str | None:
    return value if value else None


def _name_department_key(full_name: str, department: str | None) -> tuple[str, str]:
    return (full_name.casefold().strip(), (department or "").casefold().strip())


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


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
        "specialization": record.get("specialization"),
        "gender": record.get("gender"),
        "date_of_birth": record.get("date_of_birth"),
        "phone": record.get("phone"),
        "profile_url": record.get("profile_url"),
        "is_active": record.get("is_active", True),
    }


def _current_fields(existing: Lecturer) -> dict:
    return {
        "full_name": existing.full_name,
        "staff_code": existing.staff_code,
        "institutional_email": (existing.email or "").lower(),
        "academic_degree": existing.academic_degree,
        "academic_rank": existing.academic_rank,
        "position": existing.position,
        "faculty": existing.faculty,
        "department": existing.department,
        "orcid": existing.orcid,
        "specialization": existing.specialization,
        "gender": existing.gender,
        "date_of_birth": existing.date_of_birth.isoformat() if existing.date_of_birth else None,
        "phone": existing.phone,
        "profile_url": existing.repository_profile_url,
        "is_active": existing.is_active,
    }


def _hash_payload(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


@dataclasses.dataclass
class _Index:
    """In-memory view of the existing lecturers used for identity resolution."""

    rows: dict[uuid.UUID, Lecturer]
    by_staff_code: dict[str, uuid.UUID]
    by_email: dict[str, list[uuid.UUID]]
    by_name_dept: dict[tuple[str, str], list[tuple[uuid.UUID, str]]]
    by_orcid: dict[str, uuid.UUID]
    by_profile_url: dict[str, set[uuid.UUID]]
    by_source_id: dict[str, set[uuid.UUID]]
    source_ids_of: dict[uuid.UUID, set[str]]
    snapshot_bound: set[uuid.UUID]
    users_by_email: dict[str, User] = dataclasses.field(default_factory=dict)
    users_by_lecturer: dict[uuid.UUID, User] = dataclasses.field(default_factory=dict)


def _build_index(db: Session, source_systems: set[str]) -> _Index:
    """Pre-index existing lecturers for O(1) lookups."""
    index = _Index({}, {}, {}, {}, {}, {}, {}, {}, set())
    for row in db.query(Lecturer).all():
        index.rows[row.id] = row
        if row.staff_code:
            index.by_staff_code.setdefault(row.staff_code, row.id)
        if row.email:
            index.by_email.setdefault(row.email.lower(), []).append(row.id)
        if row.orcid:
            index.by_orcid.setdefault(row.orcid, row.id)
        if row.repository_profile_url:
            index.by_profile_url.setdefault(row.repository_profile_url, set()).add(row.id)
            index.by_source_id.setdefault(row.repository_profile_url, set()).add(row.id)
            index.source_ids_of.setdefault(row.id, set()).add(row.repository_profile_url)
        key = (row.full_name.casefold().strip(), (row.department or "").casefold().strip())
        index.by_name_dept.setdefault(key, []).append((row.id, _email_key(row.email)))

    for user in db.query(User).all():
        index.users_by_email[user.email.lower()] = user
        if user.lecturer_id is not None:
            index.users_by_lecturer[user.lecturer_id] = user

    if source_systems:
        stmt = (
            select(
                LecturerSourceSnapshot.lecturer_id,
                LecturerSourceSnapshot.raw_payload["source_id"].as_string(),
                LecturerSourceSnapshot.raw_payload["provenance"]["source_record_id"].as_string(),
            )
            .where(
                LecturerSourceSnapshot.lecturer_id.is_not(None),
                LecturerSourceSnapshot.source_system.in_(sorted(source_systems)),
            )
            .distinct()
        )
        for lecturer_id, sid, record_id in db.execute(stmt).all():
            for value in (sid, record_id):
                if value:
                    index.by_source_id.setdefault(value, set()).add(lecturer_id)
                    index.source_ids_of.setdefault(lecturer_id, set()).add(value)
                    index.snapshot_bound.add(lecturer_id)
    return index


@dataclasses.dataclass
class _Decision:
    record: dict
    canonical: dict
    existing: Lecturer | None
    action: str  # create | update | unchanged | conflict
    blocking: list[dict]
    warnings: list[dict]
    account_action: str | None = None  # create | exists | skip (None: no account in file)


def _conflict(
    record: dict,
    matched_by: str,
    other: Lecturer | None,
    reason: str,
    *,
    blocking: bool,
    existing_id: uuid.UUID | None = None,
) -> dict:
    return {
        "record_full_name": record["full_name"],
        "matched_by": matched_by,
        "existing_id": str(other.id if other is not None else existing_id),
        "existing_full_name": other.full_name if other is not None else record["full_name"],
        "existing_email": other.email if other is not None else record.get("institutional_email"),
        "blocking": blocking,
        "reason": reason,
        "source_id": record.get("source_id"),
    }


def _resolve(index: _Index, record: dict, canonical: dict) -> tuple[Lecturer | None, list[dict]]:
    """Resolve a record to an existing lecturer or report blocking conflicts."""
    blocking: list[dict] = []
    sid = record.get("source_id")
    staff_code = canonical["staff_code"]
    email = canonical["institutional_email"]
    sc_id = index.by_staff_code.get(staff_code) if staff_code else None
    email_ids = index.by_email.get(email, []) if email else []

    def rows(lecturer_id: uuid.UUID) -> Lecturer | None:
        return index.rows.get(lecturer_id)

    # Ids not backed by a stored row are placeholders for earlier records of
    # the same file; matching one of them means the file repeats an identity.
    placeholders = [
        i for i in (sc_id, *email_ids, *(index.by_source_id.get(sid, set()) if sid else set()))
        if i is not None and i not in index.rows
    ]
    if placeholders:
        blocking.append(_conflict(
            record, "duplicate_in_file", None,
            "Định danh bị lặp giữa các bản ghi trong cùng tệp.", blocking=True,
            existing_id=placeholders[0],
        ))
        return None, blocking

    target: Lecturer | None = None
    sid_ids = index.by_source_id.get(sid, set()) if sid else set()
    if len(sid_ids) > 1:
        blocking.append(_conflict(
            record, "ambiguous_source_id", rows(sorted(sid_ids, key=str)[0]),
            "source_id đang gắn với nhiều hồ sơ giảng viên.", blocking=True,
        ))
        return None, blocking
    if sid_ids:
        target = index.rows[next(iter(sid_ids))]
        if sc_id is not None and sc_id != target.id:
            blocking.append(_conflict(
                record, "source_id_staff_code_conflict", rows(sc_id),
                "source_id thuộc hồ sơ này nhưng mã cán bộ thuộc hồ sơ khác.", blocking=True,
            ))
        if email_ids and target.id not in email_ids:
            blocking.append(_conflict(
                record, "source_id_email_conflict", rows(email_ids[0]),
                "source_id thuộc hồ sơ này nhưng email mới thuộc hồ sơ khác.", blocking=True,
            ))
    else:
        if sc_id is not None and email_ids and sc_id not in email_ids:
            blocking.append(_conflict(
                record, "staff_code_email_conflict", rows(sc_id),
                "Mã cán bộ và email trỏ tới hai hồ sơ khác nhau.", blocking=True,
            ))
        if sc_id is not None:
            target = index.rows[sc_id]
        elif email_ids:
            target = index.rows[email_ids[0]]
        if target is not None and sid:
            bound = index.source_ids_of.get(target.id, set())
            if bound and sid not in bound:
                blocking.append(_conflict(
                    record, "source_id_bound_elsewhere", target,
                    "Hồ sơ khớp đã gắn với một source_id khác.", blocking=True,
                ))

    target_id = target.id if target is not None else None
    orcid = canonical["orcid"]
    if orcid:
        holder = index.by_orcid.get(orcid)
        if holder is not None and holder != target_id:
            blocking.append(_conflict(
                record, "orcid_conflict", rows(holder),
                "ORCID đã thuộc hồ sơ giảng viên khác.", blocking=True,
            ))
    profile_url = canonical["profile_url"]
    if profile_url:
        holders = index.by_profile_url.get(profile_url, set()) - ({target_id} if target_id else set())
        if holders:
            blocking.append(_conflict(
                record, "profile_url_conflict", rows(sorted(holders, key=str)[0]),
                "profile_url đã thuộc hồ sơ giảng viên khác.", blocking=True,
            ))
    return target, blocking


def _account_warning(record: dict, holder: User, reason: str) -> dict:
    return {
        "record_full_name": record["full_name"],
        "matched_by": "account_email",
        "existing_id": str(holder.lecturer_id or holder.id),
        "existing_full_name": holder.display_name,
        "existing_email": holder.email,
        "blocking": False,
        "reason": reason,
        "source_id": record.get("source_id"),
    }


def _plan_account(
    index: _Index, record: dict, existing: Lecturer | None
) -> tuple[str | None, list[dict]]:
    """Decide what to do with the record's optional login account (never overwrites)."""
    account = record.get("account")
    if not account:
        return None, []
    holder = index.users_by_email.get(account["email"])
    if holder is not None:
        if existing is not None and holder.lecturer_id == existing.id:
            return "exists", []
        return "skip", [_account_warning(
            record, holder,
            f"Email tài khoản {account['email']} đã được dùng bởi tài khoản khác — "
            "không ghi đè; chỉnh sửa tài khoản trong trang Giảng viên.",
        )]
    if existing is not None:
        current = index.users_by_lecturer.get(existing.id)
        if current is not None:
            return "skip", [_account_warning(
                record, current,
                "Hồ sơ này đã có tài khoản khác — không tạo thêm tài khoản từ tệp.",
            )]
    return "create", []


def _plan(index: _Index, envelope: dict) -> list[_Decision]:
    """Decide create/update/unchanged/conflict for each record without writing."""
    decisions: list[_Decision] = []
    for record in envelope["lecturers"]:
        canonical = _canonical_fields(record)
        existing, blocking = _resolve(index, record, canonical)
        name_dept_key = _name_department_key(record["full_name"], record.get("department"))
        collision_id = _ambiguous_name_candidate(
            index.by_name_dept.get(name_dept_key, []),
            canonical["institutional_email"],
            current_id=existing.id if existing is not None else None,
        )
        warnings: list[dict] = []
        if name_dept_key[0] and collision_id is not None:
            warnings.append({
                "record_full_name": record["full_name"],
                "matched_by": "name_department",
                "existing_id": str(collision_id),
                "existing_full_name": existing.full_name if existing is not None else record["full_name"],
                "existing_email": existing.email if existing is not None else record.get("institutional_email"),
                "blocking": False,
                "reason": "Trùng họ tên và đơn vị — chỉ cảnh báo, không gộp hồ sơ.",
                "source_id": record.get("source_id"),
            })

        if blocking:
            action = "conflict"
        elif existing is None:
            action = "create"
            # Keep the index consistent so later records in the same file see it.
            placeholder = uuid.uuid4()
            if canonical["staff_code"]:
                index.by_staff_code[canonical["staff_code"]] = placeholder
            if canonical["institutional_email"]:
                index.by_email.setdefault(canonical["institutional_email"], []).append(placeholder)
            if canonical["orcid"]:
                index.by_orcid[canonical["orcid"]] = placeholder
            if canonical["profile_url"]:
                index.by_profile_url.setdefault(canonical["profile_url"], set()).add(placeholder)
            if record.get("source_id"):
                index.by_source_id.setdefault(record["source_id"], set()).add(placeholder)
            index.by_name_dept.setdefault(name_dept_key, []).append(
                (placeholder, canonical["institutional_email"])
            )
        else:
            action = "unchanged" if canonical == _current_fields(existing) else "update"
        account_action = None
        if not blocking:
            account_action, account_warnings = _plan_account(index, record, existing)
            warnings.extend(account_warnings)
        decisions.append(
            _Decision(record, canonical, existing, action, blocking, warnings, account_action)
        )
    return decisions


def _summarise(index: _Index, decisions: list[_Decision]) -> dict[str, Any]:
    counts = {"create": 0, "update": 0, "unchanged": 0}
    conflicts = blocking_conflicts = 0
    blocking_samples: list[dict] = []
    warning_samples: list[dict] = []
    matched: set[uuid.UUID] = set()
    for d in decisions:
        if d.action in counts:
            counts[d.action] += 1
        if d.existing is not None:
            matched.add(d.existing.id)
        if d.blocking:
            blocking_conflicts += 1
        if d.blocking or d.warnings:
            conflicts += 1
        blocking_samples.extend(d.blocking)
        warning_samples.extend(d.warnings)
    samples = (blocking_samples + warning_samples)[:MAX_CONFLICT_SAMPLES]
    return {
        **counts,
        "conflicts": conflicts,
        "blocking_conflicts": blocking_conflicts,
        "conflict_samples": samples,
        "blocking_samples": blocking_samples[:MAX_CONFLICT_SAMPLES],
        "absent_from_file": len(index.snapshot_bound - matched),
    }


def _source_systems(envelope: dict) -> set[str]:
    return {r["provenance"]["source_system"] for r in envelope["lecturers"]}


class LecturerPreviewService:
    """Compute the diff between an uploaded dataset and current DB state.

    The preview is read-only — it never mutates the database. Lecturers that
    exist in the database but not in the file are reported as
    ``absent_from_file`` and are never treated as deletions.
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
        index = _build_index(db, _source_systems(envelope))
        decisions = _plan(index, envelope)
        s = _summarise(index, decisions)
        return LecturerPreviewSummary(
            total=len(envelope["lecturers"]),
            valid=len(envelope["lecturers"]),
            create=s["create"],
            update=s["update"],
            unchanged=s["unchanged"],
            conflicts=s["conflicts"],
            conflict_samples=s["conflict_samples"],
            dataset=envelope["dataset"],
            filename=filename,
            parser_version=envelope["dataset"].get("parser_version") or "unknown",
            blocking_conflicts=s["blocking_conflicts"],
            absent_from_file=s["absent_from_file"],
        )


def _dataset_provenance(dataset: dict) -> dict:
    keys = ("name", "institution", "source", "source_url", "source_system",
            "generated_at", "parser_version")
    return {k: dataset.get(k) for k in keys if dataset.get(k) is not None}


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
        index = _build_index(db, _source_systems(envelope))
        decisions = _plan(index, envelope)
        summary = _summarise(index, decisions)
        if summary["blocking_conflicts"]:
            # Fail closed: nothing has been written yet.
            raise LecturerDatasetError(
                "LECTURER_IDENTITY_CONFLICT",
                "Tệp chứa định danh mâu thuẫn (source_id / email / mã cán bộ / ORCID); "
                "không có dữ liệu nào được ghi.",
                status_code=409,
                conflicts=summary["blocking_samples"],
            )

        now = datetime.now(UTC)
        created = updated = unchanged = 0
        created_snapshot_ids: list[str] = []
        created_lecturer_ids: list[str] = []
        created_user_ids: list[str] = []
        dataset_provenance = _dataset_provenance(envelope["dataset"])

        try:
            for decision in decisions:
                record = decision.record
                canonical = decision.canonical
                existing = decision.existing
                provenance = record["provenance"]
                source_url = provenance["source_urls"][0] if provenance["source_urls"] else "unknown"
                email = canonical["institutional_email"] or None
                if decision.action == "create":
                    lecturer = Lecturer(
                        id=uuid.uuid4(),
                        staff_code=canonical["staff_code"],
                        full_name=canonical["full_name"],
                        full_name_normalized=record["full_name_normalized"],
                        email=email,
                        academic_degree=canonical["academic_degree"],
                        academic_rank=canonical["academic_rank"],
                        position=canonical["position"],
                        faculty=canonical["faculty"],
                        department=canonical["department"],
                        specialization=canonical.get("specialization"),
                        gender=canonical.get("gender"),
                        date_of_birth=_parse_date(canonical.get("date_of_birth")),
                        phone=canonical.get("phone"),
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
                    created += 1
                    lecturer_id = lecturer.id
                elif decision.action == "unchanged":
                    unchanged += 1
                    lecturer_id = existing.id
                else:
                    existing.full_name = canonical["full_name"]
                    existing.full_name_normalized = record["full_name_normalized"]
                    existing.staff_code = canonical["staff_code"]
                    existing.email = email
                    existing.academic_degree = canonical["academic_degree"]
                    existing.academic_rank = canonical["academic_rank"]
                    existing.position = canonical["position"]
                    existing.faculty = canonical["faculty"]
                    existing.department = canonical["department"]
                    existing.specialization = canonical.get("specialization")
                    existing.gender = canonical.get("gender")
                    existing.date_of_birth = _parse_date(canonical.get("date_of_birth"))
                    existing.phone = canonical.get("phone")
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

                # Per-record snapshot (append-only). It records the *source*
                # identity (``source_id``) next to the canonical fields.
                snapshot = LecturerSourceSnapshot(
                    id=uuid.uuid4(),
                    lecturer_id=lecturer_id,
                    source_system=provenance["source_system"],
                    source_url=source_url,
                    snapshot_hash=_hash_payload(canonical),
                    raw_payload={
                        "canonical": canonical,
                        "provenance": provenance,
                        "source_id": record.get("source_id"),
                        "dataset": dataset_provenance,
                    },
                    parser_version=envelope["dataset"].get("parser_version") or "unknown",
                    validation_status="VALID",
                    validation_errors=[],
                    fetched_at=now,
                    created_at=now,
                )
                db.add(snapshot)
                db.flush()
                created_snapshot_ids.append(str(snapshot.id))

                if decision.account_action == "create":
                    account = record["account"]
                    user = User(
                        id=uuid.uuid4(),
                        email=account["email"],
                        password_hash=account["password_hash"],
                        display_name=account["display_name"],
                        role=account["role"],
                        lecturer_id=lecturer_id,
                        is_active=account["is_active"],
                        version=1,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(user)
                    db.flush()
                    created_user_ids.append(str(user.id))

                pubs = record.get("known_publications") or []
                if pubs:
                    known = _known_publication_keys(db, lecturer_id)
                    for pub in pubs:
                        key = _publication_key(pub)
                        if key in known:
                            continue
                        known.add(key)
                        db.add(LecturerKnownPublication(
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
                        ))

            conflicts = summary["conflicts"]
            # Audit the entire batch in a single event.
            audit_metadata: dict[str, Any] = {
                "dataset_name": envelope["dataset"].get("name"),
                "dataset_schema_version": envelope["dataset"].get("schema_version"),
                "filename": filename,
                "file_sha256": hashlib.sha256(content).hexdigest(),
                "record_count": len(envelope["lecturers"]),
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "conflicts": conflicts,
                "warnings": conflicts,
                "absent_from_file": summary["absent_from_file"],
                "snapshot_ids": created_snapshot_ids,
                "created_lecturer_ids": created_lecturer_ids,
                "accounts_created": len(created_user_ids),
                "created_user_ids": created_user_ids,
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
            conflicts=summary["conflicts"],
            conflict_samples=summary["conflict_samples"],
            snapshot_ids=created_snapshot_ids,
            dataset=envelope["dataset"],
            filename=filename,
            parser_version=envelope["dataset"].get("parser_version") or "unknown",
            blocking_conflicts=0,
            absent_from_file=summary["absent_from_file"],
        )


def _publication_key(pub: dict) -> tuple[str, str, int | None]:
    return (
        pub.get("title_normalized") or "",
        pub.get("doi_normalized") or "",
        pub.get("published_year"),
    )


def _known_publication_keys(db: Session, lecturer_id: uuid.UUID) -> set[tuple[str, str, int | None]]:
    """Known publications already stored for the lecturer (avoids re-import duplicates)."""
    stmt = select(
        LecturerKnownPublication.title_normalized,
        LecturerKnownPublication.doi_normalized,
        LecturerKnownPublication.published_year,
    ).where(LecturerKnownPublication.lecturer_id == lecturer_id)
    return {(t or "", d or "", y) for t, d, y in db.execute(stmt).all()}


__all__ = [
    "LecturerDatasetError",
    "LecturerImportService",
    "LecturerImportSummary",
    "LecturerPreviewService",
    "LecturerPreviewSummary",
]
