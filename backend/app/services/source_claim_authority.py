"""Typed, fail-closed authority integration for the hybrid SOURCE_CLAIM boundary.

Four separate authorities decide whether a hybrid draft may exist at all:

1. ICTU institutional source — did ICTU formally issue this declaration, and is that
   issuance still current (not revoked)?
2. Independent identity evidence — is there author-specific evidence, verified by a
   governed verifier, that this Scopus author is this lecturer?
3. Human principal registry — which *person* is behind an account, so dual control
   cannot be satisfied by one human holding two accounts?
4. Reviewer/exception approver authorization — does this person currently hold the
   capability to propose, or to approve, an institutional exception?

None of the four exists as a governed production system in this repository. Each one
therefore ships here as a contract plus a **fail-closed adapter**: asked for facts, it
raises, and the hybrid boundary refuses. The only adapter wired to a real data source is
``StagingSourceLineageAuthority``, which reads the genuine staging tables and reports
*no* issuance attestation, because lineage bytes are not a formal issuance authority —
so the institutional-exception branch stays ``INSTITUTIONAL_PROVENANCE_UNVERIFIED``
instead of being granted on provenance alone.

Nothing here may be replaced by synthetic attestations in production:
``assert_production_safe`` refuses outright when a non-authoritative adapter is wired up
under ``ENVIRONMENT=prod``, and the gateway re-checks it at every load.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.source_staging import SourceArtifact
from app.services.matching.candidate_persistence import sha256_json
from app.services.source_claim_hybrid import (
    AuthorityFacts,
    AuthorityRequest,
    Grant,
    HumanAuthority,
    IndependentAssessment,
    ScopedHybridAuthority,
    SourceAuthenticity,
)

# ``AuthorityRequest``/``ScopedHybridAuthority`` are the policy module's port; they are
# re-exported here because every adapter below implements against them.
__all__ = [
    "AuthorityKind", "AuthorityIntegration", "AuthorityRequest", "CapabilityGrant",
    "ExceptionAuthorizationAuthority", "HumanPrincipalRegistry", "HybridAuthorityGateway",
    "IndependentEvidenceAuthority", "InstitutionalSourceAuthority", "PrincipalAttestation",
    "ScopedHybridAuthority", "StagingSourceLineageAuthority",
    "UnavailableExceptionAuthorizationAuthority", "UnavailableHumanPrincipalRegistry",
    "UnavailableIndependentEvidenceAuthority", "UnavailableInstitutionalSourceAuthority",
    "assert_production_safe", "authority_denied", "default_hybrid_authority",
    "integration_report",
]


class AuthorityKind(StrEnum):
    INSTITUTIONAL_SOURCE = "INSTITUTIONAL_SOURCE"
    INDEPENDENT_EVIDENCE = "INDEPENDENT_EVIDENCE"
    HUMAN_PRINCIPAL_REGISTRY = "HUMAN_PRINCIPAL_REGISTRY"
    EXCEPTION_AUTHORIZATION = "EXCEPTION_AUTHORIZATION"


UNAVAILABLE_CODES = {
    AuthorityKind.INSTITUTIONAL_SOURCE: "SOURCE_CLAIM_INSTITUTIONAL_AUTHORITY_UNAVAILABLE",
    AuthorityKind.INDEPENDENT_EVIDENCE: "SOURCE_CLAIM_INDEPENDENT_AUTHORITY_UNAVAILABLE",
    AuthorityKind.HUMAN_PRINCIPAL_REGISTRY: "SOURCE_CLAIM_PRINCIPAL_REGISTRY_UNAVAILABLE",
    AuthorityKind.EXCEPTION_AUTHORIZATION: "SOURCE_CLAIM_GRANT_AUTHORITY_UNAVAILABLE",
}


@dataclass(frozen=True, slots=True)
class PrincipalAttestation:
    """The registry's answer for one account: which current human is behind it."""

    user_id: uuid.UUID
    human_principal_id: uuid.UUID
    current: bool
    auth_version: int
    attestation_id: uuid.UUID
    revision_digest: str


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    """One currently held capability, bound to an exact account *and* human principal."""

    user_id: uuid.UUID
    human_principal_id: uuid.UUID
    permission: Grant
    grant_id: uuid.UUID
    current: bool
    revision_digest: str


