"""B2-D append-only history on the isolated SQLite mirror.

Scope and honesty notes:

* Every authority attestation here is SYNTHETIC. Nothing in this file authenticates a
  real institution, verifier, person or capability grant.
* SQLite is NOT PostgreSQL validation. The mirror carries no CHECK constraints, no
  foreign keys into non-staging tables and no composite FKs, so the invariants proved
  here are the ones the *service* enforces plus the UNIQUE constraints. Database-level
  CHECK/FK enforcement and concurrency are PostgreSQL work and are marked NOT_EXECUTED.
* No production decision is executed: SOURCE_CLAIM submit stays inactive throughout.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import event, select

from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.governance import AuditEvent
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.source_claim_hybrid import (
    HybridDecisionContext,
    HybridDecisionEvent,
    HybridExceptionApproval,
    HybridInstitutionalProvenance,
    HybridPolicyDocument,
    HybridReviewerProposal,
    HybridRevocation,
)
from app.services.source_claim_hybrid import (
    POLICY_DIGEST,
    POLICY_VERSION,
    AssessmentState,
    DenialReason,
    HumanAuthority,
    ReviewBranch,
    SourceAuthenticityState,
)
from app.services.source_claim_hybrid_persistence import (
    APPROVE_EXCEPTION,
    PROPOSE,
    HybridDecisionJournal,
)
from tests.unit.test_source_claim_candidate_persistence import world as world  # noqa: F401
from tests.unit.test_source_claim_decision_boundary import assert_error
from tests.unit.test_source_claim_hybrid import (
    AT,
    LATER,
    independent,
    receipt,
    standard,
)
from tests.unit.test_source_claim_hybrid import (
    setup as setup,  # noqa: F401  (hybrid fixture: world + synthetic authority + actors)
)

WAY_LATER = LATER + timedelta(minutes=10)


def journal(setup):
    world, boundary, _, _, _, _ = setup
    return HybridDecisionJournal(world[0], compatibility=boundary)


def propose(setup, command=None):
    _, _, _, actor, _, default = setup
    return journal(setup).record_proposal(actor, command or default, proposed_at=AT)


def approve(setup, *, approved_at=LATER, command=None):
    _, boundary, _, actor, approver, default = setup
    command = command or default
    draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
    return journal(setup).record_exception_approval(
        actor, approver, command, draft, proposed_at=AT, approved_at=approved_at)


def revoke(setup, target, *, kind="REVOKE", replacement=None, at=WAY_LATER):
    _, _, _, actor, approver, _ = setup
    return journal(setup).record_revocation(
        approver, actor, target_event_id=target, revocation_kind=kind,
        reason="Synthetic compensation; no identity is affected",
        replacement_event_id=replacement, decided_at=at)


def rows(db, model):
    return db.scalars(select(model)).all()


# ---------------------------------------------------------------------------
# Recording a proposal
# ---------------------------------------------------------------------------

def test_proposal_is_recorded_as_history_and_changes_no_decision_state(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    candidate = db.scalar(select(LecturerScopusCandidate))
    before = (candidate.status, candidate.version)
    result = propose(setup)
    assert (result.outcome, result.event_kind, result.stream_seq) == ("APPENDED", PROPOSE, 1)
    assert result.final_acceptance is False and result.workflow_active is False
    event_row, = rows(db, HybridDecisionEvent)
    assert event_row.previous_event_id is None and event_row.previous_event_hash is None
    assert event_row.operation_key == result.operation_key
    assert event_row.snapshot_hash == result.snapshot_hash
    assert json.loads(event_row.snapshot_json)["final_acceptance"] is False
    proposal_row, = rows(db, HybridReviewerProposal)
    assert proposal_row.branch == ReviewBranch.INSTITUTIONAL_EXCEPTION
    assert proposal_row.assurance_basis == ReviewBranch.INSTITUTIONAL_EXCEPTION
    assert proposal_row.reviewer_principal_id is not None
    # Nothing that represents an acceptance exists, and the candidate is untouched.
    db.expire_all()
    candidate = db.get(LecturerScopusCandidate, candidate.id)
    assert (candidate.status, candidate.version) == before
    assert rows(db, LecturerScopusIdentity) == [] and rows(db, IdentityEvidence) == []
    assert rows(db, LecturerScopusCandidateReview) == []


def test_recorded_context_binds_the_policy_revision_and_its_exact_parameters(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    propose(setup)
    policy, = rows(db, HybridPolicyDocument)
    assert policy.policy_digest == POLICY_DIGEST and policy.policy_revision == POLICY_VERSION
    context, = rows(db, HybridDecisionContext)
    assert context.policy_digest == POLICY_DIGEST
    assert context.context_digest == rows(db, HybridDecisionEvent)[0].snapshot_hash
    assert context.candidate_version >= 1


def test_institutional_provenance_is_stored_as_declaration_never_as_verified_evidence(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    propose(setup)
    provenance = rows(db, HybridInstitutionalProvenance)
    assert provenance and all(p.independently_verified is False for p in provenance)
    assert all(p.evidence_kind == "SOURCE_CLAIM" for p in provenance)
    assert all(p.source_tier == "INSTITUTION_DECLARED" for p in provenance)
    assert all(p.issuance_state == SourceAuthenticityState.CURRENT for p in provenance)


def test_every_append_writes_one_linked_audit_event(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    result = propose(setup)
    audit, = [a for a in rows(db, AuditEvent) if a.entity_type == "sc_hybrid_event"]
    assert audit.entity_id == result.event_id and audit.actor_type == "USER"
    assert audit.event_metadata["final_acceptance"] is False
    assert rows(db, HybridDecisionEvent)[0].audit_event_id == audit.id


# ---------------------------------------------------------------------------
# Idempotency and replay protection
# ---------------------------------------------------------------------------

def test_replaying_the_same_proposal_resolves_to_the_recorded_event(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    first = propose(setup)
    again = propose(setup)
    assert again.outcome == "ALREADY_RECORDED" and again.event_id == first.event_id
    assert len(rows(db, HybridDecisionEvent)) == 1
    assert len(rows(db, HybridReviewerProposal)) == 1


@pytest.mark.parametrize("field", ["final_acceptance", "branch", "policy_digest"])
def test_a_tampered_receipt_records_nothing(setup, field):
    world, boundary, _, actor, _, command = setup
    db = world[0]
    draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
    value = json.loads(draft.snapshot_json)
    value[field] = True if field == "final_acceptance" else "tampered"
    assert_error("HYBRID_REPLAY_INVALID", lambda: journal(setup).record_proposal(
        actor, command, proposed_at=AT, receipt=receipt(value)))
    assert rows(db, HybridDecisionEvent) == [] and rows(db, HybridDecisionContext) == []


def test_operation_key_cannot_be_reused_for_another_snapshot(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    result = propose(setup)
    # The key is derived from the trusted snapshot, so forcing another snapshot under the
    # recorded key is the tampering case the guard exists for.
    db.execute(HybridDecisionEvent.__table__.update().where(
        HybridDecisionEvent.event_id == result.event_id).values(snapshot_hash="0" * 64))
    assert_error("HYBRID_OPERATION_REPLAY_CONFLICT", lambda: propose(setup))
    assert len(rows(db, HybridDecisionEvent)) == 1


# ---------------------------------------------------------------------------
# Dual control on the exception branch
# ---------------------------------------------------------------------------

def test_exception_approval_appends_a_chained_second_event(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    proposal = propose(setup)
    result = approve(setup)
    assert (result.outcome, result.event_kind, result.stream_seq) == (
        "APPENDED", APPROVE_EXCEPTION, 2)
    approval_event = db.get(HybridDecisionEvent, result.event_id)
    assert approval_event.previous_event_id == proposal.event_id
    assert approval_event.previous_event_hash == proposal.envelope_hash
    approval, = rows(db, HybridExceptionApproval)
    assert approval.proposal_id == proposal.event_id
    assert approval.approver_user_id != approval.reviewer_user_id
    assert approval.approver_principal_id != approval.reviewer_principal_id
    # Still not an acceptance.
    assert rows(db, LecturerScopusIdentity) == [] and rows(db, IdentityEvidence) == []


def test_an_approval_needs_a_proposal_that_is_already_in_history(setup):
    world, _, _, _, _, _ = setup
    assert_error("HYBRID_PROPOSAL_NOT_RECORDED", lambda: approve(setup))
    assert rows(world[0], HybridExceptionApproval) == []


def test_only_one_approval_per_proposal_regardless_of_retries(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    propose(setup)
    first = approve(setup)
    assert approve(setup).event_id == first.event_id          # same snapshot: idempotent
    # A different action time is a different snapshot, so it is a *second* approval
    # attempt; UNIQUE(proposal_id) refuses it.
    assert_error("HYBRID_HISTORY_INTEGRITY_VIOLATION",
                 lambda: approve(setup, approved_at=LATER + timedelta(minutes=1)))
    assert len(rows(db, HybridExceptionApproval)) == 1


def test_self_approval_is_refused(setup):
    world, boundary, _, actor, _, command = setup
    propose(setup)
    draft = boundary.prepare_proposal(actor, command, proposed_at=AT)
    assert_error("HYBRID_SELF_APPROVAL_FORBIDDEN",
                 lambda: journal(setup).record_exception_approval(
                     actor, actor, command, draft, proposed_at=AT, approved_at=LATER))
    assert rows(world[0], HybridExceptionApproval) == []


def test_one_human_with_two_accounts_cannot_satisfy_dual_control(setup):
    world, _, authority, _, _, _ = setup
    propose(setup)
    shared = uuid.uuid4()
    authority.facts = replace(authority.facts, humans=tuple(
        replace(h, human_principal_id=shared) for h in authority.facts.humans))
    assert_error("HYBRID_SELF_APPROVAL_FORBIDDEN", lambda: approve(setup))
    assert rows(world[0], HybridExceptionApproval) == []


def test_an_approver_without_the_approve_grant_is_refused(setup):
    world, _, authority, actor, approver, _ = setup
    propose(setup)
    authority.facts = replace(authority.facts, humans=tuple(
        h if h.user_id == actor.user_id else replace(h, grants=())
        for h in authority.facts.humans))
    assert_error("HYBRID_EXCEPTION_PERMISSION_REQUIRED", lambda: approve(setup))
    assert rows(world[0], HybridExceptionApproval) == []
    assert approver.user_id != actor.user_id


def test_a_revoked_account_cannot_approve_even_with_a_recorded_proposal(setup):
    world, _, authority, actor, _, _ = setup
    propose(setup)
    authority.facts = replace(authority.facts, humans=tuple(
        h if h.user_id == actor.user_id else replace(h, current=False)
        for h in authority.facts.humans))
    assert_error("HYBRID_HUMAN_AUTHORIZATION_REQUIRED", lambda: approve(setup))


# ---------------------------------------------------------------------------
# Branch precedence
# ---------------------------------------------------------------------------

def test_qualifying_independent_evidence_blocks_the_exception_branch(setup):
    world, _, authority, _, _, _ = setup
    authority.facts = replace(authority.facts, independent=(independent(),))
    assert_error(DenialReason.STANDARD_AVAILABLE, lambda: propose(setup))
    assert rows(world[0], HybridDecisionEvent) == []


def test_the_standard_branch_needs_qualifying_independent_evidence(setup):
    world, _, authority, _, _, command = setup
    assert_error(DenialReason.INDEPENDENT_MISSING,
                 lambda: propose(setup, standard(command)))
    authority.facts = replace(authority.facts, independent=(independent(),))
    result = propose(setup, standard(command))
    assert result.outcome == "APPENDED"
    proposal, = rows(world[0], HybridReviewerProposal)
    assert proposal.branch == ReviewBranch.STANDARD_INDEPENDENT
    assert proposal.assurance_basis == "INDEPENDENT_VERIFIED"
    assert proposal.risk_acknowledgment is None


@pytest.mark.parametrize("branch", list(ReviewBranch))
def test_a_hard_conflict_blocks_both_branches_and_records_nothing(setup, branch):
    world, _, authority, _, _, command = setup
    authority.facts = replace(authority.facts, independent=(
        independent(state=AssessmentState.CONTRADICTORY),))
    target = standard(command) if branch == ReviewBranch.STANDARD_INDEPENDENT else command
    assert_error(DenialReason.HARD_CONFLICT, lambda: propose(setup, target))
    assert rows(world[0], HybridDecisionEvent) == []


def test_unverified_institutional_provenance_blocks_the_exception_branch(setup):
    world, _, authority, _, _, _ = setup
    authority.facts = replace(authority.facts, authenticity=())
    assert_error(DenialReason.PROVENANCE_UNVERIFIED, lambda: propose(setup))
    assert rows(world[0], HybridDecisionEvent) == []


# ---------------------------------------------------------------------------
# Revocation and supersession
# ---------------------------------------------------------------------------

def test_revocation_is_appended_under_dual_control(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    proposal = propose(setup)
    result = revoke(setup, proposal.event_id)
    assert (result.outcome, result.event_kind, result.stream_seq) == ("APPENDED", "REVOKE", 2)
    revocation, = rows(db, HybridRevocation)
    assert revocation.target_event_id == proposal.event_id
    assert revocation.initiator_user_id != revocation.authorizer_user_id
    assert revocation.initiator_principal_id != revocation.authorizer_principal_id
    assert revocation.replacement_event_id is None
    # The revoked event itself is untouched: compensation is an append, not an update.
    assert db.get(HybridDecisionEvent, proposal.event_id).envelope_hash == proposal.envelope_hash


def test_a_target_can_be_compensated_only_once(setup):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    revoke(setup, proposal.event_id)
    assert_error("HYBRID_EVENT_ALREADY_REVOKED", lambda: revoke(
        setup, proposal.event_id, at=WAY_LATER + timedelta(minutes=5)))
    assert len(rows(world[0], HybridRevocation)) == 1


def test_replaying_the_same_revocation_resolves_to_the_recorded_event(setup):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    first = revoke(setup, proposal.event_id)
    assert revoke(setup, proposal.event_id).event_id == first.event_id
    assert len(rows(world[0], HybridRevocation)) == 1


def test_supersede_requires_a_replacement_and_revoke_forbids_one(setup):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    approval = approve(setup)
    assert_error("HYBRID_REVOCATION_INVALID",
                 lambda: revoke(setup, proposal.event_id, kind="SUPERSEDE"))
    assert_error("HYBRID_REVOCATION_INVALID", lambda: revoke(
        setup, proposal.event_id, replacement=approval.event_id))
    result = revoke(setup, proposal.event_id, kind="SUPERSEDE",
                    replacement=approval.event_id)
    assert result.event_kind == "SUPERSEDE"
    revocation, = rows(world[0], HybridRevocation)
    assert revocation.replacement_event_id == approval.event_id


def test_a_single_human_cannot_revoke_alone(setup):
    world, _, _, actor, _, _ = setup
    proposal = propose(setup)
    assert_error("HYBRID_SELF_APPROVAL_FORBIDDEN",
                 lambda: journal(setup).record_revocation(
                     actor, actor, target_event_id=proposal.event_id,
                     revocation_kind="REVOKE", reason="Synthetic self-revocation",
                     decided_at=WAY_LATER))
    assert rows(world[0], HybridRevocation) == []


def test_revoking_an_unknown_event_is_refused(setup):
    world, _, _, _, _, _ = setup
    assert_error("HYBRID_REVOCATION_TARGET_NOT_FOUND",
                 lambda: revoke(setup, uuid.uuid4()))


# ---------------------------------------------------------------------------
# E3-P3-B2-E hardening: lifecycle rules (F3, F7, F8)
# ---------------------------------------------------------------------------

def test_a_revoked_proposal_can_no_longer_be_approved(setup):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    revoke(setup, proposal.event_id)
    assert_error("HYBRID_PROPOSAL_NOT_EFFECTIVE", lambda: approve(setup))
    assert rows(world[0], HybridExceptionApproval) == []


def test_a_superseded_proposal_can_no_longer_be_approved(setup):
    first = propose(setup)
    approval = approve(setup)                        # approved while it was effective
    revoke(setup, first.event_id, kind="SUPERSEDE", replacement=approval.event_id)
    # Another approval is refused for the lifecycle reason, not the once-only constraint.
    assert_error("HYBRID_PROPOSAL_NOT_EFFECTIVE",
                 lambda: approve(setup, approved_at=WAY_LATER + timedelta(minutes=5)))


@pytest.mark.parametrize("compensation", ["REVOKE", "SUPERSEDE"])
def test_a_revocation_or_supersession_cannot_itself_be_compensated(setup, compensation):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    approval = approve(setup)
    final = revoke(setup, proposal.event_id, kind=compensation,
                   replacement=None if compensation == "REVOKE" else approval.event_id)
    assert_error("HYBRID_REVOCATION_TARGET_INVALID", lambda: revoke(
        setup, final.event_id, at=WAY_LATER + timedelta(minutes=5)))
    assert len(rows(world[0], HybridRevocation)) == 1


def test_a_replacement_must_be_a_later_effective_proposal_or_approval(setup):
    world, _, _, _, _, _ = setup
    proposal = propose(setup)
    approval = approve(setup)
    retired = revoke(setup, approval.event_id)                     # the approval is revoked
    for bad in (retired.event_id,                                  # a REVOKE event
                approval.event_id):                                # revoked, not effective
        assert_error("HYBRID_REVOCATION_INVALID", lambda bad=bad: revoke(
            setup, proposal.event_id, kind="SUPERSEDE", replacement=bad,
            at=WAY_LATER + timedelta(minutes=5)))
    assert len(rows(world[0], HybridRevocation)) == 1


def test_only_one_proposal_per_candidate_is_effective(setup):
    world, _, _, actor, _, command = setup
    first = propose(setup)
    assert journal(setup).record_proposal(
        actor, command, proposed_at=AT).outcome == "ALREADY_RECORDED"      # a replay is fine
    assert_error("HYBRID_ACTIVE_PROPOSAL_EXISTS", lambda: journal(setup).record_proposal(
        actor, command, proposed_at=AT + timedelta(minutes=1)))
    assert len(rows(world[0], HybridReviewerProposal)) == 1
    # Replacement requires a validated REVOKE; the old proposal stays in history.
    revoke(setup, first.event_id)
    second = journal(setup).record_proposal(
        actor, command, proposed_at=AT + timedelta(minutes=1))
    assert (second.outcome, second.stream_seq) == ("APPENDED", 3)
    assert len(rows(world[0], HybridReviewerProposal)) == 2
    assert_error("HYBRID_ACTIVE_PROPOSAL_EXISTS", lambda: journal(setup).record_proposal(
        actor, command, proposed_at=AT + timedelta(minutes=2)))


# ---------------------------------------------------------------------------
# Append-only behaviour, transaction ownership and the inactive workflow
# ---------------------------------------------------------------------------

def test_history_is_append_only_and_the_caller_keeps_its_transaction(setup):
    world, _, _, _, _, _ = setup
    db = world[0]
    statements = []

    def capture(conn, cursor, statement, *args):
        statements.append(statement.lstrip().upper())

    proposal = propose(setup)
    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        approve(setup)
        revoke(setup, proposal.event_id)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
    assert any(s.startswith("SAVEPOINT") for s in statements)
    assert any(s.startswith("INSERT") for s in statements)
    # No UPDATE, no DELETE, and the caller's COMMIT/ROLLBACK is never taken.
    assert not any(s.startswith(("UPDATE", "DELETE", "TRUNCATE", "COMMIT", "ROLLBACK;"))
                   for s in statements)
    assert db.in_transaction()
    db.rollback()                               # the owner discards its own work
    assert rows(db, HybridDecisionEvent) == []


def test_submit_remains_inactive_on_the_persistence_boundary(setup):
    world, _, _, _, _, _ = setup
    propose(setup)
    assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: journal(setup).submit())
    assert rows(world[0], LecturerScopusIdentity) == []


def test_a_human_authority_without_a_principal_cannot_be_recorded(setup):
    world, _, authority, _, _, _ = setup
    authority.facts = replace(authority.facts, humans=tuple(
        HumanAuthority(h.user_id, None, h.auth_version, h.current, h.grants,
                       h.attestation_id, h.revision_digest)
        for h in authority.facts.humans))
    assert_error("HYBRID_HUMAN_AUTHORIZATION_REQUIRED", lambda: propose(setup))
    assert rows(world[0], HybridDecisionEvent) == []
