"""Inactive B2-B boundary on synthetic SQLite; no application/real reviewer data."""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError, replace

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import APIError
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
    LecturerScopusCandidateReview,
)
from app.models.governance import User
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.publication import ScopusAuthor
from app.models.source_staging import SourceRecord
from app.services.candidate_review_service import (
    CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE,
    AcceptCandidateCommand,
    CandidateReviewService,
    RejectCandidateCommand,
)
from app.services.matching.candidate_persistence import sha256_json
from app.services.source_claim_decision_boundary import (
    ReviewerContext,
    SourceClaimAcceptContext,
    SourceClaimDecisionBoundary,
)
from app.services.source_claims import parser
from tests.source_staging_fixtures import multi_row, sid
from tests.unit.test_source_claim_candidate_persistence import guide, uid, write
from tests.unit.test_source_claim_candidate_persistence import world as world
from tests.unit.test_source_claim_reviewer_read import completed_observation


def reviewer(db, *, role="REVIEWER", active=True):
    user = User(id=uid(750), email="reviewer@example.invalid", password_hash="synthetic",
                display_name="Synthetic reviewer", role=role, is_active=active,
                version=1, auth_version=1)
    db.add(user)
    db.flush()
    return user


def context(world, run=500, *, reason="Synthetic declaration reviewed; no identity approval"):
    db = world[0]
    root = db.scalar(select(LecturerScopusCandidate).where(
        LecturerScopusCandidate.lecturer_id == uid(1),
        LecturerScopusCandidate.scopus_author_id == uid(101)))
    obs = db.scalar(select(LecturerScopusCandidateObservation).where(
        LecturerScopusCandidateObservation.candidate_id == root.id,
        LecturerScopusCandidateObservation.generation_run_id == uid(run)))
    return SourceClaimAcceptContext(root.id, obs.id, root.version, reason)


@pytest.fixture
def setup(world):
    user = reviewer(world[0])
    guide(world)
    write(world)
    return world, SourceClaimDecisionBoundary(world[0]), ReviewerContext(user.id, user.auth_version)


def assert_error(code, operation):
    with pytest.raises(APIError) as exc:
        operation()
    assert exc.value.code == code
    return exc.value


def test_valid_snapshot_is_detached_explicit_and_never_a_decision(setup):
    world, boundary, actor = setup
    command = context(world)
    prepared = boundary.prepare(actor, command)
    snapshot = json.loads(prepared.snapshot_json)
    assert sha256_json(snapshot) == prepared.snapshot_hash
    assert snapshot["intended_action"] == "ACCEPT"
    assert snapshot["workflow_active"] is False and snapshot["decision_enabled"] is False
    assert snapshot["identity_evidence_promotion"] == "BLOCKED_OWNER_POLICY_REQUIRED"
    assert snapshot["generation"]["status"] == "STAGED"
    assert snapshot["active_rule_set"]["identity_rules_version"] == "1"
    assert snapshot["logical_fingerprints"]
    assert snapshot["capture_history"][0]["completeness"] == "COMPLETE"
    evidence, = snapshot["evidence"]
    assert evidence["evidence_kind"] == "SOURCE_CLAIM"
    assert evidence["source_tier"] == "INSTITUTION_DECLARED"
    assert evidence["source_refs"][0]["claim_id"] and evidence["source_refs"][0]["analysis_id"]
    assert evidence["history"][0]["rule_version"]
    assert "NAME_EVIDENCE_ONLY" in snapshot["review_policy"]["reason_triggers"]
    for private in ("password_hash", "record_raw", "record_email", "gv1@example.invalid"):
        assert private not in prepared.snapshot_json
    with pytest.raises(FrozenInstanceError):
        prepared.snapshot_hash = "changed"
    snapshot["evidence"].clear()
    assert json.loads(prepared.snapshot_json)["evidence"]
    assert world[0].scalars(select(IdentityEvidence)).all() == []
    assert world[0].scalars(select(LecturerScopusCandidateReview)).all() == []


