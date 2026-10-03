"""Script to clean up orphan unlinked lecturer records in PostgreSQL.

Removes all lecturer master rows that:
1. Have NO user account attached (User.lecturer_id IS NULL)
2. Have NO downstream Scopus identities attached

Preserves all 5 demo/system user accounts and their linked Lecturer records.

Usage:
    python -m scripts.clean_orphan_lecturers
"""

from __future__ import annotations

import sys
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)


def clean_orphan_lecturers(session: Session) -> int:
    # 1. Find all lecturer IDs that are linked to active Users
    linked_users = session.query(User).filter(User.lecturer_id.is_not(None)).all()
    protected_lecturer_ids = {u.lecturer_id for u in linked_users if u.lecturer_id is not None}

    # 2. Find all lecturer IDs linked to Scopus identities
    scopus_identities = session.query(LecturerScopusIdentity).all()
    protected_lecturer_ids.update(
        {i.lecturer_id for i in scopus_identities if i.lecturer_id is not None}
    )

    # 3. Find all unlinked lecturers
    all_lecturers = session.query(Lecturer).all()
    orphan_lecturers = [l for l in all_lecturers if l.id not in protected_lecturer_ids]
    orphan_ids = [l.id for l in orphan_lecturers]

    if not orphan_ids:
        print("[CLEAN] No orphan unlinked lecturers found. Database is clean!")
        return 0

    print(f"[CLEAN] Found {len(orphan_ids)} orphan unlinked lecturers to remove.")
    print(f"[CLEAN] Preserving {len(protected_lecturer_ids)} protected user-linked lecturers.")

    # 4. Clean known publications
    session.query(LecturerKnownPublication).filter(
        LecturerKnownPublication.lecturer_id.in_(orphan_ids)
    ).delete(synchronize_session=False)

    # 5. Clean source snapshots
    session.query(LecturerSourceSnapshot).filter(
        LecturerSourceSnapshot.lecturer_id.in_(orphan_ids)
    ).delete(synchronize_session=False)

    # 6. Clean lecturer master records
    deleted_count = session.query(Lecturer).filter(
        Lecturer.id.in_(orphan_ids)
    ).delete(synchronize_session=False)

    session.commit()
    print(f"[SUCCESS] Successfully removed {deleted_count} orphan unlinked lecturers.")
    return deleted_count


if __name__ == "__main__":
    factory = get_session_factory()
    with factory() as db_session:
        count = clean_orphan_lecturers(db_session)
        print(f"Done. Cleaned {count} records.")
