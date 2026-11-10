"""Bulk-apply hand-researched lecturer <-> Scopus-author pairs from a JSON file,
without clicking through the review UI for each one.

This is the generalized, scriptable version of the "Gán ID Scopus" button on the
lecturer-profile screen (and of the older ``seed_merge_guide_identities.py``,
which only covered the ICTU "multiple Scopus IDs, needs merging" page): an ADMIN
has already verified -- by hand, e.g. via ORCID, the lecturer's own publication
list, or any other outside source -- that a given Scopus Author ID really is a
given lecturer. Instead of typing that into the UI one lecturer at a time, the
ADMIN writes it once into ``data/lecturers/raw/scopus_identity_assignments.json``
(gitignored, local-only -- never commit real identifiers) and runs this script.

This still never bypasses the review boundary: every assignment goes through
``services.matching.manual_candidate.assign_scopus_identity()``, which only ever
creates a ``LecturerScopusIdentity`` via
``CandidateReviewService.accept_candidate()`` -- the ONE path allowed to do so --
citing the entry's ``reason`` as the review's evidence/reason. Nothing here
invents evidence or skips the D-2 reason policy.

JSON shape (see the file itself for a worked example)::

    {
      "entries": [
        {
          "email": "someone@ictu.edu.vn",
          "scopus_ids": ["12345678900", "98765432100"],
          "primary_scopus_id": "12345678900",   // optional, must be one of scopus_ids
          "reason": "Theo ORCID 0000-...-..."    // required: cites the source
        }
      ]
    }

Usage (from backend/)::

    python -m scripts.import_scopus_identity_assignments --check
    python -m scripts.import_scopus_identity_assignments --apply --actor-email <admin-email>

``--check`` is read-only: it resolves each lecturer/author pair and reports
what WOULD happen, writing nothing. ``--apply`` performs the assignments for
real, one entry at a time -- a failure on one entry never blocks the rest, and
re-running is safe (already-APPROVED pairs are reported and skipped).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models.governance import User
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.matching.manual_candidate import ManualCandidateError, assign_scopus_identity
from app.services.primary_scopus_identity import PrimaryIdentityError, PrimaryIdentityService

ASSIGNMENTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "lecturers"
    / "raw"
    / "scopus_identity_assignments.json"
)


def _load_entries() -> list[dict]:
    payload = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    return payload.get("entries", [])


def run_check() -> int:
    """Read-only: report what each entry would do, without writing anything."""

    entries = _load_entries()
    engine = get_engine()
    problems = 0
    with Session(engine) as session:
        for entry in entries:
            email = entry.get("email", "")
            scopus_ids = entry.get("scopus_ids", [])
            lecturer = session.scalar(select(Lecturer).where(Lecturer.email == email))
            if lecturer is None:
                print(f"[SKIP] {email}: lecturer not found in DB")
                problems += 1
                continue
            for scopus_id in scopus_ids:
                author = session.scalar(
                    select(ScopusAuthor).where(ScopusAuthor.scopus_id == scopus_id)
                )
                if author is None:
                    print(f"[MISSING] {email} / {scopus_id}: Scopus author not imported yet")
                    problems += 1
                else:
                    print(f"[OK] {email} / {scopus_id}: {author.preferred_name} (ready to assign)")
            if not entry.get("reason", "").strip():
                print(f"[SKIP] {email}: no 'reason' given (required)")
                problems += 1
    print(f"\n{len(entries)} entries checked, {problems} problem(s).")
    return 1 if problems else 0


def run_apply(actor_email: str) -> int:
    entries = _load_entries()
    engine = get_engine()
    errors = 0
    with Session(engine) as session:
        admin = session.scalar(select(User).where(User.email == actor_email))
        if admin is None or admin.role not in ("ADMIN", "REVIEWER") or not admin.is_active:
            print(f"ERROR: active ADMIN/REVIEWER user {actor_email!r} not found", file=sys.stderr)
            return 2

        for entry in entries:
            email = entry.get("email", "")
            scopus_ids = entry.get("scopus_ids", [])
            primary_scopus_id = entry.get("primary_scopus_id")
            reason = entry.get("reason", "").strip()
            if not reason:
                print(f"[SKIP] {email}: no 'reason' given (required)")
                errors += 1
                continue

            lecturer = session.scalar(select(Lecturer).where(Lecturer.email == email))
            if lecturer is None:
                print(f"[SKIP] {email}: lecturer not found in DB")
                errors += 1
                continue

            identity_id_by_scopus: dict[str, str] = {}
            for scopus_id in scopus_ids:
                try:
                    result = assign_scopus_identity(
                        session,
                        lecturer_id=lecturer.id,
                        scopus_id=scopus_id,
                        reason=reason,
                        reviewer=admin,
                    )
                    identity_id_by_scopus[scopus_id] = str(result.identity_id)
                    label = "already approved" if result.already_approved else "ASSIGNED"
                    print(f"[{label}] {email} / {scopus_id} ({result.scopus_preferred_name})")
                except ManualCandidateError as exc:
                    print(f"[ERROR] {email} / {scopus_id}: [{exc.code}] {exc.message}")
                    errors += 1

            if primary_scopus_id and primary_scopus_id in identity_id_by_scopus:
                try:
                    primary_service = PrimaryIdentityService(session, auto_commit=True)
                    primary_service.set_primary(
                        lecturer.id,
                        identity_id_by_scopus[primary_scopus_id],
                        admin.id,
                        reason=f"ID chinh (import hang loat): {reason}",
                    )
                    print(f"[PRIMARY] {email}: {primary_scopus_id}")
                except PrimaryIdentityError as exc:
                    if exc.code != "ALREADY_PRIMARY":
                        print(f"[WARN] {email}: could not set primary -- {exc.message}")

    print(f"\n{len(entries)} entries processed, {errors} error(s).")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="Read-only: report what would happen, write nothing."
    )
    mode.add_argument("--apply", action="store_true", help="Perform the assignments for real.")
    parser.add_argument(
        "--actor-email",
        help="Email of an active ADMIN/REVIEWER account the decisions are recorded under "
        "(required with --apply).",
    )
    args = parser.parse_args()
    if args.apply and not args.actor_email:
        parser.error("--apply requires --actor-email")
    if args.check:
        return run_check()
    return run_apply(args.actor_email)


if __name__ == "__main__":
    raise SystemExit(main())