def test_identical_prepare_and_replay_are_deterministic_and_inactive(setup, monkeypatch):
    world, boundary, actor = setup
    command = context(world)
    prepared = boundary.prepare(actor, command)
    assert boundary.prepare(actor, command) == prepared
    assert boundary.verify_replay(actor, command, prepared.snapshot_json,
                                  prepared.snapshot_hash) == prepared
    calls = []
    monkeypatch.setattr(CandidateReviewService, "accept_candidate", lambda *a: calls.append(a))
    monkeypatch.setattr(CandidateReviewService, "reject_candidate", lambda *a: calls.append(a))
    assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: boundary.submit(
        actor, command, prepared.snapshot_json, prepared.snapshot_hash))
    assert calls == []
    assert world[0].scalar(select(LecturerScopusCandidate)).status == "PENDING"
    assert world[0].scalars(select(LecturerScopusIdentity)).all() == []
    assert "SOURCE_CLAIM" not in CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE


@pytest.mark.parametrize(("role", "active", "expected"), [
    ("LECTURER", True, "FORBIDDEN"), ("OTHER", True, "FORBIDDEN"),
    ("REVIEWER", False, "ACCOUNT_LOCKED"),
])
def test_forbidden_roles_and_inactive_accounts_are_refused_before_candidate_data(
    world, role, active, expected,
):
    user = reviewer(world[0], role=role, active=active)
    boundary = SourceClaimDecisionBoundary(world[0])
    command = SourceClaimAcceptContext(uid(999), uid(998), 1, "Synthetic")
    assert_error(expected, lambda: boundary.prepare(ReviewerContext(user.id, 1), command))


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER"])
def test_both_authorized_roles_can_prepare_only_an_inactive_draft(world, role):
    user = reviewer(world[0], role=role)
    guide(world)
    write(world)
    prepared = SourceClaimDecisionBoundary(world[0]).prepare(
        ReviewerContext(user.id, 1), context(world))
    assert json.loads(prepared.snapshot_json)["decision_enabled"] is False


@pytest.mark.parametrize("actor", [None, ReviewerContext(uid(999), 1),
                                   ReviewerContext(uid(750), 999)])
def test_unauthenticated_unknown_or_revoked_principal_is_refused(setup, actor):
    world, boundary, _ = setup
    with pytest.raises(APIError) as exc:
        boundary.prepare(actor, context(world))
    assert exc.value.status_code == 401


def test_fresh_database_roles_are_used_and_pending_forged_role_is_not_flushed(world):
    user = reviewer(world[0], role="LECTURER")
    guide(world)
    write(world)
    user.role = "REVIEWER"  # Unflushed in-memory spoof cannot authorize the child view.
    assert_error("FORBIDDEN", lambda: SourceClaimDecisionBoundary(world[0]).prepare(
        ReviewerContext(user.id, 1), context(world)))
    assert user in world[0].dirty and user.role == "REVIEWER"
    with world[0].no_autoflush:
        stored = world[0].scalar(select(User.role).where(User.id == user.id))
    assert stored == "LECTURER"


@pytest.mark.parametrize("status", ["REJECTED", "SUPERSEDED", "ACCEPTED"])
def test_terminal_candidates_are_never_silently_reopened(setup, status):
    world, boundary, actor = setup
    command = context(world)
    world[0].execute(update(LecturerScopusCandidate).where(
        LecturerScopusCandidate.id == command.candidate_id).values(status=status))
    assert_error("CANDIDATE_ALREADY_DECIDED_CONFLICT", lambda: boundary.prepare(actor, command))
    assert world[0].get(LecturerScopusCandidate, command.candidate_id).status == status


def test_stale_version_is_checked_using_fresh_identity_map(setup):
    world, boundary, actor = setup
    command = context(world)
    world[0].execute(update(LecturerScopusCandidate).where(
        LecturerScopusCandidate.id == command.candidate_id).values(
            version=command.candidate_version + 1).execution_options(synchronize_session=False))
    assert_error("STALE_CANDIDATE_VERSION", lambda: boundary.prepare(actor, command))


def test_pending_flag_cannot_erase_prior_negative_review_history(setup):
    world, boundary, actor = setup
    command = context(world)
    world[0].add(LecturerScopusCandidateReview(
        id=uid(900), candidate_id=command.candidate_id, observation_id=command.observation_id,
        reviewer_user_id=actor.user_id, action="REJECT", from_status="PENDING",
        to_status="REJECTED", candidate_version=command.candidate_version,
        reason="Synthetic prior rejection", evidence_snapshot={},
    ))
    world[0].flush()
    assert_error("SOURCE_CLAIM_PRIOR_REVIEW_REQUIRES_POLICY", lambda: boundary.prepare(
        actor, command))
    assert world[0].get(LecturerScopusCandidate, command.candidate_id).status == "PENDING"


