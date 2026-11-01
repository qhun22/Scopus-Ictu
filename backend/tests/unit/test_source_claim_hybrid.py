"""HYBRID offline contract tests. All authority attestations below are SYNTHETIC.

They do not authenticate a real institution, verifier, human or exception grant.
SQLite is not PostgreSQL validation. No real/SOURCE_CLAIM decision is executed.
"""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import APIError
from app.models.candidate import LecturerScopusCandidate, LecturerScopusCandidateReview
from app.models.governance import User
from app.models.identity import IdentityEvidence, LecturerScopusIdentity
from app.models.publication import ScopusAuthor
from app.models.source_staging import SourceArtifact
from app.services.matching.candidate_persistence import sha256_json
from app.services.source_claim_decision_boundary import (
    PreparedSourceClaimDecision,
    ReviewerContext,
    SourceClaimDecisionBoundary,
)
from app.services.source_claim_hybrid import (
    POLICY_DIGEST,
    POLICY_ID,
    POLICY_VERSION,
    RISK_ACKNOWLEDGMENT,
    AssessmentState,
    AssuranceBasis,
    AuthorityFacts,
    DenialReason,
    Grant,
    HumanAuthority,
    HybridCommand,
    HybridSourceClaimCompatibility,
    IndependentAssessment,
    ReviewBranch,
    SourceAuthenticity,
    SourceAuthenticityState,
    evaluate_hybrid_policy,
)
from tests.source_staging_fixtures import multi_row, sid
from tests.unit.test_source_claim_candidate_persistence import guide, uid, write
from tests.unit.test_source_claim_candidate_persistence import world as world
from tests.unit.test_source_claim_decision_boundary import assert_error, context, reviewer

AT = datetime(2026, 10, 30, 10, tzinfo=UTC)
LATER = AT + timedelta(minutes=5)


class SyntheticAuthority:
    """Mutable test-only server authority; stored original context is NOT rebound."""
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def load(self, view, context_digest):
        assert view.autoflush is False
        self.calls += 1
        return self.facts


def independent(*, state=AssessmentState.QUALIFYING, kind="ORCID_EXACT", verified=True):
    # This is a verifier-output fixture, NOT inference from a source ORCID or enum.
    return IndependentAssessment(uid(820), "1" * 64, kind, state, verified)


@pytest.fixture
def setup(world):
    db = world[0]
    user = reviewer(db)
    other = User(id=uid(751), email="approver@example.invalid", password_hash="synthetic",
                 display_name="Synthetic approver", role="REVIEWER", is_active=True,
                 version=1, auth_version=1)
    db.add(other)
    db.flush()
    guide(world)
    write(world)
    actor, approver = ReviewerContext(user.id, 1), ReviewerContext(other.id, 1)
    source_command = context(world)
    base = SourceClaimDecisionBoundary(db).prepare(actor, source_command)
    humans = tuple(HumanAuthority(
        u.id, uid(900 + n), 1, True, (Grant.PROPOSE_EXCEPTION, Grant.APPROVE_EXCEPTION),
        uid(800 + n), "2" * 64) for n, u in enumerate((user, other)))
    authenticity = tuple(SourceAuthenticity(
        a.id, a.artifact_bytes_sha256, "ICTU", SourceAuthenticityState.CURRENT,
        uid(810 + n), "3" * 64, "FORMALLY_VERIFIED_ISSUANCE_V1")
        for n, a in enumerate(db.scalars(select(SourceArtifact)).all()))
    authority = SyntheticAuthority(AuthorityFacts(base.snapshot_hash, "4" * 64,
                                                 (), humans, authenticity))
    boundary = HybridSourceClaimCompatibility(db, authority=authority)
    command = HybridCommand(source_command, ReviewBranch.INSTITUTIONAL_EXCEPTION,
                            risk_acknowledgment=RISK_ACKNOWLEDGMENT)
    return world, boundary, authority, actor, approver, command


def proposal(setup):
    _, boundary, _, actor, _, command = setup
    return boundary.prepare_proposal(actor, command, proposed_at=AT)