@dataclass(frozen=True, slots=True)
class AuthorityIntegration:
    """What an adapter is, and what is still missing before it can carry production."""

    kind: AuthorityKind
    adapter: str
    production_authoritative: bool
    missing_integration: str | None = None
    data_source: str | None = None


def authority_denied(kind: AuthorityKind, missing: str) -> APIError:
    return APIError(
        status_code=409, code=UNAVAILABLE_CODES[kind],
        detail="A required SOURCE_CLAIM authority integration is unavailable.",
        data={"authority": str(kind), "missing_integration": missing})


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

class InstitutionalSourceAuthority(Protocol):
    """Formal issuance and revocation of an ICTU declaration, per selected artifact."""

    integration: AuthorityIntegration

    def issuance(self, view: Session,
                 request: AuthorityRequest) -> tuple[SourceAuthenticity, ...]: ...


class IndependentEvidenceAuthority(Protocol):
    """Governed verifier output for one lecturer ↔ Scopus author pair.

    Returns assessments, never raw evidence: this authority — not the hybrid policy —
    decides whether something was independently verified.
    """

    integration: AuthorityIntegration

    def assessments(self, view: Session,
                    request: AuthorityRequest) -> tuple[IndependentAssessment, ...]: ...


class HumanPrincipalRegistry(Protocol):
    """Account → current human principal, so two accounts of one person are one human."""

    integration: AuthorityIntegration

    def principals(self, view: Session,
                   request: AuthorityRequest) -> tuple[PrincipalAttestation, ...]: ...


class ExceptionAuthorizationAuthority(Protocol):
    """Currently held propose/approve capability grants, per account and human."""

    integration: AuthorityIntegration

    def grants(self, view: Session,
               request: AuthorityRequest) -> tuple[CapabilityGrant, ...]: ...


# ---------------------------------------------------------------------------
# Fail-closed adapters: the contract exists, the governed system does not
# ---------------------------------------------------------------------------

class UnavailableInstitutionalSourceAuthority:
    integration = AuthorityIntegration(
        AuthorityKind.INSTITUTIONAL_SOURCE, "UnavailableInstitutionalSourceAuthority", False,
        "Authenticated ICTU issuance channel, issuer delegation and revocation feed")

    def issuance(self, view, request):
        raise authority_denied(self.integration.kind, self.integration.missing_integration)


class StagingSourceLineageAuthority:
    """Real staging reader: confirms the selected artifacts exist, attests nothing.

    This is the one adapter connected to a genuinely authoritative existing source —
    the append-only staging tables, which are authoritative for *what bytes ICTU
    published and when*. They are not an issuance authority: nobody signed the
    declaration and there is no revocation feed. So this adapter returns an empty
    attestation set, which leaves ``provenance_verified`` false and blocks the
    institutional-exception branch. It fails closed if an artifact named by the trusted
    context is missing from staging or carries a malformed digest.
    """

    integration = AuthorityIntegration(
        AuthorityKind.INSTITUTIONAL_SOURCE, "StagingSourceLineageAuthority", False,
        "Formally verified, revocable ICTU issuance of the staged declaration",
        data_source="source_artifacts / source_captures (append-only staging)")

    def issuance(self, view, request):
        for artifact_id in request.artifact_ids:
            artifact = view.get(SourceArtifact, artifact_id)
            if artifact is None or artifact.capture_id is None:
                raise authority_denied(self.integration.kind,
                                       "Staged artifact lineage is incomplete")
        return ()