def test_new_capture_stales_the_exact_requested_generation(setup):
    world, boundary, actor = setup
    command = context(world)
    guide(world, ts="2026-10-30T00:00:00Z")
    assert_error("STALE_SOURCE_CLAIM_DECISION_CONTEXT", lambda: boundary.prepare(actor, command))
    write(world, 501)
    assert boundary.prepare(actor, context(world, 501))
    assert_error("STALE_SOURCE_CLAIM_DECISION_CONTEXT", lambda: boundary.prepare(actor, command))


def test_active_rule_change_stales_an_old_receipt(setup, monkeypatch):
    world, boundary, actor = setup
    command = context(world)
    before = boundary.prepare(actor, command)
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    world[1].activate_rule_set()
    assert_error("STALE_SOURCE_CLAIM_DECISION_CONTEXT", lambda: boundary.verify_replay(
        actor, command, before.snapshot_json, before.snapshot_hash))


def test_withdrawn_evidence_is_not_a_decision_basis(setup):
    world, boundary, actor = setup
    guide(world, rows=[], ts="2026-10-30T00:00:00Z")
    write(world, 501)
    assert_error("SOURCE_CLAIM_DECISION_NOT_CURRENT", lambda: boundary.prepare(
        actor, context(world, 501)))


def test_partial_latest_capture_is_incomplete_even_when_it_lists_the_claim(setup):
    world, boundary, actor = setup
    guide(world, ts="2026-10-30T00:00:00Z", completeness="PARTIAL")
    write(world, 501)
    assert_error("SOURCE_CLAIM_DECISION_INCOMPLETE", lambda: boundary.prepare(
        actor, context(world, 501)))


def test_past_partial_capture_remains_history_after_a_complete_current_capture(world):
    user = reviewer(world[0])
    guide(world, completeness="PARTIAL")
    write(world)
    guide(world, ts="2026-10-30T00:00:00Z")
    write(world, 501)
    draft = SourceClaimDecisionBoundary(world[0]).prepare(
        ReviewerContext(user.id, 1), context(world, 501))
    assert {c["completeness"] for c in json.loads(draft.snapshot_json)["capture_history"]} == {
        "COMPLETE", "PARTIAL"}


def test_equal_time_ambiguity_cannot_be_waived_by_a_reason(setup):
    world, boundary, actor = setup
    guide(world, rows=[])
    write(world, 501)
    assert_error("SOURCE_CLAIM_DECISION_NOT_CURRENT", lambda: boundary.prepare(
        actor, context(world, 501)))


def test_invalid_retained_record_is_not_a_decision_basis(setup):
    world, boundary, actor = setup
    record = world[0].scalar(select(SourceRecord))
    record.validation_status = "INVALID"  # Synthetic invalid parser output, no real records.
    world[0].flush()
    write(world, 501)
    assert_error("SOURCE_CLAIM_DECISION_NOT_CURRENT", lambda: boundary.prepare(
        actor, context(world, 501)))


def test_competing_scopus_ownership_is_blocked_without_discarding_claims(world):
    user = reviewer(world[0])
    guide(world, [multi_row(1, [sid(1)]), multi_row(2, [sid(1)])])
    write(world)
    before = world[0].scalars(select(LecturerScopusCandidateEvidence)).all()
    assert len(before) == 2
    assert_error("SOURCE_CLAIM_OWNERSHIP_CONFLICT", lambda: SourceClaimDecisionBoundary(
        world[0]).prepare(ReviewerContext(user.id, 1), context(world)))
    assert len(world[0].scalars(select(LecturerScopusCandidateEvidence)).all()) == 2


def test_multiple_ids_for_one_lecturer_remain_allowed_and_d2_reasons_remain(world):
    user = reviewer(world[0])
    guide(world, [multi_row(1, [sid(1), sid(2)])])
    write(world)
    draft = SourceClaimDecisionBoundary(world[0]).prepare(
        ReviewerContext(user.id, 1), context(world))
    triggers = json.loads(draft.snapshot_json)["review_policy"]["reason_triggers"]
    assert "NAME_EVIDENCE_ONLY" in triggers and "MULTIPLE_CANDIDATES_FOR_LECTURER" in triggers
    assert len(world[0].scalars(select(LecturerScopusCandidate)).all()) == 2