def approve(setup, receipt=None):
    _, boundary, _, actor, approver, command = setup
    return boundary.prepare_exception_approval(
        actor, approver, command, receipt or proposal(setup), proposed_at=AT, approved_at=LATER)


def receipt(value):
    return PreparedSourceClaimDecision(json.dumps(value), sha256_json(value))


def standard(command):
    return replace(command, branch=ReviewBranch.STANDARD_INDEPENDENT, risk_acknowledgment=None)


def test_default_authority_is_unavailable_and_no_admin_fallback_exists(setup):
    world, _, _, actor, _, command = setup
    world[0].execute(update(User).where(User.id == actor.user_id).values(role="ADMIN"))
    assert_error("HYBRID_AUTHORITY_UNAVAILABLE", lambda: HybridSourceClaimCompatibility(
        world[0]).prepare_proposal(actor, command, proposed_at=AT))


def test_standard_requires_a_separately_qualified_independent_assessment(setup):
    _, boundary, authority, actor, _, command = setup
    authority.facts = replace(authority.facts, independent=(independent(),))
    prepared = boundary.prepare_proposal(actor, standard(command), proposed_at=AT)
    value = json.loads(prepared.snapshot_json)
    assert value["assurance_basis"] == AssuranceBasis.INDEPENDENT_VERIFIED
    assert value["outcome"] == "OFFLINE_PROPOSAL_PREPARED"
    assert value["final_acceptance"] is False
    assert value["source_context"]["review_policy"]["accept_reason_required"] is True
    assert value["institutional_provenance"][0]["evidence_kind"] == "SOURCE_CLAIM"
    assert value["institutional_provenance"][0]["source_tier"] == "INSTITUTION_DECLARED"
    assert value["source_context"]["identity_evidence_promotion"] == "BLOCKED_OWNER_POLICY_REQUIRED"


@pytest.mark.parametrize("assessments", [(), (independent(state=AssessmentState.INSUFFICIENT),)])
def test_institutional_claim_alone_or_insufficient_assessment_never_qualifies_standard(
    setup, assessments,
):
    _, boundary, authority, actor, _, command = setup
    authority.facts = replace(authority.facts, independent=assessments)
    assert_error(DenialReason.INDEPENDENT_MISSING, lambda: boundary.prepare_proposal(
        actor, standard(command), proposed_at=AT))
    assert proposal(setup)  # Lack is eligible only for a nonfinal institutional proposal.


@pytest.mark.parametrize(("state", "expected"), [
    (AssessmentState.INVALID, DenialReason.INDEPENDENT_INVALID),
    (AssessmentState.WITHDRAWN, DenialReason.INDEPENDENT_WITHDRAWN),
    (AssessmentState.CONTRADICTORY, DenialReason.HARD_CONFLICT),
])
@pytest.mark.parametrize("branch", list(ReviewBranch))
def test_invalid_withdrawn_and_contradictory_assessments_block_both_branches(
    setup, state, expected, branch,
):
    _, boundary, authority, actor, _, command = setup
    authority.facts = replace(authority.facts, independent=(independent(state=state),))
    command = standard(command) if branch == ReviewBranch.STANDARD_INDEPENDENT else command
    assert_error(expected, lambda: boundary.prepare_proposal(actor, command, proposed_at=AT))


@pytest.mark.parametrize(("kind", "verified"), [
    ("SOURCE_CLAIM", True), ("NAME_SIMILARITY", True), ("ORCID_EXACT", False),
])
def test_type_or_source_label_is_not_independent_verification(setup, kind, verified):
    _, boundary, authority, actor, _, command = setup
    authority.facts = replace(authority.facts, independent=(
        independent(kind=kind, verified=verified),))
    assert_error(DenialReason.INDEPENDENT_INVALID, lambda: boundary.prepare_proposal(
        actor, standard(command), proposed_at=AT))


