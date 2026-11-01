"""Turn staged source-claim observations into evidence for lecturer ↔ Scopus-author pairs.

Pure (standard library + ``source_claims``): no database, network or identity writes. A source
declaration is evidence, never approval; subjects are resolved only through the profile source
URL or the e-mail, never by name; reviewer decisions are inputs that are echoed, never changed.
The input must be the observation view's projection (one analysis per capture, one rule set).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.services.source_claims.canonical import (
    normalize_email,
    normalize_orcid,
    normalize_source_id,
    sha256_json,
)
from app.services.source_claims.contract import ParsedSnapshot

BRIDGE_RULE_ID = "RULE_ICTU_SOURCE_DECLARED_SCOPUS_ID"
BRIDGE_RULE_VERSION = "E3-P3A-1"
# R-02 lists PUBLISHER / REGISTRY / AGGREGATOR_*; an institution's own declaration is none of
# them, so it gets its own tier (proposed vocabulary addition, see E3P3A_MATCHING_MAPPING).
SOURCE_TIER = "INSTITUTION_DECLARED"
OWNED = "SCOPUS_ID_OWNED"
AMBIGUOUS_ID, UNASSIGNED_ID = "SCOPUS_ID_AMBIGUOUS", "SCOPUS_ID_UNASSIGNED"
ORCID_DECLARED, EMAIL_DECLARED = "ORCID_DECLARED", "EMAIL_DECLARED"
# Stored vocabularies (models/candidate.py, models/identity.py); only a reviewer can change them.
NEGATIVE_CANDIDATE_STATUSES = frozenset({"REJECTED", "SUPERSEDED"})
NEGATIVE_IDENTITY_STATUSES = frozenset({"REJECTED", "REVOKED"})


class BridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class Resolution(StrEnum):
    RESOLVED_SOURCE_ID = "RESOLVED_SOURCE_ID"   # profile URL equals one lecturer's profile URL
    RESOLVED_EMAIL = "RESOLVED_EMAIL"           # e-mail equals one lecturer's e-mail
    AMBIGUOUS = "AMBIGUOUS"                     # several lecturers share the key
    CONFLICT = "CONFLICT"                       # URL and e-mail point at different lecturers
    UNRESOLVED = "UNRESOLVED"                   # no lecturer carries the key (R-15)
    WEAK_SOURCE_KEY = "WEAK_SOURCE_KEY"         # content-keyed record: never resolved


class PairClass(StrEnum):
    VERIFIED_ASSOCIATION = "VERIFIED_ASSOCIATION"   # an APPROVED identity already exists
    PLAUSIBLE_CANDIDATE = "PLAUSIBLE_CANDIDATE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Presence(StrEnum):
    CURRENT = "CURRENT"              # observed in the latest capture of its scope
    NOT_OBSERVED = "NOT_OBSERVED"    # absent, but absence proves nothing (PARTIAL, weak key)
    WITHDRAWN = "WITHDRAWN"          # absent from a later COMPLETE capture of the same scope


# ---------------------------------------------------------------------------
# Inputs (built by P3-B from the staging rows; tests build them from parsed snapshots)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CaptureRef:
    capture_id: UUID
    source_system: str
    scope_key: str
    projection_version: str
    captured_at: str
    completeness: str


@dataclass(frozen=True, slots=True)
class ObservedClaim:
    """One row of ``source_claim_observations`` plus its record's identity fields."""

    capture_id: UUID
    analysis_id: UUID
    contract_version: str
    identity_rules_version: str
    normalization_version: str
    claim_id: UUID
    record_id: UUID
    claim_type: str
    subject_key: str | None
    value_raw: str | None
    value_normalized: str | None
    claim_key: str
    flags: tuple[tuple[str, Any], ...]
    record_key: str
    key_method: str
    key_strength: str
    record_validation_status: str
    record_source_id: str | None
    record_email: str | None

    def flag(self, name: str, default: Any = None) -> Any:
        return dict(self.flags).get(name, default)