@pytest.mark.parametrize("status", ["CANDIDATE", "APPROVED", "REJECTED", "REVOKED"])
def test_existing_exact_identities_are_not_replaced_or_reopened(setup, status):
    world, boundary, actor = setup
    identity = LecturerScopusIdentity(id=uid(900), lecturer_id=uid(1), scopus_author_id=uid(101),
                                     status=status, version=1)
    world[0].add(identity)
    world[0].flush()
    write(world, 501)
    expected = ("IDENTITY_REVIEWER_REOPEN_REQUIRED" if status in {"REJECTED", "REVOKED"}
                else "PREEXISTING_IDENTITY_PROVENANCE_CONFLICT")
    assert_error(expected, lambda: boundary.prepare(actor, context(world, 501)))
    assert (identity.status, identity.version) == (status, 1)


def test_approved_author_for_other_lecturer_remains_protected(setup):
    world, boundary, actor = setup
    world[0].add(LecturerScopusIdentity(
        id=uid(900), lecturer_id=uid(2), scopus_author_id=uid(101), status="APPROVED", version=1))
    world[0].flush()
    write(world, 501)
    assert_error("SCOPUS_AUTHOR_ALREADY_APPROVED_FOR_OTHER_LECTURER", lambda: boundary.prepare(
        actor, context(world, 501)))


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_source_claim_does_not_lift_name_evidence_only_reason_requirement(setup, reason):
    world, boundary, actor = setup
    error = assert_error("REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE", lambda: boundary.prepare(
        actor, replace(context(world), reason=reason)))
    assert "NAME_EVIDENCE_ONLY" in error.data["reason_triggers"]


@pytest.mark.parametrize("field", ["tier", "provenance", "weight", "reviewer", "enabled"])
def test_replay_rejects_tampered_receipt_even_with_a_recomputed_client_hash(setup, field):
    world, boundary, actor = setup
    command = context(world)
    before = boundary.prepare(actor, command)
    value = json.loads(before.snapshot_json)
    if field == "tier":
        value["evidence"][0]["source_tier"] = "APPROVED_ID"
    elif field == "provenance":
        value["evidence"][0]["source_refs"][0]["claim_id"] = str(uid(999))
    elif field == "weight":
        value["evidence"][0]["current_weight"] = 999
    elif field == "reviewer":
        value["reviewer"]["id"] = str(uid(999))
    else:
        value["decision_enabled"] = True
    assert_error("SOURCE_CLAIM_DECISION_SNAPSHOT_INVALID", lambda: boundary.verify_replay(
        actor, command, json.dumps(value), sha256_json(value)))


@pytest.mark.parametrize("snapshot", [None, "[]", "not-json", "{}"])
def test_replay_malformed_receipts_are_controlled_failures(setup, snapshot):
    world, boundary, actor = setup
    assert_error("SOURCE_CLAIM_DECISION_SNAPSHOT_INVALID", lambda: boundary.verify_replay(
        actor, context(world), snapshot, "0" * 64))


def test_revoked_reviewer_role_invalidates_previous_receipt(setup):
    world, boundary, actor = setup
    command = context(world)
    receipt = boundary.prepare(actor, command)
    world[0].execute(update(User).where(User.id == actor.user_id).values(
        role="LECTURER").execution_options(synchronize_session=False))
    assert_error("FORBIDDEN", lambda: boundary.verify_replay(
        actor, command, receipt.snapshot_json, receipt.snapshot_hash))


def test_corrupted_persisted_evidence_fails_before_snapshot_creation(setup):
    world, boundary, actor = setup
    command = context(world)
    row = world[0].scalar(select(LecturerScopusCandidateEvidence))
    payload = copy.deepcopy(row.payload)
    payload["current_weight"] = 999
    row.payload = payload
    world[0].flush()
    assert_error("SOURCE_CLAIM_DECISION_EVIDENCE_INVALID", lambda: boundary.prepare(actor, command))


