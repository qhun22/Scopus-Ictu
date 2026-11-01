"""B2-D authority integration contracts: fail-closed by default.

The adapters marked SYNTHETIC below exist only to exercise the composition contract.
They authenticate nothing, and ``test_a_non_authoritative_adapter_is_refused_in_production``
is the guard that keeps them out of a production environment.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.core.exceptions import APIError
from app.models.source_staging import SourceArtifact
from app.services.source_claim_authority import (
    AuthorityKind,
    AuthorityRequest,
    CapabilityGrant,
    HybridAuthorityGateway,
    PrincipalAttestation,
    StagingSourceLineageAuthority,
    UnavailableExceptionAuthorizationAuthority,
    UnavailableHumanPrincipalRegistry,
    UnavailableIndependentEvidenceAuthority,
    UnavailableInstitutionalSourceAuthority,
    assert_production_safe,
    default_hybrid_authority,
    integration_report,
)
from app.services.source_claim_hybrid import (
    AssessmentState,
    Grant,
    HybridSourceClaimCompatibility,
    IndependentAssessment,
    ReviewBranch,
    ScopedHybridAuthority,
    SourceAuthenticity,
    SourceAuthenticityState,
)
from tests.unit.test_source_claim_candidate_persistence import world as world  # noqa: F401
from tests.unit.test_source_claim_decision_boundary import assert_error
from tests.unit.test_source_claim_hybrid import AT
from tests.unit.test_source_claim_hybrid import setup as setup  # noqa: F401


def request_for(context_digest="a" * 64, *, artifacts=(), users=()):
    return AuthorityRequest(context_digest, uuid.uuid4(), 1, uuid.uuid4(), uuid.uuid4(),
                            ("57000000001",), tuple(artifacts), tuple(users))


# --- SYNTHETIC adapters: contract exercise only, never authority ------------

class SyntheticRegistry:
    integration = replace(UnavailableHumanPrincipalRegistry.integration,
                          adapter="SyntheticRegistry")

    def __init__(self, attestations):
        self.attestations = attestations

    def principals(self, view, request):
        return self.attestations


class SyntheticIndependent:
    integration = replace(UnavailableIndependentEvidenceAuthority.integration,
                          adapter="SyntheticIndependent")

    def __init__(self, assessments=()):
        self.assessments_ = assessments

    def assessments(self, view, request):
        return self.assessments_


class SyntheticIssuance:
    integration = replace(UnavailableInstitutionalSourceAuthority.integration,
                          adapter="SyntheticIssuance")

    def __init__(self, attestations=()):
        self.attestations = attestations

    def issuance(self, view, request):
        return self.attestations


def attestation(user_id, principal_id=None, *, current=True, auth_version=1):
    return PrincipalAttestation(user_id, principal_id or uuid.uuid4(), current, auth_version,
                                uuid.uuid4(), "1" * 64)


def grant(user_id, principal_id, permission=Grant.PROPOSE_EXCEPTION, *, current=True):
    return CapabilityGrant(user_id, principal_id, permission, uuid.uuid4(), current, "2" * 64)


class SyntheticGrantAuthority:
    integration = replace(UnavailableExceptionAuthorizationAuthority.integration,
                          adapter="SyntheticGrantAuthority")

    def __init__(self, grants=()):
        self.held = grants

    def grants(self, view, request):
        return self.held


# ---------------------------------------------------------------------------
# Fail-closed defaults
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("adapter", "call", "kind"), [
    (UnavailableInstitutionalSourceAuthority(), "issuance",
     AuthorityKind.INSTITUTIONAL_SOURCE),
    (UnavailableIndependentEvidenceAuthority(), "assessments",
     AuthorityKind.INDEPENDENT_EVIDENCE),
    (UnavailableHumanPrincipalRegistry(), "principals",
     AuthorityKind.HUMAN_PRINCIPAL_REGISTRY),
    (UnavailableExceptionAuthorizationAuthority(), "grants",
     AuthorityKind.EXCEPTION_AUTHORIZATION),
])
def test_each_missing_authority_fails_closed_with_its_own_code(adapter, call, kind):
    with pytest.raises(APIError) as exc:
        getattr(adapter, call)(None, request_for())
    assert exc.value.data["authority"] == str(kind)
    assert exc.value.data["missing_integration"]
    assert adapter.integration.production_authoritative is False


def test_the_default_gateway_refuses_because_no_verifier_exists():
    gateway = default_hybrid_authority(environment="test")
    assert isinstance(gateway, ScopedHybridAuthority)
    with pytest.raises(APIError) as exc:
        gateway.load_scoped(None, request_for())
    # Institutional lineage resolves; the independent verifier is the first true gap.
    assert exc.value.code == "SOURCE_CLAIM_INDEPENDENT_AUTHORITY_UNAVAILABLE"


def test_a_digest_without_scope_cannot_resolve_any_authority():
    with pytest.raises(APIError):
        default_hybrid_authority(environment="test").load(None, "b" * 64)


@pytest.mark.parametrize("bad", [None, "short", request_for("A" * 64)])
def test_a_malformed_authority_request_is_refused(bad):
    with pytest.raises(APIError):
        default_hybrid_authority(environment="test").load_scoped(None, bad)


def test_integration_report_names_every_missing_production_integration():
    report = integration_report()
    assert [r["authority"] for r in report] == [
        "INSTITUTIONAL_SOURCE", "INDEPENDENT_EVIDENCE",
        "HUMAN_PRINCIPAL_REGISTRY", "EXCEPTION_AUTHORIZATION"]
    assert all(r["production_authoritative"] is False for r in report)
    assert all(r["missing_integration"] for r in report)


def test_a_non_authoritative_adapter_is_refused_in_production():
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=SyntheticIndependent(),
        registry=SyntheticRegistry(()), authorization=SyntheticGrantAuthority(),
        environment="prod")
    with pytest.raises(APIError) as exc:
        gateway.load_scoped(None, request_for())
    assert exc.value.code == "SOURCE_CLAIM_AUTHORITY_NOT_PRODUCTION_READY"
    assert len(exc.value.data["adapters"]) == 4
    # The same wiring is permitted outside production, which is what offline gates use.
    assert_production_safe(gateway.integrations, environment="local")


# ---------------------------------------------------------------------------
# Composition rules
# ---------------------------------------------------------------------------

def test_a_grant_bound_to_another_human_is_refused():
    user_id, person = uuid.uuid4(), uuid.uuid4()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=SyntheticIndependent(),
        registry=SyntheticRegistry((attestation(user_id, person),)),
        authorization=SyntheticGrantAuthority((grant(user_id, uuid.uuid4()),)),
        environment="test")
    with pytest.raises(APIError) as exc:
        gateway.load_scoped(None, request_for(users=(user_id,)))
    assert exc.value.code == "SOURCE_CLAIM_GRANT_AUTHORITY_UNAVAILABLE"


def test_an_account_without_a_current_human_is_refused():
    user_id = uuid.uuid4()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=SyntheticIndependent(),
        registry=SyntheticRegistry((attestation(user_id, current=False),)),
        authorization=SyntheticGrantAuthority(), environment="test")
    with pytest.raises(APIError) as exc:
        gateway.load_scoped(None, request_for(users=(user_id,)))
    assert exc.value.code == "SOURCE_CLAIM_PRINCIPAL_REGISTRY_UNAVAILABLE"


def test_two_attestations_for_one_account_are_refused():
    user_id = uuid.uuid4()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=SyntheticIndependent(),
        registry=SyntheticRegistry((attestation(user_id), attestation(user_id))),
        authorization=SyntheticGrantAuthority(), environment="test")
    with pytest.raises(APIError) as exc:
        gateway.load_scoped(None, request_for(users=(user_id,)))
    assert exc.value.code == "SOURCE_CLAIM_PRINCIPAL_REGISTRY_UNAVAILABLE"


def test_a_revoked_grant_is_not_held():
    user_id, person = uuid.uuid4(), uuid.uuid4()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=SyntheticIndependent(),
        registry=SyntheticRegistry((attestation(user_id, person),)),
        authorization=SyntheticGrantAuthority((
            grant(user_id, person, Grant.PROPOSE_EXCEPTION, current=False),
            grant(user_id, person, Grant.APPROVE_EXCEPTION))),
        environment="test")
    facts = gateway.load_scoped(None, request_for(users=(user_id,)))
    human, = facts.humans
    assert human.grants == (Grant.APPROVE_EXCEPTION,)
    assert human.human_principal_id == person


def test_the_revision_digest_covers_authority_state_but_not_which_accounts_were_looked_up():
    """An approval boundary must look up a second account and still reproduce the
    reviewer's proposal digest, so per-account facts stay out of the shared digest."""
    first, second, person = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    registry = SyntheticRegistry((attestation(first, person), attestation(second)))
    independent = SyntheticIndependent()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance(), independent=independent, registry=registry,
        authorization=SyntheticGrantAuthority(), environment="test")
    one = gateway.load_scoped(None, request_for(users=(first,)))
    both = gateway.load_scoped(None, request_for(users=(first, second)))
    assert one.revision_digest == both.revision_digest
    assert len(one.humans) == 1 and len(both.humans) == 2
    # A change in the authorities' own answers does change it.
    independent.assessments_ = (IndependentAssessment(
        uuid.uuid4(), "3" * 64, "ORCID_EXACT", AssessmentState.QUALIFYING, True),)
    assert gateway.load_scoped(None, request_for(users=(first,))).revision_digest != (
        one.revision_digest)


