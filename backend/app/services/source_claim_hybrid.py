"""SOURCE_CLAIM HYBRID V2: read-only drafts, never production decisions.

No production authority adapter exists. Default deny; test authorities are synthetic.
No route, evidence promotion, activation flag or canonical mutation.

V2 (gate B2-D) adds deterministic **branch precedence**: a qualifying independent
assessment makes STANDARD_INDEPENDENT mandatory, so the institutional-exception branch
can never be chosen as a downgrade around standard review. That changes policy meaning,
so the revision is bumped and ``POLICY_DIGEST`` binds the exact parameters a draft was
prepared under; a v1 receipt does not replay against v2.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.source_staging import SourceArtifact, SourceCapture, SourceClaim, SourceRecord
from app.services.matching.candidate_persistence import canonical_json, sha256_json
from app.services.source_claim_decision_boundary import (
    PreparedSourceClaimDecision,
    SourceClaimAcceptContext,
    SourceClaimDecisionBoundary,
    _authorize,
)

POLICY_ID = "SOURCE_CLAIM_HYBRID_V1"
POLICY_FAMILY = "SOURCE_CLAIM_HYBRID"
POLICY_VERSION = 2
POLICY_ENCODER = "CANONICAL_JSON_V1"
RISK_ACKNOWLEDGMENT = "INSTITUTIONAL_DECLARATION_IS_NOT_INDEPENDENT_VERIFICATION"
# These are existing vocabulary references, never automatic qualification rules.
_STRONG_TYPES = {"ORCID_EXACT", "DOI_EXACT", "PUBLICATION_OVERLAP", "COAUTHOR_CONFIRMED"}
_HEX = re.compile(r"^[0-9a-f]{64}$")


class ReviewBranch(StrEnum):
    STANDARD_INDEPENDENT = "STANDARD_INDEPENDENT"
    INSTITUTIONAL_EXCEPTION = "INSTITUTIONAL_EXCEPTION"


class AssuranceBasis(StrEnum):
    INDEPENDENT_VERIFIED = "INDEPENDENT_VERIFIED"
    INSTITUTIONAL_EXCEPTION = "INSTITUTIONAL_EXCEPTION"


class AssessmentState(StrEnum):
    QUALIFYING = "QUALIFYING"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"
    WITHDRAWN = "WITHDRAWN"
    CONTRADICTORY = "CONTRADICTORY"


class Grant(StrEnum):
    PROPOSE_EXCEPTION = "SOURCE_CLAIM_EXCEPTION_PROPOSE"
    APPROVE_EXCEPTION = "SOURCE_CLAIM_EXCEPTION_APPROVE"


class SourceAuthenticityState(StrEnum):
    CURRENT = "CURRENT"
    UNVERIFIED = "UNVERIFIED"
    REVOKED = "REVOKED"


class DenialReason(StrEnum):
    INDEPENDENT_MISSING = "INDEPENDENT_EVIDENCE_INSUFFICIENT"
    INDEPENDENT_INVALID = "INDEPENDENT_EVIDENCE_INVALID"
    INDEPENDENT_WITHDRAWN = "INDEPENDENT_EVIDENCE_WITHDRAWN"
    HARD_CONFLICT = "UNRESOLVED_HARD_CONFLICT"
    PROVENANCE_UNVERIFIED = "INSTITUTIONAL_PROVENANCE_UNVERIFIED"
    STANDARD_AVAILABLE = "STANDARD_INDEPENDENT_REVIEW_REQUIRED"


# Reported denial, worst first: a blocking conflict always outranks "use the other
# branch", which in turn outranks a plain lack of evidence. Alphabetical order would
# report an incidental reason and hide the one that actually governs.
_DENIAL_PRECEDENCE = (DenialReason.HARD_CONFLICT, DenialReason.INDEPENDENT_INVALID,
                      DenialReason.INDEPENDENT_WITHDRAWN, DenialReason.STANDARD_AVAILABLE,
                      DenialReason.PROVENANCE_UNVERIFIED, DenialReason.INDEPENDENT_MISSING)


def _first_denial(denials):
    for reason in _DENIAL_PRECEDENCE:
        if reason in denials:
            return reason
    return DenialReason.HARD_CONFLICT


@dataclass(frozen=True, slots=True)
class IndependentAssessment:
    """Trusted verifier OUTPUT, not a request DTO or an IdentityEvidence writer."""
    receipt_id: uuid.UUID
    receipt_digest: str
    evidence_type: str
    state: AssessmentState
    independently_verified: bool


@dataclass(frozen=True, slots=True)
class HumanAuthority:
    user_id: uuid.UUID
    human_principal_id: uuid.UUID | None
    auth_version: int
    current: bool
    grants: tuple[Grant, ...]
    attestation_id: uuid.UUID
    revision_digest: str


@dataclass(frozen=True, slots=True)
class SourceAuthenticity:
    artifact_id: uuid.UUID
    artifact_digest: str
    issuing_organization: str
    state: SourceAuthenticityState
    verification_id: uuid.UUID
    verification_digest: str
    verification_method: str


@dataclass(frozen=True, slots=True)
class AuthorityFacts:
    context_digest: str
    revision_digest: str
    independent: tuple[IndependentAssessment, ...] = ()
    humans: tuple[HumanAuthority, ...] = ()
    authenticity: tuple[SourceAuthenticity, ...] = ()
    hard_conflicts: tuple[DenialReason, ...] = ()


class HybridAuthority(Protocol):
    def load(self, view: Session, context_digest: str) -> AuthorityFacts:
        """Resolve CURRENT authoritative facts, never caller-supplied facts.

        Must be read-only and must authenticate institutional issuance, verifier
        receipts, human linkage and explicit grants. No production implementation
        is supplied by this gate; the repository lacks these capabilities.
        """
        ...


@dataclass(frozen=True, slots=True)
class AuthorityRequest:
    """The trusted scope of one authority lookup, derived only from the server context.

    Nothing here is caller input, so an authority lookup can never be widened to
    another pair, another account or another artifact than the revalidated context.
    """

    context_digest: str
    candidate_id: uuid.UUID
    candidate_version: int
    lecturer_id: uuid.UUID
    scopus_author_id: uuid.UUID
    claimed_scopus_ids: tuple[str, ...]
    artifact_ids: tuple[uuid.UUID, ...]
    user_ids: tuple[uuid.UUID, ...]


@runtime_checkable
class ScopedHybridAuthority(Protocol):
    """A ``HybridAuthority`` that takes the full scope instead of only a digest.

    Preferred when the adapter offers it; a digest-only authority still works. The
    returned facts are validated identically either way.
    """

    def load_scoped(self, view: Session, request: AuthorityRequest) -> AuthorityFacts: ...


class UnavailableAuthority:
    def load(self, view, context_digest):
        raise _deny("HYBRID_AUTHORITY_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class InstitutionalProvenance:
    source_system: str
    source_record_id: uuid.UUID
    lecturer_id: uuid.UUID
    scopus_author_id: uuid.UUID
    claimed_scopus_id: str
    capture_id: uuid.UUID
    artifact_id: uuid.UUID
    analysis_id: uuid.UUID
    claim_id: uuid.UUID
    captured_at: str
    source_revision: str
    source_record_digest: str
    immutable_snapshot_digest: str
    validity: str
    verification: SourceAuthenticity | None
    source_tier: str = "INSTITUTION_DECLARED"
    evidence_kind: str = "SOURCE_CLAIM"


@dataclass(frozen=True, slots=True)
class HybridEligibility:
    standard_eligible: bool
    exception_proposal_eligible: bool
    standard_denials: tuple[DenialReason, ...]
    exception_denials: tuple[DenialReason, ...]
    # The single branch the policy allows, or None when neither path is open. Both can
    # never be eligible at once: precedence resolves it before the reviewer chooses.
    required_branch: ReviewBranch | None = None


@dataclass(frozen=True, slots=True)
class HybridCommand:
    source: SourceClaimAcceptContext
    branch: ReviewBranch = ReviewBranch.STANDARD_INDEPENDENT
    policy_id: str = POLICY_ID
    policy_version: int = POLICY_VERSION
    risk_acknowledgment: str | None = None


def _deny(code, status=409):
    return APIError(status_code=status, code=code,
                    detail="Hybrid SOURCE_CLAIM context is unavailable or not authorized.")


def _require(condition, code="HYBRID_AUTHORITY_FACTS_INVALID"):
    if not condition:
        raise _deny(code)


def _hex(value):
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def _moment(value):
    _require(isinstance(value, datetime) and value.utcoffset() is not None,
             "HYBRID_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _facts(value, context_digest):
    _require(isinstance(value, AuthorityFacts))
    _require(value.context_digest == context_digest and _hex(value.revision_digest),
             "HYBRID_AUTHORITY_CONTEXT_MISMATCH")
    for items, kind, key in ((value.independent, IndependentAssessment, "receipt_id"),
                             (value.humans, HumanAuthority, "user_id"),
                             (value.authenticity, SourceAuthenticity, "artifact_id")):
        _require(isinstance(items, tuple) and all(isinstance(i, kind) for i in items))
        _require(all(isinstance(getattr(i, key), uuid.UUID) for i in items))
        _require(len({getattr(i, key) for i in items}) == len(items))
    _require(isinstance(value.hard_conflicts, tuple) and all(
        isinstance(c, DenialReason) and c == DenialReason.HARD_CONFLICT
        for c in value.hard_conflicts))
    for item in value.independent:
        _require(_hex(item.receipt_digest) and isinstance(item.evidence_type, str)
                 and isinstance(item.state, AssessmentState)
                 and type(item.independently_verified) is bool)
    for item in value.humans:
        _require((item.human_principal_id is None
                  or isinstance(item.human_principal_id, uuid.UUID))
                 and type(item.auth_version) is int and item.auth_version >= 1
                 and type(item.current) is bool and isinstance(item.grants, tuple)
                 and all(isinstance(g, Grant) for g in item.grants)
                 and len(set(item.grants)) == len(item.grants)
                 and isinstance(item.attestation_id, uuid.UUID) and _hex(item.revision_digest))
    for item in value.authenticity:
        _require(_hex(item.artifact_digest) and _hex(item.verification_digest)
                 and isinstance(item.verification_id, uuid.UUID)
                 and isinstance(item.state, SourceAuthenticityState)
                 and item.issuing_organization == "ICTU"
                 and item.verification_method == "FORMALLY_VERIFIED_ISSUANCE_V1")
    return value


def evaluate_hybrid_policy(independent, *, provenance_verified, hard_conflicts=()):
    """Pure policy over validated authority OUTPUT; not an evidence verifier.

    A type/DOI/ORCID/string alone never qualifies. Invalid, withdrawn and
    contradictory assessments are not a lack-of-evidence exception.
    """
    _require(isinstance(independent, tuple)
             and all(isinstance(i, IndependentAssessment) for i in independent)
             and type(provenance_verified) is bool
             and isinstance(hard_conflicts, tuple)
             and all(c == DenialReason.HARD_CONFLICT for c in hard_conflicts))
    common = set(hard_conflicts)
    qualifies = False
    for item in independent:
        _require(isinstance(item.state, AssessmentState)
                 and type(item.independently_verified) is bool)
        if item.state == AssessmentState.CONTRADICTORY:
            common.add(DenialReason.HARD_CONFLICT)
        elif item.state == AssessmentState.INVALID:
            common.add(DenialReason.INDEPENDENT_INVALID)
        elif item.state == AssessmentState.WITHDRAWN:
            common.add(DenialReason.INDEPENDENT_WITHDRAWN)
        elif item.state == AssessmentState.QUALIFYING:
            if item.independently_verified and item.evidence_type in _STRONG_TYPES:
                qualifies = True
            else:
                common.add(DenialReason.INDEPENDENT_INVALID)
    standard, exception = set(common), set(common)
    if not qualifies and not common:
        standard.add(DenialReason.INDEPENDENT_MISSING)
    if qualifies:
        # Branch precedence. Qualifying independent evidence makes standard review the
        # only open path: the exception branch is for insufficiency, not for avoiding
        # the stricter review, so it is denied here even with valid provenance.
        exception.add(DenialReason.STANDARD_AVAILABLE)
    if not provenance_verified:
        exception.add(DenialReason.PROVENANCE_UNVERIFIED)
    required = (ReviewBranch.STANDARD_INDEPENDENT if not standard else
                ReviewBranch.INSTITUTIONAL_EXCEPTION if not exception else None)
    return HybridEligibility(not standard, not exception, tuple(sorted(standard)),
                             tuple(sorted(exception)), required)


def policy_document():
    """The exact parameters a draft is prepared under; its hash is ``POLICY_DIGEST``.

    Persisted history binds this digest, so a later policy change cannot be applied
    retroactively to an already recorded decision, and an old receipt stops replaying.
    """
    return {
        "policy_family": POLICY_FAMILY, "policy_id": POLICY_ID,
        "policy_revision": POLICY_VERSION, "encoder_version": POLICY_ENCODER,
        "branch_precedence": [ReviewBranch.STANDARD_INDEPENDENT.value,
                              ReviewBranch.INSTITUTIONAL_EXCEPTION.value],
        "qualifying_independent_types": sorted(_STRONG_TYPES),
        "exception_requires_independent_insufficiency": True,
        "hard_conflict_blocks_every_branch": True,
        "denial_precedence": [r.value for r in _DENIAL_PRECEDENCE],
        "required_exception_grants": sorted(g.value for g in Grant),
        "risk_acknowledgment": RISK_ACKNOWLEDGMENT,
        "dual_control_distinct_human_principals": 2,
        "final_acceptance_enabled": False,
        "workflow_active": False,
    }


def _human(facts, actor, *, grant=None):
    human = next((h for h in facts.humans if h.user_id == actor.user_id), None)
    _require(human is not None and human.current
             and human.auth_version == actor.auth_version
             and human.human_principal_id is not None, "HYBRID_HUMAN_AUTHORIZATION_REQUIRED")
    if grant is not None:
        _require(grant in human.grants, "HYBRID_EXCEPTION_PERMISSION_REQUIRED")
    return human


def _provenance(view, base, authenticity):
    snapshot = json.loads(base.snapshot_json)
    pair = snapshot["candidate"]
    authorizations = {a.artifact_id: a for a in authenticity}
    result = {}
    for item in snapshot["evidence"]:
        for ref in item["source_refs"]:
            if ref["selection_status"] != "ACTIVE_PROJECTION":
                continue
            artifact_id = uuid.UUID(ref["artifact_id"])
            artifact = view.get(SourceArtifact, artifact_id)
            capture = view.get(SourceCapture, uuid.UUID(ref["capture_id"]))
            record = view.get(SourceRecord, uuid.UUID(ref["record_id"]))
            claim = view.get(SourceClaim, uuid.UUID(ref["claim_id"]))
            _require(all(r is not None for r in (artifact, capture, record, claim)),
                     "HYBRID_PROVENANCE_INVALID")
            _require(artifact.capture_id == capture.id
                     and artifact.content_id == capture.content_id
                     and record.analysis_id == claim.analysis_id == uuid.UUID(ref["analysis_id"])
                     and claim.record_id == record.id and claim.claim_type == "SCOPUS_ID_OWNED"
                     and claim.value_normalized == item["scopus_id"]
                     and record.validation_status != "INVALID"
                     and capture.source_system == item["source_system"]
                     and _hex(artifact.artifact_bytes_sha256) and _hex(record.record_hash),
                     "HYBRID_PROVENANCE_INVALID")
            verification = authorizations.get(artifact_id)
            if verification is not None:
                _require(verification.artifact_digest == artifact.artifact_bytes_sha256,
                         "HYBRID_PROVENANCE_INVALID")
            provenance = InstitutionalProvenance(
                item["source_system"], record.id, uuid.UUID(pair["lecturer_id"]),
                uuid.UUID(pair["scopus_author_id"]), item["scopus_id"], capture.id, artifact.id,
                uuid.UUID(ref["analysis_id"]), claim.id, ref["captured_at"],
                artifact.artifact_bytes_sha256, record.record_hash,
                artifact.artifact_bytes_sha256, item["current_state"], verification)
            result[canonical_json(asdict(provenance))] = provenance
    _require(bool(result), "HYBRID_PROVENANCE_MISSING")
    return tuple(result[k] for k in sorted(result))


def _scope(base, user_ids):
    """Derive the authority lookup scope from the trusted source snapshot alone."""
    snapshot = json.loads(base.snapshot_json)
    pair = snapshot["candidate"]
    artifacts, claimed = set(), set()
    for item in snapshot["evidence"]:
        claimed.add(item["scopus_id"])
        for ref in item["source_refs"]:
            if ref["selection_status"] == "ACTIVE_PROJECTION":
                artifacts.add(uuid.UUID(ref["artifact_id"]))
    accounts = tuple(dict.fromkeys(user_ids))
    _require(bool(accounts) and all(isinstance(a, uuid.UUID) for a in accounts),
             "HYBRID_COMMAND_INVALID")
    return AuthorityRequest(
        base.snapshot_hash, uuid.UUID(pair["id"]), pair["version"],
        uuid.UUID(pair["lecturer_id"]), uuid.UUID(pair["scopus_author_id"]),
        tuple(sorted(claimed)), tuple(sorted(artifacts, key=str)), accounts)


def _receipt(snapshot):
    return PreparedSourceClaimDecision(canonical_json(snapshot), sha256_json(snapshot))


def _compare(supplied, trusted):
    try:
        _require(isinstance(supplied, PreparedSourceClaimDecision), "HYBRID_REPLAY_INVALID")
        value = json.loads(supplied.snapshot_json)
        _require(isinstance(value, dict)
                 and sha256_json(value) == supplied.snapshot_hash == trusted.snapshot_hash
                 and canonical_json(value) == trusted.snapshot_json, "HYBRID_REPLAY_INVALID")
    except (TypeError, ValueError) as exc:
        raise _deny("HYBRID_REPLAY_INVALID") from exc
    return trusted


def verify_receipt(supplied, trusted):
    """Compare a caller-held draft against a freshly prepared trusted receipt.

    The trusted receipt is what callers may act on; the supplied one only ever has to
    match it exactly, byte for byte and hash for hash.
    """
    return _compare(supplied, trusted)


POLICY_DIGEST = sha256_json(policy_document())


class HybridSourceClaimCompatibility:
    """Offline port only. No production adapter, grant storage or finalization."""

    def __init__(self, session: Session, *, authority: HybridAuthority | None = None):
        self.session = session
        self.authority = authority if authority is not None else UnavailableAuthority()

    def _load(self, view, request):
        """Prefer the scoped port; a digest-only authority still gets the same checks."""
        if isinstance(self.authority, ScopedHybridAuthority):
            return self.authority.load_scoped(view, request)
        return self.authority.load(view, request.context_digest)

    def authorize_principals(self, view, actors, request, *, grant):
        """Freshly authorize several distinct humans at one action boundary.

        Stored account state and authority facts are both re-read here, so an action
        cannot ride on authorization captured earlier in the session. Distinctness is
        checked on the human principal as well as the account, which is what stops one
        person with two accounts from satisfying dual control.
        """
        facts = _facts(self._load(view, request), request.context_digest)
        humans = []
        for actor in actors:
            _authorize(view, actor)
            humans.append(_human(facts, actor, grant=grant))
        _require(len({h.user_id for h in humans}) == len(humans)
                 and len({h.human_principal_id for h in humans}) == len(humans),
                 "HYBRID_SELF_APPROVAL_FORBIDDEN")
        return facts, tuple(humans)

    def _prepare(self, view, actor, command, proposed_at, *, co_actors=()):
        _require(isinstance(command, HybridCommand)
                 and command.policy_id == POLICY_ID
                 and type(command.policy_version) is int
                 and command.policy_version == POLICY_VERSION, "HYBRID_POLICY_VERSION_MISMATCH")
        _require(isinstance(command.branch, ReviewBranch)
                 and isinstance(command.source, SourceClaimAcceptContext), "HYBRID_COMMAND_INVALID")
        reason = command.source.reason
        _require(isinstance(reason, str) and bool(reason.strip()) and len(reason) <= 4000
                 and not any(ord(c) < 32 or ord(c) == 127 for c in reason), "HYBRID_REASON_INVALID")
        moment = _moment(proposed_at)
        user = _authorize(view, actor)
        base = SourceClaimDecisionBoundary._prepare(view, user, command.source)
        request = _scope(base, (actor.user_id, *(a.user_id for a in co_actors)))
        facts = _facts(self._load(view, request), base.snapshot_hash)
        reviewer = _human(facts, actor, grant=(
            Grant.PROPOSE_EXCEPTION if command.branch == ReviewBranch.INSTITUTIONAL_EXCEPTION
            else None))
        provenance = _provenance(view, base, facts.authenticity)
        _require(not any(p.verification is not None
                         and p.verification.state == SourceAuthenticityState.REVOKED
                         for p in provenance), "HYBRID_SOURCE_REVOKED")
        verified = all(p.verification is not None
                       and p.verification.state == SourceAuthenticityState.CURRENT
                       for p in provenance)
        independent = tuple(sorted(facts.independent, key=lambda i: str(i.receipt_id)))
        eligibility = evaluate_hybrid_policy(
            independent, provenance_verified=verified, hard_conflicts=facts.hard_conflicts)
        if command.branch == ReviewBranch.INSTITUTIONAL_EXCEPTION:
            _require(command.risk_acknowledgment == RISK_ACKNOWLEDGMENT,
                     "HYBRID_RISK_ACKNOWLEDGMENT_REQUIRED")
            _require(eligibility.exception_proposal_eligible,
                     _first_denial(eligibility.exception_denials))
            assurance = AssuranceBasis.INSTITUTIONAL_EXCEPTION
        else:
            _require(command.risk_acknowledgment is None, "HYBRID_COMMAND_INVALID")
            _require(eligibility.standard_eligible, _first_denial(eligibility.standard_denials))
            assurance = AssuranceBasis.INDEPENDENT_VERIFIED
        # The resolved branch is the one the policy allows; the command may only agree.
        _require(eligibility.required_branch == command.branch, "HYBRID_BRANCH_PRECEDENCE")
        snapshot = {
            "schema_version": 2, "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
            "policy_family": POLICY_FAMILY, "policy_digest": POLICY_DIGEST,
            "branch": command.branch, "assurance_basis": assurance,
            "outcome": "OFFLINE_PROPOSAL_PREPARED", "workflow_active": False,
            "decision_enabled": False, "final_acceptance": False, "simulation_only": True,
            "proposed_at": moment.isoformat(), "approved_at": None,
            "reviewer": asdict(reviewer), "approver": None, "reason": reason.strip(),
            "risk_acknowledgment": command.risk_acknowledgment,
            "source_context_hash": base.snapshot_hash,
            "source_context": json.loads(base.snapshot_json),
            "authority_revision_digest": facts.revision_digest,
            "institutional_provenance": [asdict(p) for p in provenance],
            "independent_assessments": [asdict(i) for i in independent],
            "conflict_evaluation": {"hard_conflicts": sorted(set(facts.hard_conflicts)),
                                    "eligibility": asdict(eligibility)},
            "revocation_or_supersession_ref": None,
        }
        return _receipt(snapshot), facts, reviewer

    def prepare_proposal(self, actor, command, *, proposed_at):
        with self.session.no_autoflush:
            with Session(bind=self.session.connection(), autoflush=False,
                         join_transaction_mode="create_savepoint") as view:
                receipt, _, _ = self._prepare(view, actor, command, proposed_at)
                return receipt

    def verify_proposal(self, actor, command, receipt, *, proposed_at):
        return _compare(receipt, self.prepare_proposal(actor, command, proposed_at=proposed_at))

    def prepare_exception_approval(self, reviewer_actor, approver_actor, command, proposal,
                                   *, proposed_at, approved_at):
        """A distinct human validates an offline draft; no state/decision write."""
        _require(isinstance(command, HybridCommand)
                 and command.branch == ReviewBranch.INSTITUTIONAL_EXCEPTION,
                 "HYBRID_APPROVAL_NOT_APPLICABLE")
        with self.session.no_autoflush:
            with Session(bind=self.session.connection(), autoflush=False,
                         join_transaction_mode="create_savepoint") as view:
                # Fresh stored authorization for BOTH humans at this action boundary.
                _authorize(view, approver_actor)
                trusted, facts, reviewer = self._prepare(
                    view, reviewer_actor, command, proposed_at, co_actors=(approver_actor,))
                _compare(proposal, trusted)
                approver = _human(facts, approver_actor, grant=Grant.APPROVE_EXCEPTION)
                _require(approver.user_id != reviewer.user_id
                         and approver.human_principal_id != reviewer.human_principal_id,
                         "HYBRID_SELF_APPROVAL_FORBIDDEN")
                moment = _moment(approved_at)
                _require(moment >= _moment(proposed_at), "HYBRID_TIMESTAMP_INVALID")
                snapshot = json.loads(trusted.snapshot_json)
                snapshot.update(outcome="OFFLINE_APPROVAL_VALIDATED",
                                approved_at=moment.isoformat(),
                                approver=asdict(approver), proposal_digest=trusted.snapshot_hash)
                return _receipt(snapshot)

    def verify_exception_approval(self, reviewer_actor, approver_actor, command, proposal, approval,
                                  *, proposed_at, approved_at):
        trusted = self.prepare_exception_approval(
            reviewer_actor, approver_actor, command, proposal,
            proposed_at=proposed_at, approved_at=approved_at)
        return _compare(approval, trusted)

    def submit(self, *args, **kwargs):
        """No draft/authority/direct function can enable production acceptance."""
        raise _deny("SOURCE_CLAIM_WORKFLOW_INACTIVE")