def test_valid_provenance_only_prepares_exception_and_retains_distinct_assurance(setup):
    world, _, _, _, _, _ = setup
    prepared = proposal(setup)
    value = json.loads(prepared.snapshot_json)
    assert value["policy_id"] == POLICY_ID and value["policy_version"] == POLICY_VERSION
    assert value["policy_digest"] == POLICY_DIGEST
    assert value["conflict_evaluation"]["eligibility"]["required_branch"] == (
        ReviewBranch.INSTITUTIONAL_EXCEPTION)
    assert value["assurance_basis"] == AssuranceBasis.INSTITUTIONAL_EXCEPTION
    assert value["independent_assessments"] == []
    assert value["final_acceptance"] is False and value["simulation_only"] is True
    assert value["workflow_active"] is False and value["decision_enabled"] is False
    assert value["approved_at"] is None and value["approver"] is None
    provenance, = value["institutional_provenance"]
    assert provenance["claimed_scopus_id"] == sid(1)
    assert provenance["lecturer_id"] == str(uid(1))
    assert provenance["scopus_author_id"] == str(uid(101))
    assert provenance["captured_at"].endswith(("+00:00", "Z"))
    assert provenance["source_revision"] == provenance["immutable_snapshot_digest"]
    assert provenance["verification"]["issuing_organization"] == "ICTU"
    assert provenance["verification"]["verification_method"] == "FORMALLY_VERIFIED_ISSUANCE_V1"
    assert world[0].scalars(select(IdentityEvidence)).all() == []
    assert world[0].scalars(select(LecturerScopusIdentity)).all() == []
    with pytest.raises(FrozenInstanceError):
        prepared.snapshot_hash = "changed"


@pytest.mark.parametrize("state", [None, SourceAuthenticityState.UNVERIFIED,
                                  SourceAuthenticityState.REVOKED])
def test_missing_unverified_or_revoked_institutional_authenticity_blocks_exception(setup, state):
    _, _, authority, _, _, _ = setup
    authority.facts = replace(authority.facts, authenticity=(
        () if state is None else tuple(
            replace(a, state=state) for a in authority.facts.authenticity)))
    with pytest.raises(APIError):
        proposal(setup)


@pytest.mark.parametrize("field", ["artifact_digest", "verification_digest", "issuing_organization",
                                   "verification_method"])
def test_malformed_or_substituted_source_attestation_fails_closed(setup, field):
    _, _, authority, _, _, _ = setup
    item = authority.facts.authenticity[0]
    changed = "0" * 64 if field == "artifact_digest" else "untrusted"
    authority.facts = replace(authority.facts, authenticity=(replace(item, **{field: changed}),))
    with pytest.raises(APIError):
        proposal(setup)


def test_distinct_authorized_humans_validate_offline_approval_only(setup):
    world, boundary, _, actor, approver, command = setup
    prepared = proposal(setup)
    approval = approve(setup, prepared)
    value = json.loads(approval.snapshot_json)
    assert value["outcome"] == "OFFLINE_APPROVAL_VALIDATED"
    assert value["proposal_digest"] == prepared.snapshot_hash
    assert value["reviewer"]["user_id"] != value["approver"]["user_id"]
    assert value["reviewer"]["human_principal_id"] != value["approver"]["human_principal_id"]
    assert value["assurance_basis"] == AssuranceBasis.INSTITUTIONAL_EXCEPTION
    assert value["final_acceptance"] is False
    assert boundary.verify_exception_approval(
        actor, approver, command, prepared, approval, proposed_at=AT, approved_at=LATER) == approval
    assert world[0].scalars(select(LecturerScopusIdentity)).all() == []