class UnavailableIndependentEvidenceAuthority:
    """No verifier exists, so insufficiency is unknown — and unknown is not insufficient.

    Refusing (rather than returning an empty assessment set) is what keeps the
    institutional-exception branch from being reachable by simply having no verifier.
    """

    integration = AuthorityIntegration(
        AuthorityKind.INDEPENDENT_EVIDENCE, "UnavailableIndependentEvidenceAuthority", False,
        "Governed independent verifier, qualification rules and conflict resolution")

    def assessments(self, view, request):
        raise authority_denied(self.integration.kind, self.integration.missing_integration)


class UnavailableHumanPrincipalRegistry:
    integration = AuthorityIntegration(
        AuthorityKind.HUMAN_PRINCIPAL_REGISTRY, "UnavailableHumanPrincipalRegistry", False,
        "ICTU person registry proving account ↔ human equivalence and HUMAN/SERVICE kind")

    def principals(self, view, request):
        raise authority_denied(self.integration.kind, self.integration.missing_integration)


class UnavailableExceptionAuthorizationAuthority:
    integration = AuthorityIntegration(
        AuthorityKind.EXCEPTION_AUTHORIZATION, "UnavailableExceptionAuthorizationAuthority", False,
        "Dual-control capability grants for exception propose/approve, with revocation")

    def grants(self, view, request):
        raise authority_denied(self.integration.kind, self.integration.missing_integration)


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

def _hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value)


class HybridAuthorityGateway:
    """Composes the four authorities into the ``AuthorityFacts`` the policy consumes.

    Read-only: every lookup receives the caller's no-autoflush view and may only read.
    The returned ``revision_digest`` is the hash of exactly the facts gathered here, so
    a later change of any authority's answer produces a different digest and a stored
    draft stops replaying — facts can never be back-dated into an existing proposal.
    """

    def __init__(self, *, institutional: InstitutionalSourceAuthority | None = None,
                 independent: IndependentEvidenceAuthority | None = None,
                 registry: HumanPrincipalRegistry | None = None,
                 authorization: ExceptionAuthorizationAuthority | None = None,
                 environment: str | None = None) -> None:
        self.institutional = institutional or UnavailableInstitutionalSourceAuthority()
        self.independent = independent or UnavailableIndependentEvidenceAuthority()
        self.registry = registry or UnavailableHumanPrincipalRegistry()
        self.authorization = authorization or UnavailableExceptionAuthorizationAuthority()
        self.environment = environment

    @property
    def integrations(self) -> tuple[AuthorityIntegration, ...]:
        return (self.institutional.integration, self.independent.integration,
                self.registry.integration, self.authorization.integration)

    def load(self, view: Session, context_digest: str) -> AuthorityFacts:
        """Digest-only entry point; without the trusted scope nothing can be resolved."""
        raise authority_denied(AuthorityKind.INSTITUTIONAL_SOURCE,
                               "Scoped authority request is required")

    def load_scoped(self, view: Session, request: AuthorityRequest) -> AuthorityFacts:
        assert_production_safe(self.integrations, environment=self.environment)
        if not isinstance(request, AuthorityRequest) or not _hex64(request.context_digest):
            raise authority_denied(AuthorityKind.INSTITUTIONAL_SOURCE,
                                   "Trusted authority request is malformed")
        # Order is fixed so a missing integration is reported deterministically.
        authenticity = tuple(self.institutional.issuance(view, request))
        independent = tuple(self.independent.assessments(view, request))
        attestations = tuple(self.registry.principals(view, request))
        grants = tuple(self.authorization.grants(view, request))
        humans = tuple(self._human(attestations, grants, user_id)
                       for user_id in request.user_ids)
        return AuthorityFacts(request.context_digest, _revision_digest(
            request, authenticity, independent), independent, humans, authenticity)

    def _human(self, attestations, grants, user_id) -> HumanAuthority:
        """Compose one account's attestation and grants; mismatched bindings are refused.

        A grant is usable only if the authorization authority binds it to the *same*
        human the registry reports for that account, so a stale or transplanted grant
        cannot carry another person's capability.
        """
        found = [a for a in attestations if a.user_id == user_id]
        if len(found) != 1:
            raise authority_denied(AuthorityKind.HUMAN_PRINCIPAL_REGISTRY,
                                   "Exactly one current human attestation per account")
        human = found[0]
        if not isinstance(human, PrincipalAttestation) or not human.current:
            raise authority_denied(AuthorityKind.HUMAN_PRINCIPAL_REGISTRY,
                                   "Account is not bound to a current human principal")
        held, digests = [], []
        for grant in grants:
            if grant.user_id != user_id:
                continue
            if not isinstance(grant, CapabilityGrant) or not isinstance(grant.permission, Grant):
                raise authority_denied(AuthorityKind.EXCEPTION_AUTHORIZATION,
                                       "Capability grant is not a typed permission")
            if grant.human_principal_id != human.human_principal_id:
                raise authority_denied(AuthorityKind.EXCEPTION_AUTHORIZATION,
                                       "Capability grant is bound to another human principal")
            if not grant.current or grant.permission in held:
                continue
            held.append(grant.permission)
            digests.append(str(grant.grant_id) + grant.revision_digest)
        revision = sha256_json({"attestation": str(human.attestation_id) + human.revision_digest,
                                "grants": sorted(digests)})
        return HumanAuthority(user_id, human.human_principal_id, human.auth_version, True,
                              tuple(held), human.attestation_id, revision)


