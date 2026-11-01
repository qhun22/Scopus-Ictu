"""Explicit review serialization and an unexposed SOURCE_CLAIM read contract.

No authorization bypass or new route: production reviewers still use only the
existing completed NAME/PUBLICATION observation. Source preview is offline until
the separately authorized decision/read release gate is satisfied.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.schemas.review_api import (
    ReviewNameEvidenceResponse,
    ReviewPublicationEvidenceResponse,
    ReviewSourceClaimEvidenceResponse,
    ReviewSourceClaimProjectionResponse,
)
from app.services.matching.candidate_persistence import (
    GenerationRunConflict,
    canonical_json,
    sha256_json,
)
from app.services.matching.source_claim_candidate_persistence import (
    RULE_SET_ID,
    SourceClaimCandidateWriter,
)

_STATES = {"CURRENT", "WITHDRAWN", "NOT_OBSERVED", "AMBIGUOUS", "INVALID"}
_CONFLICT_CODES = {
    "PRIOR_NEGATIVE_DECISION_REVIEWER_REOPEN_REQUIRED",
    "SCOPUS_ID_APPROVED_FOR_OTHER_LECTURER",
    "SCOPUS_ID_DECLARED_FOR_SEVERAL_LECTURERS",
    "SCOPUS_ID_ALSO_LISTED_AS_AMBIGUOUS",
    "SCOPUS_ID_ALSO_LISTED_AS_UNASSIGNED",
    "SCOPUS_ID_ALSO_LISTED_AS_AMBIGUOUS_AND_UNASSIGNED",
    "CLAIM_WITHDRAWN_FROM_SOURCE",
}
_TRACE_FIELDS = (
    "capture_id", "analysis_id", "artifact_id", "content_id", "claim_id", "record_id",
    "contract_version", "identity_rules_version", "normalization_version",
)


def _error(code="SOURCE_CLAIM_EVIDENCE_INVALID"):
    return APIError(status_code=409, code=code,
                    detail="Candidate evidence cannot be safely represented for review.")


def _uuid(value):
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def source_ref_ids(source_refs):
    """Existing NAME/PUBLICATION reference interpretation, unchanged."""
    result = {}
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        ref_id, kind = _uuid(ref.get("id")), ref.get("kind")
        if ref_id is not None and isinstance(kind, str):
            result.setdefault(kind, ref_id)
    return result


def serialize_review_evidence(evidence_rows, publications):
    """Existing live contract: NAME/PUBLICATION only; SOURCE_CLAIM remains gated."""
    names, papers = [], []
    for ev in evidence_rows:
        if ev.evidence_kind == "SOURCE_CLAIM":
            raise _error("SOURCE_CLAIM_REVIEW_INACTIVE")
        if ev.evidence_kind not in {"NAME", "PUBLICATION"}:
            raise _error("CANDIDATE_EVIDENCE_KIND_UNSUPPORTED")
        payload = ev.payload if isinstance(ev.payload, dict) else {}
        refs = list(ev.source_refs or [])
        common = dict(evidence_id=ev.id, evidence_kind=ev.evidence_kind,
                      rule_id=ev.rule_id, rule_version=ev.rule_version,
                      source_refs=refs, evidence_fingerprint=ev.evidence_fingerprint)
        if ev.evidence_kind == "NAME":
            names.append(ReviewNameEvidenceResponse(**common, **{
                key: payload.get(key) for key in (
                    "lecturer_source_value", "lecturer_comparison_value", "scopus_surface_type",
                    "scopus_surface_value", "scopus_comparison_value",
                )
            }))
        elif ev.evidence_kind == "PUBLICATION":
            ids = source_ref_ids(refs)
            canonical_id = ids.get("publication")
            publication = publications.get(canonical_id)
            papers.append(ReviewPublicationEvidenceResponse(
                **common, reconciliation=payload.get("reconciliation"),
                known_publication_id=ids.get("lecturer_known_publication"),
                lecturer_source_snapshot_id=ids.get("lecturer_source_snapshot"),
                canonical_publication_id=canonical_id,
                title=(publication.title if publication
                       else payload.get("canonical_publication_title")),
                doi=publication.doi if publication else payload.get("canonical_publication_doi"),
                eid=publication.eid if publication else payload.get("canonical_publication_eid"),
                candidate_scopus_author_id=_uuid(payload.get("candidate_scopus_author_id")),
            ))
    return names, papers


def _descriptor(row):
    if row.evidence_kind != "SOURCE_CLAIM":
        raise _error("CANDIDATE_EVIDENCE_KIND_UNSUPPORTED")
    return {"evidence_kind": row.evidence_kind, "rule_id": row.rule_id,
            "rule_version": row.rule_version, "fingerprint": row.evidence_fingerprint,
            "payload": row.payload, "source_refs": row.source_refs}


def _historical_captures(state):
    """Verify the B1 envelope hash and capture fields before using history.

    Hash a detached top-level view excluding input_hash, exactly as B1 wrote it.
    Validation never repairs a stored hash or mutates stored provenance.
    """
    if not isinstance(state, dict):
        raise _error()
    stored_hash = state.get("input_hash")
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        raise _error()
    try:
        expected_hash = sha256_json({k: v for k, v in state.items() if k != "input_hash"})
    except (TypeError, ValueError) as exc:
        raise _error() from exc
    if stored_hash != expected_hash:
        raise _error()
    captures = state.get("captures")
    if not isinstance(captures, list) or not captures:
        raise _error()
    result = {}
    for capture in captures:
        if not isinstance(capture, dict):
            raise _error()
        capture_id = capture.get("capture_id")
        captured_at = capture.get("captured_at")
        completeness = capture.get("completeness")
        if (not isinstance(capture_id, str) or _uuid(capture_id) is None
                or capture_id in result or not isinstance(captured_at, str)
                or not isinstance(completeness, str)
                or completeness not in {"COMPLETE", "PARTIAL"}):
            raise _error()
        try:
            moment = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _error() from exc
        if moment.utcoffset() is None:
            raise _error()
        result[capture_id] = {"captured_at": moment.astimezone(UTC),
                              "completeness": completeness}
    return result


def _history(row, observation, run, candidate):
    """Validate stored historical membership; it never proves current authority."""
    capture_map = _historical_captures(run.source_state)
    descriptor = _descriptor(row)
    snapshot = observation.candidate_snapshot
    pair = snapshot["pair"]
    if (pair["lecturer_id"] != str(candidate.lecturer_id)
            or pair["scopus_author_id"] != str(candidate.scopus_author_id)
            or sha256_json(snapshot) != observation.observation_hash
            or sum(e == descriptor for e in snapshot["evidence"]) != 1
            or snapshot["reviewer_active"] is not False):
        raise _error()
    payload = row.payload
    if (payload["source_tier"] != "INSTITUTION_DECLARED"
            or payload["logical_fingerprint"] != row.evidence_fingerprint
            or payload["current_state"] not in _STATES
            or sha256_json([
                "SOURCE_CLAIM", str(candidate.lecturer_id), str(candidate.scopus_author_id),
                payload["source_system"], payload["scope_key"], payload["projection_version"],
                payload["claim_key"],
            ]) != row.evidence_fingerprint):
        raise _error()
    traces = []
    for ref in row.source_refs:
        if (ref not in run.source_state["source_observations"]
                or ref["claim_type"] != "SCOPUS_ID_OWNED"
                or ref["value_normalized"] != payload["scopus_id"]
                or ref["claim_key"] != payload["claim_key"]):
            raise _error()
        capture = capture_map[ref["capture_id"]]
        traces.append({**{k: ref[k] for k in _TRACE_FIELDS},
                       "captured_at": capture["captured_at"],
                       "completeness": capture["completeness"]})
    return descriptor, {
        "evidence_id": row.id, "observation_id": observation.id, "generation_run_id": run.id,
        "rule_id": row.rule_id, "rule_version": row.rule_version,
        "recorded_state": payload["current_state"],
    }, traces, set(pair["reasons"]) & _CONFLICT_CODES


def source_claim_read_preview(session: Session, candidate_id: uuid.UUID):
    """Future reviewer contract, NOT an HTTP handler or authorization boundary.

    Read only. Caller authorization/exposure belongs to the later release gate.
    Reuses the accepted writer's public CURRENT projection without rewriting it.
    Every historical row is labeled history; only trusted current descriptors can
    provide current state/weight. No latest-run/UUID shortcut or weight summation.
    """
    with session.no_autoflush:
        candidate = session.get(LecturerScopusCandidate, candidate_id)
        if candidate is None:
            raise APIError(status_code=404, code="CANDIDATE_NOT_FOUND",
                           detail="Candidate was not found.")
        rows = session.execute(
            select(LecturerScopusCandidateEvidence, LecturerScopusCandidateObservation,
                   CandidateGenerationRun)
            .join(LecturerScopusCandidateObservation,
                  LecturerScopusCandidateObservation.id
                  == LecturerScopusCandidateEvidence.observation_id)
            .join(CandidateGenerationRun, CandidateGenerationRun.id
                  == LecturerScopusCandidateObservation.generation_run_id)
            .where(LecturerScopusCandidateObservation.candidate_id == candidate_id,
                   CandidateGenerationRun.rule_set_id == RULE_SET_ID,
                   CandidateGenerationRun.status == "STAGED")
            .order_by(LecturerScopusCandidateEvidence.id)
        ).all()
        groups = defaultdict(list)
        try:
            for row, observation, run in rows:
                groups[row.evidence_fingerprint].append(_history(row, observation, run, candidate))
            # Validate historical envelopes first, including malformed states
            # that the accepted B1 CURRENT reader is not intended to parse.
            try:
                current = {e["fingerprint"]: e
                           for e in SourceClaimCandidateWriter(session).current_evidence()}
            except GenerationRunConflict as exc:
                raise _error("SOURCE_CLAIM_PROJECTION_UNAVAILABLE") from exc
            items = []
            for fingerprint, history in sorted(groups.items()):
                active = current.get(fingerprint)
                payload = active["payload"] if active else history[0][0]["payload"]
                state = payload["current_state"] if active else "STALE"
                if state not in _STATES | {"STALE"}:
                    raise _error()
                # Whitelist fields; never forward payload/refs/snapshot dictionaries.
                traces = {canonical_json(trace): trace for h in history for trace in h[2]}
                active_refs = {
                    (r["capture_id"], r["analysis_id"], r["claim_id"], r["artifact_id"])
                    for r in active["source_refs"]
                } if active else set()
                safe_traces = []
                for trace in traces.values():
                    key = tuple(trace[k] for k in
                                ("capture_id", "analysis_id", "claim_id", "artifact_id"))
                    safe_traces.append({**trace, "selection_status":
                                        "ACTIVE_PROJECTION" if key in active_refs
                                        else "HISTORICAL_ONLY"})
                items.append(ReviewSourceClaimEvidenceResponse(
                    evidence_fingerprint=fingerprint, source_system=payload["source_system"],
                    scope_key=payload["scope_key"], scopus_id=payload["scopus_id"],
                    subject_resolution=payload["subject_resolution"] if active else None,
                    recorded_subject_resolutions=sorted({
                        h[0]["payload"]["subject_resolution"] for h in history}),
                    selection_status="ACTIVE_PROJECTION" if active else "HISTORICAL_ONLY",
                    current_state=state,
                    current_weight=payload["current_weight"] if active else 0,
                    is_primary_claimed=(payload["is_primary_claimed"]
                                        if state == "CURRENT" else None),
                    listed=payload["listed"] if state == "CURRENT" else None,
                    temporal_ambiguity=state == "AMBIGUOUS",
                    recorded_states=sorted({h[0]["payload"]["current_state"] for h in history}),
                    recorded_conflict_codes=sorted(set().union(*(h[3] for h in history))),
                    history=[h[1] for h in history],
                    source_refs=sorted(safe_traces, key=canonical_json),
                ))
            return ReviewSourceClaimProjectionResponse(
                candidate_id=candidate.id, candidate_status=candidate.status, items=items)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _error() from exc
