"""Safely inspect and remove explicitly marked disposable lecturer fixtures.

Lecturers are institutional master records. Missing user or Scopus links do
not make a lecturer disposable. This tool therefore only considers records
with an explicit ``test://disposable/`` provenance snapshot and requires both
an explicit lecturer id and ``--apply`` for mutation.

Usage:
    python -m scripts.clean_orphan_lecturers --lecturer-id ID
    python -m scripts.clean_orphan_lecturers --lecturer-id ID --apply
"""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session_factory
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)

DISPOSABLE_SOURCE_SYSTEM = "TEST"
DISPOSABLE_SOURCE_PREFIX = "test://disposable/"


def has_disposable_provenance(source_system: str, source_url: str) -> bool:
    return (
        source_system == DISPOSABLE_SOURCE_SYSTEM
        and source_url.startswith(DISPOSABLE_SOURCE_PREFIX)
    )


def disposable_lecturer_ids(
    session: Session,
    lecturer_ids: Sequence[uuid.UUID],
) -> list[uuid.UUID]:
    """Return only explicitly disposable ids with no protected relationships."""
    if not lecturer_ids:
        return []

    linked_user = exists().where(User.lecturer_id == Lecturer.id)
    linked_scopus = exists().where(LecturerScopusIdentity.lecturer_id == Lecturer.id)
    downstream_publication = exists().where(
        LecturerKnownPublication.lecturer_id == Lecturer.id
    )
    disposable_snapshot = exists().where(
        LecturerSourceSnapshot.lecturer_id == Lecturer.id,
        LecturerSourceSnapshot.source_system == DISPOSABLE_SOURCE_SYSTEM,
        LecturerSourceSnapshot.source_url.startswith(DISPOSABLE_SOURCE_PREFIX),
    )

    statement = (
        select(Lecturer.id)
        .where(
            Lecturer.id.in_(lecturer_ids),
            disposable_snapshot,
            ~linked_user,
            ~linked_scopus,
            ~downstream_publication,
        )
        .order_by(Lecturer.id)
    )
    return list(session.scalars(statement))


def remove_disposable_lecturers(
    session: Session,
    lecturer_ids: Sequence[uuid.UUID],
) -> int:
    """Delete only preselected disposable lecturers in the current transaction."""
    removable_ids = disposable_lecturer_ids(session, lecturer_ids)
    if not removable_ids:
        return 0

    session.query(LecturerSourceSnapshot).filter(
        LecturerSourceSnapshot.lecturer_id.in_(removable_ids)
    ).delete(synchronize_session=False)
    deleted = session.query(Lecturer).filter(Lecturer.id.in_(removable_ids)).delete(
        synchronize_session=False
    )
    return deleted


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lecturer-id",
        action="append",
        required=True,
        help="Explicit lecturer UUID to inspect; repeat for multiple records.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletion. Without this flag the command is a dry run.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if settings.environment.lower() == "prod":
        raise SystemExit("Refusing to run in ENVIRONMENT=prod.")

    try:
        lecturer_ids = [uuid.UUID(value) for value in args.lecturer_id]
    except ValueError as exc:
        raise SystemExit(f"Invalid --lecturer-id: {exc}") from exc

    factory = get_session_factory()
    with factory() as session:
        candidates = disposable_lecturer_ids(session, lecturer_ids)
        print(
            f"Selection: {len(candidates)} of {len(lecturer_ids)} requested lecturer(s) "
            f"match source_system={DISPOSABLE_SOURCE_SYSTEM!r}, "
            f"source_url prefix={DISPOSABLE_SOURCE_PREFIX!r}, "
            "and have no protected relationships."
        )
        if not args.apply:
            print("Dry run only. No records changed. Pass --apply to mutate.")
            return 0

        try:
            deleted = remove_disposable_lecturers(session, lecturer_ids)
            session.commit()
        except Exception:
            session.rollback()
            raise
        print(f"Applied deletion: {deleted} disposable lecturer record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
