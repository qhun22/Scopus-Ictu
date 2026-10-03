"""Dataset payload parser — runtime JSON ingest for M2.5A §25 / §29.

This module lives in the runtime layer (``app/services``) instead of
``scripts/`` because the preview/import endpoints need to parse and
validate uploads without depending on the dataset builder. The
builder itself remains the canonical producer of ``ictu_lecturers.json``;
this parser is intentionally minimal — it enforces only the
invariants that the API contract requires before any database action.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

ALLOWED_DEGREES: frozenset[str | None] = frozenset({
    "TS", "ThS", "KS", "CN", "DH", "ĐH", "BS", "PGS", "GS",
    "Tiến sĩ", "Thạc sĩ", "Kỹ sư", "Cử nhân", "Đại học", None,
})
ALLOWED_RANKS: frozenset[str | None] = frozenset({
    "PGS", "GS", "Phó giáo sư", "Giáo sư", None,
})
ALLOWED_DATASET_SCHEMA_MAJOR: int = 1
MAX_FILE_BYTES: int = 20 * 1024 * 1024  # mirrors scopus_import_max_bytes cap
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
ORCID_RE = re.compile(r"^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$")
STAFF_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

ACADEMIC_DEGREE_VALUES: tuple[str, ...] = ("TS", "ThS", "KS", "CN", "PGS", "GS")


class DatasetValidationError(ValueError):
    """Raised when the uploaded payload fails project invariants.

    The endpoint maps this to a 422 response with a stable error code.
    """

    def __init__(self, code: str, message: str, *, location: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.location = location


def _require(cond: bool, code: str, message: str, *, location: str = "") -> None:
    if not cond:
        raise DatasetValidationError(code, message, location=location)


def normalise_full_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def hash_payload(payload: dict | list | bytes) -> str:
    if isinstance(payload, (dict, list)):
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    else:
        body = payload
    return hashlib.sha256(body).hexdigest()


def parse_and_validate(raw_bytes: bytes, *, filename: str | None = None) -> dict:
    """Decode and validate an uploaded lecturer dataset.

    Returns the normalised dataset envelope (a dict with ``dataset``
    metadata and a ``lecturers`` list of normalised records).
    """
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise DatasetValidationError(
            "IMPORT_FILE_TOO_LARGE",
            f"Tệp vượt quá dung lượng cho phép ({MAX_FILE_BYTES} bytes).",
        )
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(
            "INVALID_LECTURER_DATASET",
            "Tệp JSON không hợp lệ. Vui lòng kiểm tra định dạng tệp.",
        ) from exc
    if not isinstance(data, dict):
        raise DatasetValidationError(
            "INVALID_LECTURER_DATASET",
            "Tệp JSON phải có cấu trúc đối tượng ở cấp cao nhất.",
        )

    dataset = data.get("dataset")
    _require(isinstance(dataset, dict), "INVALID_LECTURER_DATASET",
             "Thiếu khóa 'dataset' trong tệp.", location="dataset")
    schema_version = str(dataset.get("schema_version", ""))
    major_str = schema_version.split(".", 1)[0] if schema_version else ""
    _require(
        schema_version and (schema_version == "1.0" or major_str.isdigit()
                            and int(major_str) == ALLOWED_DATASET_SCHEMA_MAJOR),
        "UNSUPPORTED_DATASET_SCHEMA",
        f"Phiên bản lược đồ {schema_version!r} không được hỗ trợ. "
        f"Yêu cầu '{ALLOWED_DATASET_SCHEMA_MAJOR}.x'.",
        location="dataset.schema_version",
    )
    _require(
        isinstance(dataset.get("record_count"), int) and dataset["record_count"] >= 0,
        "INVALID_LECTURER_DATASET",
        "'dataset.record_count' phải là số nguyên không âm.",
        location="dataset.record_count",
    )

    raw_lecturers = data.get("lecturers")
    _require(isinstance(raw_lecturers, list), "INVALID_LECTURER_DATASET",
             "'lecturers' phải là một danh sách.", location="lecturers")
    _require(len(raw_lecturers) >= 1, "INVALID_LECTURER_DATASET",
             "'lecturers' không được rỗng.", location="lecturers")
    _require(
        dataset["record_count"] == len(raw_lecturers),
        "INVALID_LECTURER_DATASET",
        "dataset.record_count không khớp với số bản ghi thực tế.",
        location="dataset.record_count",
    )

    records: list[dict] = []
    seen_emails: dict[str, int] = {}
    seen_staff_codes: dict[str, int] = {}
    for idx, rec in enumerate(raw_lecturers):
        location = f"lecturers[{idx}]"
        _require(isinstance(rec, dict), "INVALID_LECTURER_DATASET",
                 f"{location} phải là một đối tượng.", location=location)
        full_name = normalise_full_name(str(rec.get("full_name") or ""))
        _require(full_name, "INVALID_LECTURER_DATASET",
                 f"{location}.full_name là bắt buộc.", location=f"{location}.full_name")
        faculty = (str(rec.get("faculty") or "").strip()) or None
        department = (str(rec.get("department") or "").strip()) or None
        # faculty/department are *advisory* in the canonical dataset — the
        # M1 ``lecturers`` table allows them to be NULL when the upstream
        # source does not publish them (M2.5A §9 — completeness rule). The
        # previous build emitted empty strings which was misleading; we now
        # coerce missing values to None.

        email = rec.get("institutional_email")
        if email is not None:
            email = str(email).strip().lower() or None
            if email is not None:
                _require(EMAIL_RE.match(email), "INVALID_LECTURER_DATASET",
                         f"{location}.institutional_email không hợp lệ ({email!r}).",
                         location=f"{location}.institutional_email")
                if email in seen_emails:
                    raise DatasetValidationError(
                        "DUPLICATE_LECTURER_IDENTITY",
                        f"Email {email!r} bị trùng giữa các bản ghi.",
                        location=location,
                    )
                seen_emails[email] = idx

        staff_code = rec.get("staff_code")
        if staff_code is not None:
            staff_code = str(staff_code).strip() or None
            if staff_code is not None:
                _require(STAFF_CODE_RE.match(staff_code), "INVALID_LECTURER_DATASET",
                         f"{location}.staff_code phải là chuỗi chữ/số/gạch dưới.",
                         location=f"{location}.staff_code")
                if staff_code in seen_staff_codes:
                    raise DatasetValidationError(
                        "DUPLICATE_LECTURER_IDENTITY",
                        f"Mã cán bộ {staff_code!r} bị trùng giữa các bản ghi.",
                        location=location,
                    )
                seen_staff_codes[staff_code] = idx

        degree = rec.get("academic_degree")
        rank = rec.get("academic_rank")
        _require(degree in ALLOWED_DEGREES, "INVALID_LECTURER_DATASET",
                 f"{location}.academic_degree={degree!r} không hợp lệ.",
                 location=f"{location}.academic_degree")
        _require(rank in ALLOWED_RANKS, "INVALID_LECTURER_DATASET",
                 f"{location}.academic_rank={rank!r} không hợp lệ.",
                 location=f"{location}.academic_rank")

        orcid = rec.get("orcid")
        if orcid is not None:
            orcid = str(orcid).strip() or None
            if orcid is not None and not ORCID_RE.match(orcid):
                raise DatasetValidationError(
                    "INVALID_LECTURER_DATASET",
                    f"{location}.orcid không đúng định dạng.",
                    location=f"{location}.orcid",
                )

        known_pubs = rec.get("known_publications") or []
        _require(isinstance(known_pubs, list), "INVALID_LECTURER_DATASET",
                 f"{location}.known_publications phải là một danh sách.",
                 location=f"{location}.known_publications")
        normalised_pubs: list[dict] = []
        for j, pub in enumerate(known_pubs):
            _require(isinstance(pub, dict), "INVALID_LECTURER_DATASET",
                     f"{location}.known_publications[{j}] phải là đối tượng.",
                     location=f"{location}.known_publications[{j}]")
            title = str(pub.get("title_raw") or "").strip()
            _require(title, "INVALID_LECTURER_DATASET",
                     f"{location}.known_publications[{j}].title_raw là bắt buộc.",
                     location=f"{location}.known_publications[{j}]")
            normalised_pubs.append({
                "title_raw": title,
                "title_normalized": normalise_full_name(pub.get("title_normalized") or title),
                "doi_raw": pub.get("doi_raw"),
                "doi_normalized": pub.get("doi_normalized"),
                "source_title_raw": pub.get("source_title_raw"),
                "published_year": pub.get("published_year"),
            })

        provenance = rec.get("provenance") or {}
        if not isinstance(provenance, dict):
            raise DatasetValidationError(
                "INVALID_LECTURER_DATASET",
                f"{location}.provenance phải là đối tượng.",
                location=f"{location}.provenance",
            )
        source_urls = provenance.get("source_urls") or []
        _require(isinstance(source_urls, list) and source_urls,
                 "INVALID_LECTURER_DATASET",
                 f"{location}.provenance.source_urls phải là danh sách không rỗng.",
                 location=f"{location}.provenance.source_urls")

        records.append({
            "source_id": rec.get("source_id"),
            "staff_code": staff_code,
            "full_name": full_name,
            "full_name_normalized": full_name.casefold(),
            "institutional_email": email,
            "tel": rec.get("tel"),
            "academic_degree": degree,
            "academic_rank": rank,
            "position": rec.get("position"),
            "faculty": faculty,
            "department": department,
            "profile_url": rec.get("profile_url"),
            "orcid": orcid,
            "is_active": bool(rec.get("is_active", True)),
            "provenance": {
                "source_name": str(provenance.get("source_name") or "unknown"),
                "source_system": str(provenance.get("source_system") or "unknown"),
                "source_urls": list(source_urls),
                "source_record_id": provenance.get("source_record_id"),
                "retrieved_at": provenance.get("retrieved_at"),
            },
            "known_publications": normalised_pubs,
        })

    return {
        "dataset": {
            "name": dataset.get("name"),
            "schema_version": schema_version,
            "institution": dataset.get("institution"),
            "source": dataset.get("source"),
            "source_url": dataset.get("source_url"),
            "source_system": dataset.get("source_system"),
            "generated_at": dataset.get("generated_at"),
            "parser_version": dataset.get("parser_version"),
            "record_count": len(records),
        },
        "lecturers": records,
    }


def iter_lecturers(envelope: dict) -> Iterable[dict]:
    yield from envelope["lecturers"]