# ---------------------------------------------------------------------------
# The one adapter wired to a real data source
# ---------------------------------------------------------------------------

def test_staging_lineage_attests_nothing_and_refuses_an_unknown_artifact(setup):
    world = setup[0]
    db = world[0]
    authority = StagingSourceLineageAuthority()
    known = db.scalars(select(SourceArtifact.id)).all()
    assert known, "the hybrid fixture stages at least one artifact"
    # Real staging rows resolve, and the adapter still attests no formal issuance.
    assert authority.issuance(db, request_for(artifacts=known)) == ()
    with pytest.raises(APIError) as exc:
        authority.issuance(db, request_for(artifacts=(uuid.uuid4(),)))
    assert exc.value.code == "SOURCE_CLAIM_INSTITUTIONAL_AUTHORITY_UNAVAILABLE"


def test_lineage_only_institutional_facts_keep_the_exception_branch_closed(setup):
    """End-to-end: the default production wiring reaches no branch at all.

    With the real staging adapter plus a SYNTHETIC registry/grant authority (so the
    human checks can be reached), the absent verifier still blocks every path.
    """
    world, _, _, actor, _, command = setup
    db = world[0]
    person = uuid.uuid4()
    gateway = HybridAuthorityGateway(
        institutional=StagingSourceLineageAuthority(),
        registry=SyntheticRegistry((attestation(actor.user_id, person),)),
        authorization=SyntheticGrantAuthority((
            grant(actor.user_id, person, Grant.PROPOSE_EXCEPTION),)),
        environment="test")
    boundary = HybridSourceClaimCompatibility(db, authority=gateway)
    assert_error("SOURCE_CLAIM_INDEPENDENT_AUTHORITY_UNAVAILABLE",
                 lambda: boundary.prepare_proposal(actor, command, proposed_at=AT))
    # Even with a verifier present, no issuance attestation means no exception branch.
    gateway.independent = SyntheticIndependent()
    assert_error("INSTITUTIONAL_PROVENANCE_UNVERIFIED",
                 lambda: boundary.prepare_proposal(actor, command, proposed_at=AT))