def _revision_digest(request: AuthorityRequest, authenticity, independent) -> str:
    """Digest of the authority state shared by every actor on this context.

    Per-account facts are deliberately excluded: each ``HumanAuthority`` carries its own
    ``revision_digest``, and the actor's is bound into the snapshot. Keeping accounts out
    of the shared digest is what lets an approval boundary — which must look up a second
    account — still reproduce the reviewer's proposal digest exactly.
    """
    return sha256_json({
        "context_digest": request.context_digest,
        "authenticity": sorted(str(a.verification_id) + a.verification_digest
                               for a in authenticity),
        "independent": sorted(str(i.receipt_id) + i.receipt_digest for i in independent),
    })


def assert_production_safe(integrations: tuple[AuthorityIntegration, ...], *,
                           environment: str | None = None) -> None:
    """Refuse non-authoritative authority adapters in a production environment.

    Offline gates run with incomplete integrations on purpose. Production must never
    substitute them, so this fails closed rather than degrading.
    """
    env = environment if environment is not None else _current_environment()
    if env != "prod":
        return
    missing = [i.adapter for i in integrations if not i.production_authoritative]
    if missing:
        raise APIError(
            status_code=409, code="SOURCE_CLAIM_AUTHORITY_NOT_PRODUCTION_READY",
            detail="SOURCE_CLAIM authority integrations are not production-authoritative.",
            data={"adapters": missing})


def _current_environment() -> str:
    from app.core.config import settings  # imported lazily: offline tools need no settings

    return settings.environment


def default_hybrid_authority(*, environment: str | None = None) -> HybridAuthorityGateway:
    """The production default: staging lineage plus three unavailable authorities.

    Every branch therefore fails closed. Replace an adapter only with a governed,
    genuinely authoritative integration.
    """
    return HybridAuthorityGateway(institutional=StagingSourceLineageAuthority(),
                                  environment=environment)


def integration_report(gateway: HybridAuthorityGateway | None = None) -> list[dict[str, object]]:
    """Machine-readable list of what is wired and what is still missing."""
    target = gateway if gateway is not None else default_hybrid_authority(environment="test")
    return [{"authority": str(i.kind), "adapter": i.adapter, "data_source": i.data_source,
             "production_authoritative": i.production_authoritative,
             "missing_integration": i.missing_integration} for i in target.integrations]