@pytest.mark.parametrize("same_account", [True, False])
def test_same_account_or_two_accounts_for_the_same_human_cannot_approve(setup, same_account):
    _, boundary, authority, actor, approver, command = setup
    prepared = proposal(setup)
    if same_account:
        approver = actor
    else:
        first, second = authority.facts.humans
        authority.facts = replace(authority.facts, humans=(
            first, replace(second, human_principal_id=first.human_principal_id)))
    assert_error("HYBRID_SELF_APPROVAL_FORBIDDEN", lambda: boundary.prepare_exception_approval(
        actor, approver, command, prepared, proposed_at=AT, approved_at=LATER))


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("failure", ["inactive", "session", "role", "grant", "service", "revoked"])
def test_both_humans_are_freshly_reauthorized_and_generic_admin_does_not_imply_grants(
    setup, which, failure,
):
    world, boundary, authority, actor, approver, command = setup
    prepared = proposal(setup)
    human = authority.facts.humans[which]
    if failure in {"inactive", "session", "role"}:
        values = ({"is_active": False} if failure == "inactive" else
                  {"auth_version": 2} if failure == "session" else {"role": "LECTURER"})
        world[0].execute(update(User).where(User.id == human.user_id).values(**values)
                         .execution_options(synchronize_session=False))
    else:
        change = ({"grants": ()} if failure == "grant" else
                  {"human_principal_id": None} if failure == "service" else {"current": False})
        if failure == "grant":
            world[0].execute(update(User).where(User.id == human.user_id).values(role="ADMIN"))
        humans = list(authority.facts.humans)
        humans[which] = replace(human, **change)
        authority.facts = replace(authority.facts, humans=tuple(humans))
    with pytest.raises(APIError):
        boundary.prepare_exception_approval(
            actor, approver, command, prepared, proposed_at=AT, approved_at=LATER)


@pytest.mark.parametrize("reason", [None, "", "   ", "x" * 4001, "has\ncontrol", 123])
def test_reason_required_validated_and_never_identity_evidence(setup, reason):
    _, boundary, _, actor, _, command = setup
    command = replace(command, source=replace(command.source, reason=reason))
    assert_error("HYBRID_REASON_INVALID", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=AT))


@pytest.mark.parametrize("risk", [None, "", True, "I accept"])
def test_risk_acknowledgment_must_be_explicit_and_exact(setup, risk):
    _, boundary, _, actor, _, command = setup
    command = replace(command, risk_acknowledgment=risk)
    assert_error("HYBRID_RISK_ACKNOWLEDGMENT_REQUIRED", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=AT))


def test_hard_conflict_cannot_be_overridden_by_an_institutional_exception(setup):
    _, _, authority, _, _, _ = setup
    authority.facts = replace(authority.facts, hard_conflicts=(DenialReason.HARD_CONFLICT,))
    assert_error(DenialReason.HARD_CONFLICT, lambda: proposal(setup))


def test_actual_competing_source_ownership_remains_blocking_before_authority(setup):
    world, boundary, authority, actor, _, command = setup
    guide(world, [multi_row(1, [sid(1)]), multi_row(2, [sid(1)])],
          ts="2026-10-30T00:00:00Z")
    write(world, 501)
    command = replace(command, source=context(world, 501))
    assert_error("SOURCE_CLAIM_OWNERSHIP_CONFLICT", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=AT))
    assert authority.calls == 0


@pytest.mark.parametrize("status", ["REJECTED", "ACCEPTED", "SUPERSEDED"])
def test_negative_and_terminal_history_is_not_automatically_reassessed(setup, status):
    world, boundary, _, actor, _, command = setup
    world[0].execute(update(LecturerScopusCandidate).where(
        LecturerScopusCandidate.id == command.source.candidate_id).values(status=status))
    assert_error("CANDIDATE_ALREADY_DECIDED_CONFLICT", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=AT))


@pytest.mark.parametrize("version", [0, 1, 3, True, "2"])
def test_policy_version_mismatch_fails_closed(setup, version):
    _, boundary, _, actor, _, command = setup
    assert_error("HYBRID_POLICY_VERSION_MISMATCH", lambda: boundary.prepare_proposal(
        actor, replace(command, policy_version=version), proposed_at=AT))


@pytest.mark.parametrize("field", ["policy_id", "policy_version", "assurance_basis", "proposed_at",
                                   "source_revision", "reviewer", "final_acceptance"])
