"""Remove imported lecturers that no lecturer import covers any more (dry run by default).

    python -m scripts.purge_orphan_lecturers            # only reports what would be removed
    python -m scripts.purge_orphan_lecturers --apply    # removes them (take a backup first)

A lecturer is an orphan when an import created it, every import that covered it was rolled back, and
nothing else (account, Scopus identity) depends on it. Manual lecturers are never touched.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.governance import User
from app.services.lecturer_dataset.rollback import (
    LecturerRollbackError,
    LecturerRollbackService,
    find_orphaned_imported_lecturers,
)
from scripts import demo_launcher as dl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    values = dl.read_env_file(dl.ENV_FILE)
    problems = dl.validate_config(values)
    if problems:
        print("[LOI] Cau hinh khong hop le: " + "; ".join(problems))
        return 1
    url = (
        f"postgresql+psycopg2://{values['DB_USER']}:{values['DB_PASSWORD']}"
        f"@127.0.0.1:{dl.PG_PORT}/{values['DB_NAME']}"
    )
    with Session(create_engine(url)) as db:
        orphans = find_orphaned_imported_lecturers(db)
        print(f"Database {values['DB_NAME']}: {len(orphans)} ho so giang vien mo coi.")
        if not args.apply or not orphans:
            return 0
        admin = db.scalars(select(User).where(User.role == "ADMIN").order_by(User.created_at)).first()
        if admin is None:
            print("[LOI] Khong co tai khoan ADMIN de ghi nhat ky.")
            return 1
        try:
            removed = LecturerRollbackService().purge_orphans(db, actor=admin)
        except LecturerRollbackError as exc:
            print(f"[LOI] {exc.code}: {exc.message}")
            return 1
        print(f"[OK] Da go {removed} ho so giang vien mo coi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
