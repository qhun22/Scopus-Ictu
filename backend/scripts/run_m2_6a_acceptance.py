"""Run the M2.6A acceptance checks against the configured local PostgreSQL DB.

This intentionally uses the real import service and an explicitly supplied
local CSV. It does not delete canonical or raw data after the run because the
resulting rows are the requested local acceptance/provenance dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import app.models  # noqa: F401 - register the complete metadata
from app.core.config import settings
from app.core.database import get_session_factory
from app.core.exceptions import APIError
from app.models.governance import User
from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_normalizer import normalize_import
from app.services.scopus_import_service import (
    create_import_job,
    delete_scopus_import,
    process_import_job,
)

ACCEPTANCE_EMAIL = "m2.6a-acceptance@local.invalid"


def _counts(db) -> dict[str, int]:
    return {
        "publications": db.query(Publication).count(),
        "publication_raw_sources": db.query(PublicationRawSource).count(),
        "raw_eligible": db.query(RawScopusRecord)
        .filter(RawScopusRecord.validation_status == "VALID")
        .count(),
    }


def _admin(db) -> User:
    user = db.query(User).filter(User.email == ACCEPTANCE_EMAIL).first()
    if user is not None:
        return user
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=ACCEPTANCE_EMAIL,
        password_hash="acceptance-only-not-a-login-secret",
        display_name="M2.6A Acceptance",
        role="ADMIN",
        lecturer_id=None,
        is_active=True,
        version=1,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    return user


def _summary(db, import_id: uuid.UUID) -> dict:
    db.expire_all()
    item = db.query(ScopusImport).filter(ScopusImport.id == import_id).one()
    return dict(item.normalization_summary or {})


def main() -> None:
    if settings.environment.lower() == "prod":
        raise SystemExit("Refusing acceptance execution in ENVIRONMENT=prod.")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.dataset.expanduser()
    if not dataset.is_file():
        raise SystemExit(f"Dataset file not found: {dataset}")

    content = dataset.read_bytes()
    factory = get_session_factory()
    with factory() as db:
        admin = _admin(db)
        before = _counts(db)

        first = create_import_job(
            db,
            filename=dataset.name,
            content=content,
            actor=admin,
            allow_duplicate=True,
        )
        process_import_job(first.id, content, admin.id)
        first_summary = _summary(db, first.id)
        after_first = _counts(db)

        rerun_counters = normalize_import(db, first.id).to_dict()
        after_rerun = _counts(db)

        duplicate = create_import_job(
            db,
            filename=dataset.name,
            content=content,
            actor=admin,
            allow_duplicate=True,
        )
        process_import_job(duplicate.id, content, admin.id)
        duplicate_summary = _summary(db, duplicate.id)
        after_duplicate = _counts(db)

        canonical = db.query(Publication).order_by(Publication.created_at).first()
        if canonical is None:
            raise RuntimeError("Acceptance import produced no canonical publication")
        original_title = canonical.title
        now = datetime.now(UTC)
        metadata_import = ScopusImport(
            id=uuid.uuid4(),
            file_name="m2_6a_metadata_change.csv",
            file_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            total_records=1,
            valid_records=1,
            invalid_records=0,
            status="STAGED",
            error_summary=None,
            normalization_summary=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        metadata_raw = RawScopusRecord(
            id=uuid.uuid4(),
            import_id=metadata_import.id,
            row_number=1,
            row_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            eid_raw=canonical.eid,
            doi_raw=canonical.doi,
            raw_payload={"Title": f"{original_title} [changed acceptance title]"},
            validation_status="VALID",
            validation_errors=None,
            created_at=now,
        )
        db.add(metadata_import)
        db.flush()
        db.add(metadata_raw)
        db.commit()
        metadata_counters = normalize_import(db, metadata_import.id).to_dict()
        db.expire_all()
        unchanged_title = (
            db.query(Publication).filter(Publication.id == canonical.id).one().title
            == original_title
        )
        metadata_linked = (
            db.query(PublicationRawSource)
            .filter(PublicationRawSource.raw_record_id == metadata_raw.id)
            .count()
            == 1
        )

        delete_check: dict[str, object]
        try:
            delete_scopus_import(db, first.id, admin)
            delete_check = {"blocked": False, "code": None, "status_code": None}
        except APIError as exc:
            db.rollback()
            delete_check = {
                "blocked": True,
                "code": exc.code,
                "status_code": exc.status_code,
            }

        report = {
            "dataset": dataset.name,
            "dataset_bytes": len(content),
            "before": before,
            "first_import_id": str(first.id),
            "first_normalization": first_summary,
            "after_first": after_first,
            "first_publication_delta": after_first["publications"] - before["publications"],
            "rerun_normalization": rerun_counters,
            "after_rerun": after_rerun,
            "duplicate_import_id": str(duplicate.id),
            "duplicate_normalization": duplicate_summary,
            "after_duplicate": after_duplicate,
            "metadata_change": {
                "counters": metadata_counters,
                "canonical_title_unchanged": unchanged_title,
                "new_raw_provenance_linked": metadata_linked,
            },
            "delete_safety": delete_check,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