@dataclass(frozen=True, slots=True)
class LecturerRef:
    lecturer_id: UUID
    repository_profile_url: str | None
    email: str | None
    orcid: str | None


@dataclass(frozen=True, slots=True)
class ScopusAuthorRef:
    scopus_author_id: UUID
    scopus_id: str


@dataclass(frozen=True, slots=True)
class DecisionRef:
    """Existing review state of a pair: candidate status and/or identity status, as stored."""

    lecturer_id: UUID
    scopus_author_id: UUID
    candidate_status: str | None = None   # PENDING | ACCEPTED | REJECTED | SUPERSEDED
    identity_status: str | None = None    # CANDIDATE | APPROVED | REJECTED | REVOKED


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ObservationRef:
    capture_id: UUID
    captured_at: str
    completeness: str
    analysis_id: UUID
    contract_version: str
    claim_id: UUID
    record_id: UUID


@dataclass(frozen=True, slots=True)
class SourceClaimEvidence:
    """One real-world source claim supporting one pair; repeated observations do not multiply it."""

    evidence_key: tuple[str, ...]
    fingerprint: str
    rule_id: str
    rule_version: str
    source_tier: str
    lecturer_id: UUID
    scopus_author_id: UUID
    scopus_id: str
    source_system: str
    scope_key: str
    claim_key: str
    subject_resolution: Resolution
    is_primary_claimed: bool
    listed: bool
    presence: Presence
    identity_rules_version: str
    normalization_version: str
    observed_in: tuple[ObservationRef, ...]


@dataclass(frozen=True, slots=True)
class PairAssessment:
    lecturer_id: UUID
    scopus_author_id: UUID
    scopus_id: str
    classification: PairClass
    reasons: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    existing_candidate_status: str | None
    existing_identity_status: str | None
    decision_preserved: bool                # the bridge never changes a stored decision
    accept_reason_required: bool            # R-05: source listing alone never auto-accepts


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    source_system: str
    scope_key: str
    claim_key: str
    lecturer_id: UUID | None
    scopus_id: str | None
    detail: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class BridgeResult:
    evidence: tuple[SourceClaimEvidence, ...]
    pairs: tuple[PairAssessment, ...]
    findings: tuple[Finding, ...]
    identity_rules_version: str | None
    normalization_version: str | None


# ---------------------------------------------------------------------------
# Building inputs from a parsed snapshot (pure; P3-B maps the same fields from staging rows)
# ---------------------------------------------------------------------------

def observations_from_snapshot(snapshot: ParsedSnapshot, *, capture_id: UUID, analysis_id: UUID,
                               ids: dict[str, UUID]) -> tuple[ObservedClaim, ...]:
    """``ids`` maps ``record_ref`` and ``record_ref/claim_key`` to stable row ids."""
    records = {r.ref: r for r in snapshot.records}
    observed = []
    for claim in snapshot.claims:
        record = records[claim.record_ref]
        normalized = {name: dict(value) for name, value in record.normalized}
        observed.append(ObservedClaim(
            capture_id=capture_id, analysis_id=analysis_id,
            contract_version=snapshot.contract_version,
            identity_rules_version=snapshot.identity_rules_version,
            normalization_version=snapshot.normalization_version,
            claim_id=ids[f"{claim.record_ref}/{claim.claim_key}"], record_id=ids[claim.record_ref],
            claim_type=claim.claim_type.value, subject_key=claim.subject_key,
            value_raw=claim.value.raw, value_normalized=claim.value.normalized,
            claim_key=claim.claim_key, flags=claim.flags, record_key=record.record_key.value,
            key_method=record.record_key.method.value,
            key_strength=record.record_key.strength.value,
            record_validation_status=record.validation_status.value,
            record_source_id=(normalized.get("source_id") or {}).get("normalized"),
            record_email=(normalized.get("email") or {}).get("normalized")))
    return tuple(observed)


# ---------------------------------------------------------------------------
# The bridge
# ---------------------------------------------------------------------------

