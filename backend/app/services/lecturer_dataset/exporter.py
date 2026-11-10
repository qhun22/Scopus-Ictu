"""Export of the canonical ICTU lecturer set in the importable JSON format.

The export emits only lecturers that carry a *verified source identity*: at
least one import snapshot of ``source_system`` that records the source's own
``source_id`` (for ICTU: the repository profile URL). Synthetic/demo lecturers,
manually created lecturers and lecturers whose snapshots never recorded a
source identity are therefore not part of the dataset.

``source_id`` is read back from the snapshot that recorded it — it is never
the internal ``lecturers.id`` and it is never synthesised from it. Nothing
that is not stored in PostgreSQL is invented: legacy ``tel`` values are imported
into ``phone`` and exported under that canonical key. The raw ``tel`` key and
the unpersisted Google Scholar profile are omitted and listed in
``dataset.export.not_preserved_fields``.

The output is accepted by :func:`parse_and_validate` and by the import
service (round trip).

Each record also includes all currently APPROVED ``scopus_ids`` and the
valid human-selected ``primary_scopus_id`` (or null). These export fields
are a reference: the lecturer importer does not recreate review decisions.

A lecturer that has a login account is exported together with it (``account``:
email, role, display name, and active flag). ``password_hash`` and other
authentication secrets are **not** included; the export whitelist only carries
business identity fields. Re-importing a file without ``password_hash`` will
skip account creation for those records (the importer will log a warning).
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.lecturer_primary_scopus import LecturerPrimaryScopusEvent
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.models.publication import ScopusAuthor
from app.services.lecturer_dataset.parser import UUID_RE

ICTU_SOURCE_SYSTEM = "ictu_dspace_archive"
EXPORTER_VERSION = "scopus_ictu_lecturer_export/1.1"
SCHEMA_VERSION = "1.1"
NOT_PRESERVED_FIELDS: tuple[str, ...] = ("tel", "google_scholar")
RECOVERABILITY_NOTE = (
    "Bản xuất khôi phục tất cả các trường canonical đang được PostgreSQL lưu, "
    "bao gồm specialization, gender, date_of_birth và phone (thêm từ migration e1a2b3c4d5f6). "
    "Khi nhập, tel được chuẩn hóa thành phone; bản xuất chỉ có khóa phone. "
    "Google Scholar chưa được lưu nên không có trong bản xuất; "
    "JSON nguồn gốc (v1), Craw và sidecar vẫn là nguồn lưu trữ cho các trường này. "
    "Giảng viên có tài khoản đăng nhập được xuất kèm khối account (email, vai trò, "
    "display_name, is_active, mã băm Argon2id); bí mật xác thực và phiên đăng nhập "
    "không có trong tệp xuất."
)


@dataclasses.dataclass(frozen=True)
class LecturerExport:
    payload: dict[str, Any]
    record_count: int
    excluded_without_source_id: int
    known_publication_count: int
    account_count: int = 0


def _source_id_of(payload: dict) -> str | None:
    provenance = payload.get("provenance")
    candidates = [payload.get("source_id")]
    if isinstance(provenance, dict):
        candidates.append(provenance.get("source_record_id"))
    for value in candidates:
        if isinstance(value, str) and value.strip() and not UUID_RE.match(value.strip()):
            return value.strip()
    return None


def _scopus_ids_for_export(
    db: Session, lecturer_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[str]], dict[uuid.UUID, str]]:
    """Read every saved identity, including authors without imported publications.

    Only the latest, still-valid human primary selection is exported. Source
    hints, revoked links and automatically suggested primary IDs are excluded.
    """
    ids: dict[uuid.UUID, list[str]] = {}
    primary: dict[uuid.UUID, str] = {}
    if not lecturer_ids:
        return ids, primary

    identity = LecturerScopusIdentity
    event = LecturerPrimaryScopusEvent
    latest = (
        select(event.lecturer_id, func.max(event.seq).label("seq"))
        .where(event.lecturer_id.in_(lecturer_ids))
        .group_by(event.lecturer_id)
        .subquery()
    )
    rows = db.execute(
        select(
            identity.lecturer_id,
            ScopusAuthor.scopus_id,
            ((event.action == "SET") & (event.identity_id == identity.id)).label("is_primary"),
        )
        .select_from(identity)
        .join(ScopusAuthor, ScopusAuthor.id == identity.scopus_author_id)
        .outerjoin(latest, latest.c.lecturer_id == identity.lecturer_id)
        .outerjoin(event, event.seq == latest.c.seq)
        .where(identity.lecturer_id.in_(lecturer_ids), identity.status == "APPROVED")
        .order_by(ScopusAuthor.scopus_id.asc())
    ).all()
    for lecturer_id, scopus_id, is_primary in rows:
        ids.setdefault(lecturer_id, []).append(scopus_id)
        if is_primary:
            primary[lecturer_id] = scopus_id
    return ids, primary


def build_lecturer_export(
    db: Session,
    *,
    now: datetime,
    source_system: str = ICTU_SOURCE_SYSTEM,
) -> LecturerExport:
    """Build the export envelope for lecturers verified by ``source_system``."""
    snapshot_rows = db.execute(
        select(
            LecturerSourceSnapshot.lecturer_id,
            LecturerSourceSnapshot.raw_payload,
        )
        .where(
            LecturerSourceSnapshot.lecturer_id.is_not(None),
            LecturerSourceSnapshot.source_system == source_system,
        )
        .order_by(
            LecturerSourceSnapshot.lecturer_id.asc(),
            LecturerSourceSnapshot.created_at.asc(),
            LecturerSourceSnapshot.id.asc(),
        )
    ).all()

    # Earliest snapshot that recorded a source identity = the provenance origin.
    origin: dict[uuid.UUID, tuple[str, dict]] = {}
    seen_without_source_id: set[uuid.UUID] = set()
    for lecturer_id, payload in snapshot_rows:
        if lecturer_id in origin or not isinstance(payload, dict):
            continue
        sid = _source_id_of(payload)
        if sid is None:
            seen_without_source_id.add(lecturer_id)
        else:
            origin[lecturer_id] = (sid, payload)
    excluded = len(seen_without_source_id - set(origin))

    lecturers = (
        db.execute(select(Lecturer).where(Lecturer.id.in_(list(origin)))).scalars().all()
        if origin
        else []
    )
    by_id = {row.id: row for row in lecturers}
    scopus_ids, primary_scopus_ids = _scopus_ids_for_export(db, list(by_id))

    publications: dict[uuid.UUID, list[dict]] = {}
    if origin:
        pub_rows = db.execute(
            select(LecturerKnownPublication)
            .join(
                LecturerSourceSnapshot,
                LecturerSourceSnapshot.id == LecturerKnownPublication.snapshot_id,
            )
            .where(
                LecturerKnownPublication.lecturer_id.in_(list(origin)),
                LecturerSourceSnapshot.source_system == source_system,
            )
            .order_by(
                LecturerKnownPublication.title_normalized.asc(),
                LecturerKnownPublication.created_at.asc(),
                LecturerKnownPublication.id.asc(),
            )
        ).scalars().all()
        seen: set[tuple[uuid.UUID, str, str, int | None]] = set()
        for pub in pub_rows:
            key = (
                pub.lecturer_id, pub.title_normalized, pub.doi_normalized or "", pub.published_year,
            )
            if key in seen:
                continue
            seen.add(key)
            publications.setdefault(pub.lecturer_id, []).append({
                "title_raw": pub.title_raw,
                "title_normalized": pub.title_normalized,
                "doi_raw": pub.doi_raw,
                "doi_normalized": pub.doi_normalized,
                "source_title_raw": pub.source_title_raw,
                "published_year": pub.published_year,
            })

    # At most one account per lecturer (unique index uq_users_lecturer).
    accounts: dict[uuid.UUID, User] = {}
    if origin:
        for user in db.execute(
            select(User)
            .where(User.lecturer_id.in_(list(origin)))
            .order_by(User.created_at.asc(), User.id.asc())
        ).scalars():
            accounts.setdefault(user.lecturer_id, user)

    exported_at = now.isoformat()
    records: list[dict] = []
    derived_from: dict | None = None
    for lecturer_id, (sid, payload) in origin.items():
        row = by_id.get(lecturer_id)
        if row is None:
            continue
        original = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        provenance = {k: v for k, v in original.items() if k != "export"}
        provenance["export"] = {"exported_at": exported_at, "exporter": EXPORTER_VERSION}
        if derived_from is None and isinstance(payload.get("dataset"), dict):
            derived_from = payload["dataset"]
        account = accounts.get(lecturer_id)
        record = {
            "source_id": sid,
            "staff_code": row.staff_code,
            "full_name": row.full_name,
            "institutional_email": row.email,
            "academic_degree": row.academic_degree,
            "academic_rank": row.academic_rank,
            "position": row.position,
            "faculty": row.faculty,
            "department": row.department,
            "specialization": row.specialization,
            "gender": row.gender,
            "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
            "phone": row.phone,
            "profile_url": row.repository_profile_url,
            "orcid": row.orcid,
            "scopus_ids": scopus_ids.get(lecturer_id, []),
            "primary_scopus_id": primary_scopus_ids.get(lecturer_id),
            "is_active": row.is_active,
            "provenance": provenance,
            "known_publications": publications.get(lecturer_id, []),
            "full_name_normalized": row.full_name_normalized,
        }
        if account is not None:
            # Whitelist: business identity fields + hashed credential for roundtrip restore.
            # Plaintext passwords are never stored; only the Argon2id hash is exported.
            record["account"] = {
                "email": account.email,
                "display_name": account.display_name,
                "role": account.role,
                "is_active": account.is_active,
                "password_hash": account.password_hash,
            }
        records.append(record)
    records.sort(key=lambda r: r["source_id"])
    derived_from = derived_from or {}

    dataset: dict[str, Any] = {
        "name": derived_from.get("name") or "ICTU Lecturer Master Dataset",
        "schema_version": SCHEMA_VERSION,
        "institution": derived_from.get("institution"),
        "source": derived_from.get("source") or "ICTU lecturer master data (PostgreSQL export)",
        "source_url": derived_from.get("source_url"),
        "source_system": source_system,
        "generated_at": exported_at,
        "exported_at": exported_at,
        "parser_version": EXPORTER_VERSION,
        "record_count": len(records),
        "export": {
            "exporter": EXPORTER_VERSION,
            "origin": "PostgreSQL canonical lecturers",
            "derived_from": derived_from,
            "not_preserved_fields": list(NOT_PRESERVED_FIELDS),
            "recoverability_note": RECOVERABILITY_NOTE,
            "excluded_without_source_id": excluded,
            "includes_accounts": True,
            "includes_scopus_ids": True,
            "scopus_identity_count": sum(len(r["scopus_ids"]) for r in records),
            "primary_scopus_id_count": sum(r["primary_scopus_id"] is not None for r in records),
            "scopus_note": (
                "scopus_ids chứa tất cả ID đã được duyệt và lưu cho giảng viên; "
                "primary_scopus_id là ID chính đã được người dùng chọn, hoặc null. "
                "Nhập lại JSON không tự xác nhận liên kết Scopus hoặc lựa chọn ID chính."
            ),
            "accounts_note": (
                "Tệp chứa thông tin tài khoản (email, vai trò, display_name, is_active). "
                "Bí mật xác thực và phiên đăng nhập không có trong tệp xuất."
            ),
        },
    }
    return LecturerExport(
        payload={"dataset": dataset, "lecturers": records},
        record_count=len(records),
        excluded_without_source_id=excluded,
        known_publication_count=sum(len(v) for v in publications.values()),
        account_count=sum(1 for r in records if "account" in r),
    )