def test_rehashed_proposal_tampering_is_not_authoritative_replay(setup, field):
    _, boundary, _, actor, _, command = setup
    value = json.loads(proposal(setup).snapshot_json)
    if field == "source_revision":
        value["institutional_provenance"][0]["source_revision"] = "0" * 64
    elif field == "reviewer":
        value["reviewer"]["user_id"] = str(uid(999))
    else:
        value[field] = "tampered"
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_proposal(
        actor, command, receipt(value), proposed_at=AT))


@pytest.mark.parametrize("field", ["approver", "proposal_digest", "approved_at", "assurance_basis"])
def test_rehashed_approval_or_cross_proposal_substitution_is_refused(setup, field):
    _, boundary, _, actor, approver, command = setup
    prepared = proposal(setup)
    value = json.loads(approve(setup, prepared).snapshot_json)
    value[field] = "substituted"
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_exception_approval(
        actor, approver, command, prepared, receipt(value), proposed_at=AT, approved_at=LATER))


def test_newer_independent_facts_do_not_replace_an_old_proposal(setup):
    _, boundary, authority, actor, _, command = setup
    prepared = proposal(setup)
    # V2 precedence: newly qualifying independent evidence makes standard review
    # mandatory, so the stored exception draft cannot even be re-prepared.
    authority.facts = replace(authority.facts, independent=(independent(),))
    assert_error(DenialReason.STANDARD_AVAILABLE, lambda: boundary.verify_proposal(
        actor, command, prepared, proposed_at=AT))
    # A change that leaves the exception branch open still breaks the old replay.
    authority.facts = replace(authority.facts, independent=(
        independent(state=AssessmentState.INSUFFICIENT),))
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_proposal(
        actor, command, prepared, proposed_at=AT))


def test_authority_context_cannot_be_reused_for_a_different_candidate_or_reason(setup):
    _, boundary, _, actor, _, command = setup
    command = replace(command, source=replace(command.source, reason="Another review context"))
    assert_error("HYBRID_AUTHORITY_CONTEXT_MISMATCH", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=AT))


def test_source_withdrawal_and_new_capture_invalidate_old_proposal(setup):
    world, boundary, _, actor, _, command = setup
    prepared = proposal(setup)
    guide(world, rows=[], ts="2026-10-30T00:00:00Z")
    assert_error("STALE_SOURCE_CLAIM_DECISION_CONTEXT", lambda: boundary.verify_proposal(
        actor, command, prepared, proposed_at=AT))
    write(world, 501)
    assert_error("SOURCE_CLAIM_DECISION_NOT_CURRENT", lambda: boundary.prepare_proposal(
        actor, replace(command, source=context(world, 501)), proposed_at=AT))


def test_permission_revocation_invalidates_already_prepared_approval(setup):
    _, boundary, authority, actor, approver, command = setup
    prepared = proposal(setup)
    approval = approve(setup, prepared)
    first, second = authority.facts.humans
    authority.facts = replace(authority.facts, humans=(first, replace(second, grants=())))
    assert_error("HYBRID_EXCEPTION_PERMISSION_REQUIRED", lambda: boundary.verify_exception_approval(
        actor, approver, command, prepared, approval, proposed_at=AT, approved_at=LATER))


def test_duplicate_preparation_is_deterministic_and_creates_no_decisions(setup):
    world, _, authority, _, _, _ = setup
    first, second = proposal(setup), proposal(setup)
    assert first == second
    assert approve(setup, first) == approve(setup, second)
    assert authority.calls >= 4
    for model in (LecturerScopusIdentity, IdentityEvidence, LecturerScopusCandidateReview):
        assert world[0].scalars(select(model)).all() == []


@pytest.mark.parametrize("value", [None, "{}", [], PreparedSourceClaimDecision("[]", "0" * 64)])
def test_malformed_receipts_have_controlled_replay_failure(setup, value):
    _, boundary, _, actor, _, command = setup
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_proposal(
        actor, command, value, proposed_at=AT))