def _validate(observations: tuple[ObservedClaim, ...],
              captures: dict[UUID, CaptureRef]) -> tuple[str | None, str | None]:
    """Fail closed unless the input is one rule set and one analysis per capture."""
    rules = {(o.identity_rules_version, o.normalization_version) for o in observations}
    if len(rules) > 1:
        raise BridgeError("MIXED_RULE_VERSIONS", f"observations span rule sets {sorted(rules)}")
    analyses: dict[UUID, set[UUID]] = defaultdict(set)
    seen: set[tuple[UUID, UUID]] = set()
    for o in observations:
        if o.capture_id not in captures:
            raise BridgeError("UNKNOWN_CAPTURE", f"capture {o.capture_id} has no CaptureRef")
        analyses[o.capture_id].add(o.analysis_id)
        if (o.capture_id, o.claim_id) in seen:
            raise BridgeError("DUPLICATE_OBSERVATION", f"claim {o.claim_id} twice in one capture")
        seen.add((o.capture_id, o.claim_id))
    for capture in captures.values():
        _instant(capture)                      # fail closed on naive or unparseable capture times
    crowded = sorted(str(c) for c, a in analyses.items() if len(a) > 1)
    if crowded:
        raise BridgeError("MULTIPLE_ANALYSES_PER_CAPTURE",
                          f"captures {crowded} carry several analyses (artifact versions or rules)")
    return next(iter(rules)) if rules else (None, None)


def _lecturer_index(lecturers: Iterable[LecturerRef]):
    by_url: dict[str, set[UUID]] = defaultdict(set)
    by_email: dict[str, set[UUID]] = defaultdict(set)
    by_id: dict[UUID, LecturerRef] = {}
    for lecturer in lecturers:
        by_id[lecturer.lecturer_id] = lecturer
        url = normalize_source_id(lecturer.repository_profile_url).normalized \
            if lecturer.repository_profile_url else None
        email = normalize_email(lecturer.email).normalized if lecturer.email else None
        if url:
            by_url[url].add(lecturer.lecturer_id)
        if email:
            by_email[email].add(lecturer.lecturer_id)
    return by_url, by_email, by_id


def _resolve(o: ObservedClaim, by_url, by_email) -> tuple[Resolution, UUID | None]:
    if o.key_strength == "WEAK":
        return Resolution.WEAK_SOURCE_KEY, None
    url_hits = by_url.get(o.record_source_id, set()) if o.record_source_id else set()
    email_hits = by_email.get(o.record_email, set()) if o.record_email else set()
    if len(url_hits) > 1:
        return Resolution.AMBIGUOUS, None
    if url_hits:
        if email_hits and email_hits != url_hits:
            return Resolution.CONFLICT, None
        return Resolution.RESOLVED_SOURCE_ID, next(iter(url_hits))
    if len(email_hits) > 1:
        return Resolution.AMBIGUOUS, None
    if email_hits:
        return Resolution.RESOLVED_EMAIL, next(iter(email_hits))
    return Resolution.UNRESOLVED, None


