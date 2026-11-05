"""One-time backfill: approve the 35 lecturer <-> Scopus-author pairs that
ICTU's own repository page already confirms (the "multi Scopus ID, needs
merging" roster), using each lecturer's declared *primary* Scopus ID.

Source: data/lecturers/raw/merge_guide.json, captured from
https://repository.ictu.edu.vn/huong-dan-gop-tai-khoan-scopus/

This script never invents evidence and never bypasses the review boundary:

  - If a PENDING candidate already exists for (lecturer, primary scopus
    author) -- from the ordinary name-matching candidate generator -- it is
    accepted through the normal CandidateReviewService.accept_candidate(),
    citing the ICTU page as the reason.
  - If no candidate exists at all (the common case here: these are exactly
    the lecturers whose Scopus-listed name is too different from their ICTU
    name for the name-matching rules to find on their own -- e.g. a Scopus
    name written "Surname, Given Middle" against an ICTU name in a different
    order), this script creates ONE new, clearly
    separate CandidateGenerationRun (rule_set_id=ICTU_OFFICIAL_MERGE_GUIDE_
    BACKFILL) carrying a single SOURCE_CLAIM evidence row that cites the
    ICTU page, then accepts it through the same service. SOURCE_CLAIM
    evidence promotes to IdentityEvidence.evidence_type='APPROVED_ID' --
    this repository page IS the institution declaring the ID, not a
    name/publication heuristic.
  - Already-APPROVED pairs are left untouched (idempotent re-run).
  - After an ACCEPT, the identity is also set as the lecturer's *primary*
    display Scopus ID (PrimaryIdentityService), matching what the ICTU page
    calls "ID chinh hien dung".

Only the primary Scopus ID per lecturer is touched here. The other
(alternate/duplicate) IDs each lecturer may hold are left for ADMIN to
review individually in the normal "Duyet doi sanh" queue -- they are lower
confidence and some may turn out to belong to someone else entirely.

``--actor-email`` is required: the email of an active ADMIN account that the
review decisions are recorded under (audit trail). It is deliberately not
hard-coded in this file.

``--dry-run`` writes nothing: the review service only flushes, and the whole
session is rolled back at the end. ``--apply`` commits each lecturer on its own,
so one failing entry never discards the entries already applied.

Usage (from backend/)::

    python -m scripts.seed_merge_guide_identities --dry-run --actor-email <admin-email>
    python -m scripts.seed_merge_guide_identities --apply --actor-email <admin-email>
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.services.candidate_review_queries import current_reviewable_observation
from app.services.candidate_review_service import (
    AcceptCandidateCommand,
    CandidateReviewError,
    CandidateReviewService,
)
from app.services.matching.candidate_persistence import canonical_json, sha256_json
from app.services.primary_scopus_identity import PrimaryIdentityError, PrimaryIdentityService

MERGE_GUIDE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "lecturers" / "raw" / "merge_guide.json"
)
RULE_SET_ID = "ICTU_OFFICIAL_MERGE_GUIDE_BACKFILL"
RULE_SET_VERSION = "2026-11-03"
EVIDENCE_RULE_ID = "ICTU_OFFICIAL_MERGE_GUIDE"
EVIDENCE_RULE_VERSION = "1.0"


def _reason(name: str, email: str, source_url: str) -> str:
    return (
        f"Xac nhan theo trang chinh thuc ICTU ({source_url}): "
        f"ID chinh cua {name} ({email})."
    )


def _create_source_claim_candidate(
    session: Session,
    *,
    lecturer: Lecturer,
    scopus_author: ScopusAuthor,
    entry: dict,
    source_url: str,
    now: datetime,
) -> tuple[LecturerScopusCandidate, LecturerScopusCandidateObservation]:
    run = CandidateGenerationRun(
        id=uuid.uuid4(),
        rule_set_id=RULE_SET_ID,
        rule_set_version=RULE_SET_VERSION,
        source_state={
            "schema_version": 1,
            "source": "ICTU repository Scopus merge-guide backfill",
            "source_url": source_url,
            "lecturer_email": lecturer.email,
        },
        status="COMPLETED",
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    candidate = LecturerScopusCandidate(
        id=uuid.uuid4(),
        lecturer_id=lecturer.id,
        scopus_author_id=scopus_author.id,
        status="PENDING",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(candidate)
    session.flush()

    snapshot = {
        "lecturer_id": str(lecturer.id),
        "lecturer_full_name": lecturer.full_name,
        "scopus_author_id": str(scopus_author.id),
        "scopus_author_scopus_id": scopus_author.scopus_id,
        "scopus_author_preferred_name": scopus_author.preferred_name,
        "source": "ictu_repository_merge_guide",
    }
    observation = LecturerScopusCandidateObservation(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        generation_run_id=run.id,
        observed_at=now,
        candidate_snapshot=json.loads(canonical_json(snapshot)),
        observation_hash=sha256_json(snapshot),
    )
    session.add(observation)
    session.flush()

    payload = {
        "lecturer_name_on_source": entry["name"],
        "lecturer_email": entry["email"],
        "declared_id_count": entry["declared_id_count"],
        "declared_publication_count": entry["publication_count"],
        "primary_scopus_id": entry["primary_scopus_id"],
        "all_scopus_ids_on_source": entry["scopus_ids"],
    }
    evidence = LecturerScopusCandidateEvidence(
        id=uuid.uuid4(),
        observation_id=observation.id,
        evidence_kind="SOURCE_CLAIM",
        rule_id=EVIDENCE_RULE_ID,
        rule_version=EVIDENCE_RULE_VERSION,
        payload=json.loads(canonical_json(payload)),
        source_refs=[{"kind": "ictu_repository_page", "url": source_url}],
        evidence_fingerprint=sha256_json(payload),
    )
    session.add(evidence)
    session.flush()

    return candidate, observation


def run(apply: bool, actor_email: str) -> int:
    guide = json.loads(MERGE_GUIDE_PATH.read_text(encoding="utf-8"))
    source_url = guide["source_url"]
    entries = guide["entries"]

    engine = get_engine()
    results: list[tuple[str, str, str]] = []  # (name, email, outcome)

    with Session(engine) as session:
        admin = session.scalar(select(User).where(User.email == actor_email))
        if admin is None or admin.role != "ADMIN" or not admin.is_active:
            print(f"ERROR: active ADMIN user {actor_email!r} not found", file=sys.stderr)
            return 2

        # auto_commit=apply: a dry run must never commit (the service only flushes then), while
        # --apply keeps committing per lecturer so one failure cannot discard earlier entries.
        service = CandidateReviewService(session, auto_commit=apply)

        for entry in entries:
            name = entry["name"]
            email = entry["email"]
            primary_id = entry["primary_scopus_id"]
            now = datetime.now(UTC)

            lecturer = session.scalar(select(Lecturer).where(Lecturer.email == email))
            if lecturer is None:
                results.append((name, email, "SKIP: lecturer email not found in DB"))
                continue

            scopus_author = session.scalar(
                select(ScopusAuthor).where(ScopusAuthor.scopus_id == primary_id)
            )
            if scopus_author is None:
                results.append((name, email, f"SKIP: scopus_author {primary_id} not in DB"))
                continue

            existing_identity = session.scalar(
                select(LecturerScopusIdentity).where(
                    LecturerScopusIdentity.lecturer_id == lecturer.id,
                    LecturerScopusIdentity.scopus_author_id == scopus_author.id,
                )
            )
            if existing_identity is not None and existing_identity.status == "APPROVED":
                results.append((name, email, "OK: already APPROVED"))
                identity_id = existing_identity.id
            elif existing_identity is not None:
                results.append(
                    (name, email, f"SKIP: identity exists with status={existing_identity.status}")
                )
                continue
            else:
                candidate = session.scalar(
                    select(LecturerScopusCandidate).where(
                        LecturerScopusCandidate.lecturer_id == lecturer.id,
                        LecturerScopusCandidate.scopus_author_id == scopus_author.id,
                    )
                )
                reason = _reason(name, email, source_url)

                if candidate is not None and candidate.status == "PENDING":
                    try:
                        observation = current_reviewable_observation(session, candidate.id)
                        accept_result = service.accept_candidate(
                            AcceptCandidateCommand(
                                candidate_id=candidate.id,
                                observation_id=observation.id,
                                candidate_version=candidate.version,
                                reviewer_user_id=admin.id,
                                reason=reason,
                            )
                        )
                        identity_id = accept_result.resulting_identity_id
                        results.append((name, email, "ACCEPTED: existing PENDING candidate"))
                    except CandidateReviewError as exc:
                        results.append((name, email, f"ERROR accepting existing candidate: {exc}"))
                        session.rollback()
                        continue
                elif candidate is not None:
                    results.append(
                        (name, email, f"SKIP: candidate exists with status={candidate.status}")
                    )
                    continue
                else:
                    try:
                        new_candidate, _obs = _create_source_claim_candidate(
                            session,
                            lecturer=lecturer,
                            scopus_author=scopus_author,
                            entry=entry,
                            source_url=source_url,
                            now=now,
                        )
                        session.flush()
                        observation = current_reviewable_observation(session, new_candidate.id)
                        accept_result = service.accept_candidate(
                            AcceptCandidateCommand(
                                candidate_id=new_candidate.id,
                                observation_id=observation.id,
                                candidate_version=new_candidate.version,
                                reviewer_user_id=admin.id,
                                reason=reason,
                            )
                        )
                        identity_id = accept_result.resulting_identity_id
                        results.append(
                            (name, email, "ACCEPTED: new SOURCE_CLAIM candidate (ICTU page)")
                        )
                    except CandidateReviewError as exc:
                        results.append((name, email, f"ERROR creating/accepting candidate: {exc}"))
                        session.rollback()
                        continue

            # Set as the lecturer's primary (display) Scopus ID.
            try:
                primary_service = PrimaryIdentityService(session, auto_commit=False)
                primary_service.set_primary(
                    lecturer.id, identity_id, admin.id,
                    reason=f"ID chinh theo trang chinh thuc ICTU: {source_url}",
                )
            except PrimaryIdentityError as exc:
                if exc.code != "ALREADY_PRIMARY":
                    results[-1] = (
                        name,
                        email,
                        results[-1][2] + f" | primary-set warning: {exc.message}",
                    )

        if apply:
            session.commit()
        else:
            session.rollback()

    mode_label = "APPLIED" if apply else "DRY-RUN (rolled back)"
    print(f"{mode_label} -- {len(entries)} entries from merge_guide.json\n")
    width_name = max(len(r[0]) for r in results)
    width_email = max(len(r[1]) for r in results)
    for name, email, outcome in results:
        print(f"{name:<{width_name}}  {email:<{width_email}}  {outcome}")

    errors = sum(1 for _, _, o in results if o.startswith("ERROR"))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run", action="store_true", help="Run and roll back; prints what would happen."
    )
    mode.add_argument("--apply", action="store_true", help="Run and commit.")
    parser.add_argument(
        "--actor-email",
        required=True,
        help="Email of an active ADMIN account the decisions are recorded under.",
    )
    args = parser.parse_args()
    return run(apply=args.apply, actor_email=args.actor_email)


if __name__ == "__main__":
    raise SystemExit(main())