def test_caller_pending_state_and_prior_writes_survive_success_failure_and_retry(setup):
    world, boundary, authority, actor, _, command = setup
    db = world[0]
    earlier = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="Caller-owned")
    db.add(earlier)
    db.flush()
    pending = ScopusAuthor(id=uid(998), scopus_id=None, preferred_name="Invalid pending")
    db.add(pending)
    assert proposal(setup)
    authority.facts = replace(authority.facts, hard_conflicts=(DenialReason.HARD_CONFLICT,))
    assert_error(DenialReason.HARD_CONFLICT, lambda: proposal(setup))
    authority.facts = replace(authority.facts, hard_conflicts=())
    assert proposal(setup)
    assert pending in db.new and db.in_transaction() and db.is_active
    with db.no_autoflush:
        assert db.get(ScopusAuthor, earlier.id) is earlier
    db.rollback()  # Only owner controls outer rollback.
    assert db.get(ScopusAuthor, uid(999)) is None


def test_unexpected_authority_integrity_error_preserves_caller_transaction(setup, monkeypatch):
    world, _, authority, _, _, _ = setup
    earlier = ScopusAuthor(id=uid(999), scopus_id=sid(999), preferred_name="Caller-owned")
    world[0].add(earlier)
    world[0].flush()
    original = authority.load

    def fail(*args):
        raise IntegrityError("Synthetic read error", {}, RuntimeError("unexpected"))

    monkeypatch.setattr(authority, "load", fail)
    with pytest.raises(IntegrityError):
        proposal(setup)
    assert world[0].in_transaction() and world[0].get(ScopusAuthor, earlier.id) is earlier
    monkeypatch.setattr(authority, "load", original)
    assert proposal(setup)


def test_proposals_approvals_and_all_submit_boundaries_never_emit_decision_dml(setup):
    world, boundary, _, actor, _, command = setup
    statements = []

    def capture(conn, cursor, statement, *args):
        statements.append(statement.lstrip().upper())

    event.listen(world[0].get_bind(), "before_cursor_execute", capture)
    try:
        prepared = proposal(setup)
        approved = approve(setup, prepared)
        assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: boundary.submit(approved))
        assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: boundary.submit())
        base_boundary = SourceClaimDecisionBoundary(world[0])
        base = base_boundary.prepare(actor, command.source)
        assert_error("SOURCE_CLAIM_WORKFLOW_INACTIVE", lambda: base_boundary.submit(
            actor, command.source, base.snapshot_json, base.snapshot_hash))
    finally:
        event.remove(world[0].get_bind(), "before_cursor_execute", capture)
    assert any(s.startswith("SAVEPOINT") for s in statements)
    assert any(s.startswith("ROLLBACK TO SAVEPOINT") for s in statements)
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE", "COMMIT")) for s in statements)


def test_safe_snapshot_has_no_raw_source_rows_or_account_secrets(setup):
    text = approve(setup).snapshot_json
    for private in ("password_hash", "record_raw", "record_email", "gv1@example.invalid",
                    "approver@example.invalid", "upstream_storage_ref"):
        assert private not in text


@pytest.mark.parametrize("moment", [None, AT.replace(tzinfo=None), "2026-10-30"])
def test_naive_or_invalid_proposal_time_is_rejected(setup, moment):
    _, boundary, _, actor, _, command = setup
    assert_error("HYBRID_TIMESTAMP_INVALID", lambda: boundary.prepare_proposal(
        actor, command, proposed_at=moment))


def test_approval_cannot_predate_proposal(setup):
    _, boundary, _, actor, approver, command = setup
    assert_error("HYBRID_TIMESTAMP_INVALID", lambda: boundary.prepare_exception_approval(
        actor, approver, command, proposal(setup),
        proposed_at=AT, approved_at=AT-timedelta(days=1)))


def test_pure_evaluator_distinguishes_insufficiency_from_conflict():
    missing = evaluate_hybrid_policy((), provenance_verified=True)
    assert missing.standard_denials == (DenialReason.INDEPENDENT_MISSING,)
    assert missing.exception_proposal_eligible
    conflict = evaluate_hybrid_policy(
        (independent(state=AssessmentState.CONTRADICTORY),), provenance_verified=True)
    assert conflict.exception_denials == (DenialReason.HARD_CONFLICT,)
    assert not conflict.standard_eligible and not conflict.exception_proposal_eligible


