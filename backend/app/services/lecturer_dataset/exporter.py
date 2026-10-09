"""Export of the canonical ICTU lecturer set in the importable JSON format.

The export emits only lecturers that carry a *verified source identity*: at
least one import snapshot of ``source_system`` that records the source's own
``source_id`` (for ICTU: the repository profile URL). Synthetic/demo lecturers,
manually created lecturers and lecturers whose snapshots never recorded a
source identity are therefore not part of the dataset.

``source_id`` is read back from the snapshot that recorded it — it is never
the internal ``lecturers.id`` and it is never synthesised from it. Nothing
that is not stored in PostgreSQL is invented: ``tel`` and the Google Scholar
profile are not persisted, so they are omitted and listed in
``dataset.export.not_preserved_fields``.

The output is accepted by :func:`parse_and_validate` and by the import
service (round trip). Users/accounts/credentials are never read here.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)
from app.services.lecturer_dataset.parser import UUID_RE

ICTU_SOURCE_SYSTEM = "ictu_dspace_archive"
EXPORTER_VERSION = "scopus_ictu_lecturer_export/1.0"
SCHEMA_VERSION = "1.0"
NOT_PRESERVED_FIELDS: tuple[str, ...] = ("tel", "google_scholar")
RECOVERABILITY_NOTE = (
    "Bản xuất chỉ khôi phục các trường canonical đang được PostgreSQL lưu. "
    "Các trường tel và Google Scholar chưa được lưu nên không có trong bản xuất; "
    "JSON nguồn gốc (v1), Craw và sidecar vẫn là nguồn lưu trữ cho các trường này."
)


@dataclasses.dataclass(frozen=True)
class LecturerExport:
    payload: dict[str, Any]
    record_count: int
    excluded_without_source_id: int
    known_publication_count: int


def _source_id_of(payload: dict) -> str | None:
    provenance = payload.get("provenance")
    candidates = [payload.get("source_id")]
    if isinstance(provenance, dict):
        candidates.append(provenance.get("source_record_id"))
    for value in candidates:
        if isinstance(value, str) and value.strip() and not UUID_RE.match(value.strip()):
            return value.strip()
    return None


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
            key = (pub.lecturer_id, pub.title_normalized, pub.doi_normalized or "", pub.published_year)
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
        records.append({
            "source_id": sid,
            "staff_code": row.staff_code,
            "full_name": row.full_name,
            "institutional_email": row.email,
            "academic_degree": row.academic_degree,
            "academic_rank": row.academic_rank,
            "position": row.position,
            "faculty": row.faculty,
            "department": row.department,
            "profile_url": row.repository_profile_url,
            "orcid": row.orcid,
            "is_active": row.is_active,
            "provenance": provenance,
            "known_publications": publications.get(lecturer_id, []),
            "full_name_normalized": row.full_name_normalized,
        })
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
        },
    }
    return LecturerExport(
        payload={"dataset": dataset, "lecturers": records},
        record_count=len(records),
        excluded_without_source_id=excluded,
        known_publication_count=sum(len(v) for v in publications.values()),
    )