def test_caller_transaction_prior_writes_survive_success_failure_and_retry(setup):
    world, boundary, actor = setup
    db = world[0]
    command = context(world)
    earlier = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="Caller earlier write")
    db.add(earlier)
    db.flush()
    bad = replace(command, reason=None)
    assert_error("REVIEW_REASON_REQUIRED_FOR_WEAK_EVIDENCE", lambda: boundary.prepare(actor, bad))
    assert db.in_transaction() and db.get(ScopusAuthor, earlier.id) is earlier
    prepared = boundary.prepare(actor, command)
    assert boundary.verify_replay(actor, command, prepared.snapshot_json, prepared.snapshot_hash)
    assert db.get(ScopusAuthor, earlier.id) is earlier
    db.rollback()  # Owner controls rollback of all its data, including its earlier write.
    assert db.get(ScopusAuthor, uid(999)) is None


def test_boundary_does_not_autoflush_or_commit_pending_caller_state(setup):
    world, boundary, actor = setup
    pending = ScopusAuthor(id=uid(999), scopus_id=None, preferred_name="Invalid pending caller row")
    world[0].add(pending)
    assert boundary.prepare(actor, context(world))
    assert pending in world[0].new and world[0].is_active


def test_unexpected_integrity_error_propagates_with_prior_caller_write_intact(setup, monkeypatch):
    world, boundary, actor = setup
    db = world[0]
    command = context(world)
    earlier = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="Caller write")
    db.add(earlier)
    db.flush()
    original = SourceClaimDecisionBoundary._prepare

    def fail(view, user, cmd):
        # Authorization has already established the child's SAVEPOINT.
        raise IntegrityError("synthetic query failure", {}, RuntimeError("unexpected FK"))

    monkeypatch.setattr(SourceClaimDecisionBoundary, "_prepare", staticmethod(fail))
    with pytest.raises(IntegrityError):
        boundary.prepare(actor, command)
    assert db.in_transaction() and db.get(ScopusAuthor, earlier.id) is earlier
    monkeypatch.setattr(SourceClaimDecisionBoundary, "_prepare", staticmethod(original))
    assert boundary.prepare(actor, command)


def test_boundary_uses_savepoints_and_never_emits_decision_dml(setup):
    world, boundary, actor = setup
    statements = []

    def capture(conn, cursor, statement, parameters, execution_context, executemany):
        statements.append(statement.lstrip().upper())

    event.listen(world[0].get_bind(), "before_cursor_execute", capture)
    try:
        command = context(world)
        draft = boundary.prepare(actor, command)
        assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: boundary.submit(
            actor, command, draft.snapshot_json, draft.snapshot_hash))
    finally:
        event.remove(world[0].get_bind(), "before_cursor_execute", capture)
    assert any(s.startswith("SAVEPOINT") for s in statements)
    assert any(s.startswith("ROLLBACK TO SAVEPOINT") for s in statements)
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE", "COMMIT")) for s in statements)


@pytest.mark.parametrize("kind", ["NAME", "PUBLICATION"])
@pytest.mark.parametrize("action", ["ACCEPT", "REJECT"])
def test_existing_legacy_decisions_remain_unchanged_on_synthetic_sqlite(world, kind, action):
    # Regression only: existing service, isolated synthetic completed legacy run.
    # No SOURCE_CLAIM decision is executed and no real DB/identity is involved.
    user = reviewer(world[0])
    guide(world)
    write(world)
    root, obs, _ = completed_observation(world, kind)
    service = CandidateReviewService(world[0])
    reason = "Synthetic legacy regression"
    if action == "ACCEPT":
        result = service.accept_candidate(AcceptCandidateCommand(
            root.id, obs.id, root.version, user.id, reason))
        assert result.candidate_status == "ACCEPTED"
        promoted = world[0].scalars(select(IdentityEvidence)).all()
        assert len(promoted) == 1
        assert promoted[0].evidence_type == (
            "NAME_SIMILARITY" if kind == "NAME" else "PUBLICATION_OVERLAP")
    else:
        result = service.reject_candidate(RejectCandidateCommand(
            root.id, obs.id, root.version, user.id, reason))
        assert result.candidate_status == "REJECTED"
        assert world[0].scalars(select(IdentityEvidence)).all() == []
    review = world[0].scalar(select(LecturerScopusCandidateReview))
    assert review.evidence_snapshot["evidence"][0]["evidence_kind"] == kind
    assert world[0].get(CandidateGenerationRun, uid(500)).status == "STAGED"