@pytest.mark.parametrize("kind", ["default", "wrong_context", "duplicate", "untyped_state"])
def test_malformed_authority_output_cannot_be_used_as_an_attestation(setup, kind):
    _, _, authority, _, _, _ = setup
    if kind == "default":
        authority.facts = None
    elif kind == "wrong_context":
        authority.facts = replace(authority.facts, context_digest="0" * 64)
    elif kind == "duplicate":
        authority.facts = replace(authority.facts, humans=authority.facts.humans * 2)
    else:
        authority.facts = replace(authority.facts, independent=(
            replace(independent(), state="QUALIFYING"),))
    with pytest.raises(APIError):
        proposal(setup)


def test_revoked_institutional_source_blocks_even_independently_supported_standard(setup):
    _, boundary, authority, actor, _, command = setup
    authority.facts = replace(
        authority.facts, independent=(independent(),), authenticity=tuple(
            replace(a, state=SourceAuthenticityState.REVOKED)
            for a in authority.facts.authenticity))
    assert_error("HYBRID_SOURCE_REVOKED", lambda: boundary.prepare_proposal(
        actor, standard(command), proposed_at=AT))


def test_new_authenticity_verification_does_not_rewrite_a_captured_proposal(setup):
    _, boundary, authority, actor, _, command = setup
    prepared = proposal(setup)
    authority.facts = replace(authority.facts, authenticity=tuple(
        replace(a, verification_digest="8" * 64) for a in authority.facts.authenticity))
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_proposal(
        actor, command, prepared, proposed_at=AT))


@pytest.mark.parametrize("another_lecturer", [False, True])
def test_approval_is_bound_to_exact_candidate_pair_and_source_context(setup, another_lecturer):
    world, boundary, authority, actor, approver, command = setup
    db = world[0]
    lecturer_number = 2 if another_lecturer else 1
    guide(world, [multi_row(1, [sid(1)]), multi_row(lecturer_number, [sid(2)])],
          ts="2026-10-30T00:00:00Z")
    write(world, 501)
    artifacts = db.scalars(select(SourceArtifact)).all()
    template = authority.facts.authenticity[0]
    authority.facts = replace(authority.facts, authenticity=tuple(
        replace(template, artifact_id=a.id, artifact_digest=a.artifact_bytes_sha256)
        for a in artifacts))
    command = replace(command, source=context(world, 501))
    base = SourceClaimDecisionBoundary(db).prepare(actor, command.source)
    authority.facts = replace(authority.facts, context_digest=base.snapshot_hash)
    original_proposal = boundary.prepare_proposal(actor, command, proposed_at=AT)
    original_approval = boundary.prepare_exception_approval(
        actor, approver, command, original_proposal, proposed_at=AT, approved_at=LATER)
    # Resolve the other root's observation from stored source output, not a name match.
    from app.models.candidate import LecturerScopusCandidateObservation

    root = db.scalar(select(LecturerScopusCandidate).where(
        LecturerScopusCandidate.lecturer_id == uid(lecturer_number),
        LecturerScopusCandidate.scopus_author_id == uid(102)))
    obs = db.scalar(select(LecturerScopusCandidateObservation).where(
        LecturerScopusCandidateObservation.candidate_id == root.id,
        LecturerScopusCandidateObservation.generation_run_id == uid(501)))
    other_command = replace(command, source=replace(command.source, candidate_id=root.id,
                                                   observation_id=obs.id))
    other_base = SourceClaimDecisionBoundary(db).prepare(actor, other_command.source)
    authority.facts = replace(authority.facts, context_digest=other_base.snapshot_hash)
    other_proposal = boundary.prepare_proposal(actor, other_command, proposed_at=AT)
    assert_error("HYBRID_REPLAY_INVALID", lambda: boundary.verify_exception_approval(
        actor, approver, other_command, other_proposal, original_approval,
        proposed_at=AT, approved_at=LATER))