def test_a_synthetic_issuance_attestation_must_still_match_the_stored_artifact(setup):
    world, _, _, actor, _, command = setup
    db = world[0]
    person = uuid.uuid4()
    artifact = db.scalars(select(SourceArtifact)).first()
    gateway = HybridAuthorityGateway(
        institutional=SyntheticIssuance((SourceAuthenticity(
            artifact.id, "9" * 64, "ICTU", SourceAuthenticityState.CURRENT,
            uuid.uuid4(), "4" * 64, "FORMALLY_VERIFIED_ISSUANCE_V1"),)),
        independent=SyntheticIndependent(),
        registry=SyntheticRegistry((attestation(actor.user_id, person),)),
        authorization=SyntheticGrantAuthority((
            grant(actor.user_id, person, Grant.PROPOSE_EXCEPTION),)),
        environment="test")
    boundary = HybridSourceClaimCompatibility(db, authority=gateway)
    # The digest does not match the stored artifact bytes, so provenance is invalid.
    assert_error("HYBRID_PROVENANCE_INVALID",
                 lambda: boundary.prepare_proposal(actor, command, proposed_at=AT))
    gateway.institutional = SyntheticIssuance((SourceAuthenticity(
        artifact.id, artifact.artifact_bytes_sha256, "ICTU",
        SourceAuthenticityState.CURRENT, uuid.uuid4(), "4" * 64,
        "FORMALLY_VERIFIED_ISSUANCE_V1"),))
    prepared = boundary.prepare_proposal(actor, command, proposed_at=AT)
    assert prepared.snapshot_hash
    assert ReviewBranch.INSTITUTIONAL_EXCEPTION in prepared.snapshot_json