def _instant(capture: CaptureRef) -> datetime:
    """The capture time as an offset-aware UTC instant; naive or invalid times are refused."""
    try:
        moment = datetime.fromisoformat(capture.captured_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise BridgeError("CAPTURE_TIME_INVALID",
                          f"capture {capture.capture_id}: {capture.captured_at!r}") from exc
    if moment.utcoffset() is None:
        raise BridgeError("CAPTURE_TIME_INVALID",
                          f"capture {capture.capture_id} has no UTC offset")
    return moment.astimezone(UTC)


def _sort_key(capture: CaptureRef) -> tuple[datetime, str]:
    """Chronological order by instant. The UUID only makes exact ties deterministic; it never
    means one capture came after another."""
    return _instant(capture), str(capture.capture_id)


def _presence(observed: list[ObservedClaim], scope_captures: list[CaptureRef],
              captures: dict[UUID, CaptureRef]) -> tuple[Presence, str | None]:
    """Presence of a claim, plus ``"PRESENCE_DIFFERS"`` when equally recent captures disagree.

    WITHDRAWN needs a capture at a strictly later instant than the last COMPLETE capture that
    listed the claim, every capture at that latest instant COMPLETE and omitting the claim, and a
    non-weak subject key. Captures at the same instant are never ordered against each other.
    """
    instants = {c.capture_id: _instant(c) for c in scope_captures}
    latest_instant = max(instants.values())
    latest = [c for c in scope_captures if instants[c.capture_id] == latest_instant]
    seen_in = {o.capture_id for o in observed}
    listed_latest = [c for c in latest if c.capture_id in seen_in]
    if listed_latest:
        if len(listed_latest) == len(latest):
            return Presence.CURRENT, None
        return Presence.NOT_OBSERVED, "PRESENCE_DIFFERS"
    last_seen_instant = max(instants[c] for c in seen_in)
    last_seen = [captures[c] for c in seen_in if instants[c] == last_seen_instant]
    weak = any(o.key_strength == "WEAK" for o in observed)
    if (not weak and last_seen_instant < latest_instant
            and all(c.completeness == "COMPLETE" for c in latest)
            and any(c.completeness == "COMPLETE" for c in last_seen)):
        return Presence.WITHDRAWN, None
    return Presence.NOT_OBSERVED, None


def _finding(code, scope, claim_key, lecturer_id=None, scopus_id=None, **detail) -> Finding:
    return Finding(code, scope[0], scope[1], claim_key, lecturer_id, scopus_id,
                   tuple(sorted(detail.items())))


def bridge_source_claims(
    observations: Iterable[ObservedClaim], captures: Iterable[CaptureRef],
    lecturers: Iterable[LecturerRef], scopus_authors: Iterable[ScopusAuthorRef],
    decisions: Iterable[DecisionRef] = (),
) -> BridgeResult:
    observations = tuple(observations)
    capture_map = {c.capture_id: c for c in captures}
    rules = _validate(observations, capture_map)
    by_url, by_email, lecturer_by_id = _lecturer_index(lecturers)
    author_by_scopus_id = {a.scopus_id: a for a in scopus_authors}
    decision_by_pair = {(d.lecturer_id, d.scopus_author_id): d for d in decisions}
    approved_owner: dict[UUID, set[UUID]] = defaultdict(set)
    for d in decision_by_pair.values():
        if d.identity_status == "APPROVED":
            approved_owner[d.scopus_author_id].add(d.lecturer_id)

    captures_by_scope: dict[tuple[str, str, str], list[CaptureRef]] = defaultdict(list)
    for c in capture_map.values():
        captures_by_scope[(c.source_system, c.scope_key, c.projection_version)].append(c)

    # Real-world claim identity: (source system, scope, projection, claim_key). Repeated captures,
    # artifact versions and analyses of the same claim collapse onto it; other sources stay apart.
    grouped: dict[tuple[str, str, str, str], list[ObservedClaim]] = defaultdict(list)
    for o in observations:
        c = capture_map[o.capture_id]
        grouped[(c.source_system, c.scope_key, c.projection_version, o.claim_key)].append(o)

    findings: list[Finding] = []
    evidence: list[SourceClaimEvidence] = []
    current_unowned: dict[str, set[str]] = defaultdict(set)     # scopus_id -> claim types
    orcid_records: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for claim_identity in sorted(grouped):
        source_system, scope_key, projection, claim_key = claim_identity
        group = sorted(grouped[claim_identity],
                       key=lambda o: _sort_key(capture_map[o.capture_id]))
        scope = (source_system, scope_key)
        latest_obs = group[-1]
        presence, order_ambiguity = _presence(
            group, captures_by_scope[(source_system, scope_key, projection)], capture_map)
        value = latest_obs.value_normalized
        latest_instant = _instant(capture_map[latest_obs.capture_id])
        tied = [o for o in group if _instant(capture_map[o.capture_id]) == latest_instant]
        if order_ambiguity is None and len({o.flags for o in tied}) > 1:
            order_ambiguity = "FLAGS_DIFFER"        # same-instant captures disagree on the flags
        if order_ambiguity is not None:
            findings.append(_finding("CAPTURE_ORDER_AMBIGUOUS", scope, claim_key, scopus_id=value,
                                     claim_type=latest_obs.claim_type, reason=order_ambiguity,
                                     captures=len({o.capture_id for o in tied})))
        if value is None:
            findings.append(_finding("INVALID_CLAIM_VALUE", scope, claim_key,
                                     claim_type=latest_obs.claim_type,
                                     value_raw=latest_obs.value_raw))
            continue

        if latest_obs.claim_type in (AMBIGUOUS_ID, UNASSIGNED_ID):
            if presence is Presence.CURRENT:
                current_unowned[value].add(latest_obs.claim_type)
            findings.append(_finding("UNOWNED_SCOPUS_ID_LISTED", scope, claim_key, scopus_id=value,
                                     claim_type=latest_obs.claim_type,
                                     in_catalog=value in author_by_scopus_id,
                                     presence=presence.value))
            continue

        resolution, lecturer_id = _resolve(latest_obs, by_url, by_email)
        if latest_obs.claim_type == ORCID_DECLARED:
            orcid_records[value].add((source_system, latest_obs.record_key))
            if lecturer_id is not None:
                stored = normalize_orcid(lecturer_by_id[lecturer_id].orcid).normalized \
                    if lecturer_by_id[lecturer_id].orcid else None
                code = ("ORCID_DECLARED_MATCHES_LECTURER" if stored == value
                        else "ORCID_DECLARED_DIFFERS_FROM_LECTURER" if stored
                        else "ORCID_DECLARED_LECTURER_HAS_NONE")
                findings.append(_finding(code, scope, claim_key, lecturer_id, evidence_tier=
                                         "SOURCE_DECLARED_NOT_SLOT_VERIFIED"))
            continue
        if latest_obs.claim_type == EMAIL_DECLARED:
            if resolution is Resolution.RESOLVED_SOURCE_ID:
                stored = normalize_email(lecturer_by_id[lecturer_id].email).normalized \
                    if lecturer_by_id[lecturer_id].email else None
                if stored != value:
                    findings.append(_finding("EMAIL_DECLARED_DIFFERS_FROM_LECTURER", scope,
                                             claim_key, lecturer_id))
            continue

        # SCOPUS_ID_OWNED
        if lecturer_id is None:
            findings.append(_finding(f"SUBJECT_{resolution.value}", scope, claim_key,
                                     scopus_id=value, record_key_method=latest_obs.key_method))
            continue
        author = author_by_scopus_id.get(value)
        if author is None:
            findings.append(_finding("SCOPUS_AUTHOR_NOT_IN_CATALOG", scope, claim_key,
                                     lecturer_id, value))
            continue
        evidence_key = (str(lecturer_id), str(author.scopus_author_id), BRIDGE_RULE_ID,
                        BRIDGE_RULE_VERSION, source_system, scope_key, projection, claim_key)
        evidence.append(SourceClaimEvidence(
            evidence_key=evidence_key, fingerprint=sha256_json(list(evidence_key)),
            rule_id=BRIDGE_RULE_ID, rule_version=BRIDGE_RULE_VERSION, source_tier=SOURCE_TIER,
            lecturer_id=lecturer_id, scopus_author_id=author.scopus_author_id, scopus_id=value,
            source_system=source_system, scope_key=scope_key, claim_key=claim_key,
            subject_resolution=resolution,
            is_primary_claimed=bool(latest_obs.flag("is_primary_claimed", False)),
            listed=bool(latest_obs.flag("listed", True)), presence=presence,
            identity_rules_version=latest_obs.identity_rules_version,
            normalization_version=latest_obs.normalization_version,
            observed_in=tuple(ObservationRef(
                o.capture_id, capture_map[o.capture_id].captured_at,
                capture_map[o.capture_id].completeness, o.analysis_id, o.contract_version,
                o.claim_id, o.record_id) for o in group)))

    for orcid, holders in sorted(orcid_records.items()):
        if len(holders) > 1:   # R-14: kept and flagged, never resolved automatically
            findings.append(Finding("ORCID_DECLARED_BY_MULTIPLE_RECORDS", "*", "*",
                                    f"ORCID_DECLARED|*|{orcid}", None, None,
                                    (("orcid", orcid), ("records", tuple(sorted(holders))))))

    pairs = _assess_pairs(evidence, decision_by_pair, approved_owner, current_unowned, findings)
    evidence.sort(key=lambda e: e.evidence_key)
    findings.sort(key=lambda f: (f.code, f.source_system, f.scope_key, f.claim_key,
                                 str(f.lecturer_id), f.scopus_id or ""))
    return BridgeResult(tuple(evidence), pairs, tuple(findings), *rules)


def _assess_pairs(evidence, decision_by_pair, approved_owner, current_unowned, findings):
    by_pair: dict[tuple[UUID, UUID], list[SourceClaimEvidence]] = defaultdict(list)
    for item in evidence:
        by_pair[(item.lecturer_id, item.scopus_author_id)].append(item)
    owners_now: dict[UUID, set[UUID]] = defaultdict(set)
    for (lecturer_id, author_id), items in by_pair.items():
        if any(i.presence is not Presence.WITHDRAWN for i in items):
            owners_now[author_id].add(lecturer_id)

    pairs = []
    for (lecturer_id, author_id), items in sorted(by_pair.items(),
                                                  key=lambda p: (str(p[0][0]), str(p[0][1]))):
        decision = decision_by_pair.get((lecturer_id, author_id))
        scopus_id = items[0].scopus_id
        live = [i for i in items if i.presence is not Presence.WITHDRAWN]
        reasons = []
        if decision is not None and (decision.candidate_status in NEGATIVE_CANDIDATE_STATUSES
                                     or decision.identity_status in NEGATIVE_IDENTITY_STATUSES):
            reasons.append("PRIOR_NEGATIVE_DECISION_REVIEWER_REOPEN_REQUIRED")
        if approved_owner[author_id] - {lecturer_id}:
            reasons.append("SCOPUS_ID_APPROVED_FOR_OTHER_LECTURER")
        if len(owners_now[author_id]) > 1:
            reasons.append("SCOPUS_ID_DECLARED_FOR_SEVERAL_LECTURERS")
        if scopus_id in current_unowned:
            reasons.append("SCOPUS_ID_ALSO_LISTED_AS_" + "_AND_".join(
                sorted(t.removeprefix("SCOPUS_ID_") for t in current_unowned[scopus_id])))
        if not live:
            reasons.append("CLAIM_WITHDRAWN_FROM_SOURCE")
        if decision is not None and decision.identity_status == "APPROVED":
            classification = PairClass.VERIFIED_ASSOCIATION     # verified by a reviewer, not here
        elif any(r.startswith("SCOPUS_ID_") for r in reasons):
            classification = PairClass.CONFLICTING_EVIDENCE
        elif not live:
            classification = PairClass.INSUFFICIENT_EVIDENCE
        else:
            classification = PairClass.PLAUSIBLE_CANDIDATE
        pairs.append(PairAssessment(
            lecturer_id, author_id, scopus_id, classification, tuple(reasons),
            tuple(sorted(i.fingerprint for i in items)),
            decision.candidate_status if decision else None,
            decision.identity_status if decision else None,
            decision_preserved=True, accept_reason_required=True))
        if decision is not None and decision.identity_status == "APPROVED" and not live:
            findings.append(Finding("SOURCE_NO_LONGER_LISTS_APPROVED_ID", items[0].source_system,
                                    items[0].scope_key, items[0].claim_key, lecturer_id,
                                    scopus_id))
    return tuple(pairs)
