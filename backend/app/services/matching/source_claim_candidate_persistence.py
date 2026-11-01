"""E3-P3-B1: caller-owned, non-reviewable SOURCE_CLAIM persistence.

Recompute from the active staging projection and the accepted P3-A bridge. Never
accept caller-supplied evidence. STAGED is deliberately not COMPLETED: P3-B2 must
provide the reviewer compatibility boundary before this evidence can be reviewed.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import Uuid, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import ScopusAuthor
from app.models.source_staging import (
    SourceAnalysis,
    SourceArtifact,
    SourceCapture,
    SourceClaim,
    SourceContent,
    SourceRecord,
    SourceRuleSet,
)
from app.services.matching.candidate_persistence import (
    GenerationRunConflict,
    canonical_json,
    sha256_json,
)
from app.services.source_claim_matching import bridge

RULE_SET_ID = "E3_SOURCE_CLAIM_CANDIDATES"
RULE_SET_VERSION = "E3-P3-B1/1"
RELEASE_GATE = "E3-P3-B2_REQUIRED"


def _json(value):
    """Detached JSON values: no ORM/domain mutable aliases escape into storage."""
    return json.loads(canonical_json(value))


def _aware(value: datetime) -> datetime:
    # SQLite drops tzinfo on ORM round-trip; PostgreSQL timestamptz does not.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class SourceClaimWriteResult:
    run_id: uuid.UUID
    status: str
    candidates: int
    observations: int
    evidence: int
    idempotent_replay: bool


class SourceClaimCandidateWriter:
    """No commits, outer rollbacks, review actions or live workflow integration."""

    def __init__(self, session: Session):
        self.session = session
        dialect = session.get_bind().dialect.name
        if dialect not in {"postgresql", "sqlite"}:
            raise ValueError(f"Unsupported dialect: {dialect}")
        self._insert = pg_insert if dialect == "postgresql" else sqlite_insert

    def _inputs(self):
        active = self.session.scalar(select(SourceRuleSet).order_by(
            SourceRuleSet.sequence_no.desc()).limit(1))
        if active is None:
            raise GenerationRunConflict("No active source rule set")
        selected = text(
            "SELECT capture_id, artifact_id, analysis_id FROM source_capture_analyses "
            "WHERE selection_rank = 1 AND is_active_rule_set = 1"
        ).columns(capture_id=Uuid(), artifact_id=Uuid(), analysis_id=Uuid()).subquery()
        rows = self.session.execute(
            select(SourceCapture, SourceContent, SourceAnalysis, SourceArtifact)
            .join(SourceContent, SourceContent.id == SourceCapture.content_id)
            .join(selected, selected.c.capture_id == SourceCapture.id)
            .join(SourceAnalysis, SourceAnalysis.id == selected.c.analysis_id)
            .join(SourceArtifact, SourceArtifact.id == selected.c.artifact_id)
            .order_by(SourceCapture.id)
        ).all()
        count = self.session.scalar(select(func.count()).select_from(SourceCapture))
        if len(rows) != count or len({cap.id for cap, *_ in rows}) != count:
            raise GenerationRunConflict("Every capture needs exactly one active analysis")
        captures, observed, refs = [], [], {}
        projected_claims = text(
            "SELECT capture_id, claim_id FROM source_claim_observations"
        ).columns(capture_id=Uuid(), claim_id=Uuid()).subquery()
        for cap, content, analysis, artifact in rows:
            if (analysis.identity_rules_version, analysis.normalization_version) != (
                active.identity_rules_version, active.normalization_version
            ):
                raise GenerationRunConflict("Inactive analysis selected")
            # The immutable hashed envelope retains the offset even when the
            # SQLite test mirror's DateTime column loses it. Never invent UTC.
            captured_at = datetime.fromisoformat(
                json.loads(cap.capture_json)["captured_at"].replace("Z", "+00:00"))
            if captured_at.utcoffset() is None:
                raise GenerationRunConflict("Capture envelope has no UTC offset")
            captures.append(bridge.CaptureRef(
                cap.id, cap.source_system, content.scope_key, cap.projection_version,
                captured_at.astimezone(UTC).isoformat(), cap.completeness,
            ))
            for claim, record in self.session.execute(
                select(SourceClaim, SourceRecord)
                .join(SourceRecord, SourceRecord.id == SourceClaim.record_id)
                .join(projected_claims, projected_claims.c.claim_id == SourceClaim.id)
                .where(projected_claims.c.capture_id == cap.id)
                .order_by(SourceClaim.id)
            ):
                normalized = record.normalized
                observation = bridge.ObservedClaim(
                    cap.id, analysis.id, analysis.contract_version,
                    analysis.identity_rules_version, analysis.normalization_version,
                    claim.id, record.id, claim.claim_type, claim.subject_key,
                    claim.value_raw, claim.value_normalized, claim.claim_key,
                    tuple(sorted(claim.flags.items())), record.record_key,
                    record.key_method, record.key_strength, record.validation_status,
                    (normalized.get("source_id") or {}).get("normalized"),
                    (normalized.get("email") or {}).get("normalized"),
                )
                observed.append(observation)
                refs[(str(cap.id), str(claim.id))] = _json({
                    **asdict(observation), "artifact_id": artifact.id,
                    "artifact_bytes_sha256": artifact.artifact_bytes_sha256,
                    "content_id": content.id, "content_hash": content.content_hash,
                    "capture_hash": cap.capture_hash, "record_hash": record.record_hash,
                    "record_raw": record.raw, "record_issues": record.issues,
                    "source_url": content.source_url,
                })
        lecturers = [bridge.LecturerRef(
            r.id, r.repository_profile_url, r.email, r.orcid,
        ) for r in self.session.scalars(select(Lecturer).order_by(Lecturer.id))]
        authors = [bridge.ScopusAuthorRef(r.id, r.scopus_id)
                   for r in self.session.scalars(select(ScopusAuthor).order_by(ScopusAuthor.id))]
        roots = {(r.lecturer_id, r.scopus_author_id): r for r in self.session.scalars(
            select(LecturerScopusCandidate).order_by(LecturerScopusCandidate.id))}
        identities = {(r.lecturer_id, r.scopus_author_id): r for r in self.session.scalars(
            select(LecturerScopusIdentity).order_by(LecturerScopusIdentity.id))}
        # Absent and PENDING are equivalent input states. Creating our own root
        # must not change the next replay's input identity. Reviewed states differ.
        decision_pairs = set(identities) | {
            pair for pair, root in roots.items() if root.status != "PENDING"}
        decisions = [bridge.DecisionRef(
            *pair, roots[pair].status if pair in roots else None,
            identities[pair].status if pair in identities else None,
        ) for pair in sorted(decision_pairs, key=str)]
        result = bridge.bridge_source_claims(observed, captures, lecturers, authors, decisions)
        state = _json({
            "schema_version": 1, "release_gate": RELEASE_GATE, "reviewer_active": False,
            "active_rule_set": {"id": active.id, "sequence_no": active.sequence_no,
                                "identity_rules_version": active.identity_rules_version,
                                "normalization_version": active.normalization_version},
            "captures": [asdict(c) for c in captures],
            "source_observations": [refs[key] for key in sorted(refs)],
            "bridge": asdict(result),
        })
        return result, refs, roots, identities, state

    def _prepare(self):
        result, refs, roots, identities, state = self._inputs()
        grouped = defaultdict(list)
        for item in result.evidence:
            sources = [refs[(str(o.capture_id), str(o.claim_id))] for o in item.observed_in]
            ambiguous = any(
                f.code == "CAPTURE_ORDER_AMBIGUOUS" and f.source_system == item.source_system
                and f.scope_key == item.scope_key and f.claim_key == item.claim_key
                for f in result.findings)
            latest = max(datetime.fromisoformat(o.captured_at) for o in item.observed_in)
            invalid = any(s["record_validation_status"] == "INVALID" for s in sources
                          if next(datetime.fromisoformat(o.captured_at)
                                  for o in item.observed_in
                                  if str(o.capture_id) == s["capture_id"]) == latest)
            presence = ("INVALID" if invalid else "AMBIGUOUS" if ambiguous
                        else item.presence.value)
            if presence == "CURRENT" and not item.listed:
                presence = "NOT_OBSERVED"
            fingerprint = sha256_json([
                "SOURCE_CLAIM", str(item.lecturer_id), str(item.scopus_author_id),
                item.source_system, item.scope_key, item.evidence_key[-2], item.claim_key,
            ])
            descriptor = _json({
                "evidence_kind": "SOURCE_CLAIM", "rule_id": item.rule_id,
                "rule_version": item.rule_version, "fingerprint": fingerprint,
                "payload": {
                    "source_tier": "INSTITUTION_DECLARED", "logical_fingerprint": fingerprint,
                    "source_system": item.source_system, "scope_key": item.scope_key,
                    "projection_version": item.evidence_key[-2], "claim_key": item.claim_key,
                    "scopus_id": item.scopus_id, "subject_resolution": item.subject_resolution,
                    "current_state": presence, "current_weight": int(presence == "CURRENT"),
                    "is_primary_claimed": None if ambiguous else item.is_primary_claimed,
                    "listed": None if ambiguous else item.listed,
                    "identity_rules_version": item.identity_rules_version,
                    "normalization_version": item.normalization_version,
                },
                "source_refs": sources,
            })
            grouped[(item.lecturer_id, item.scopus_author_id)].append(descriptor)
        items = []
        for pair in result.pairs:
            key = pair.lecturer_id, pair.scopus_author_id
            descriptors = sorted(grouped[key], key=lambda e: e["fingerprint"])
            identity = identities.get(key)
            eligible = (any(e["payload"]["current_weight"] for e in descriptors)
                        and (identity is None or identity.status not in {"REJECTED", "REVOKED"}))
            if key not in roots and not eligible:
                continue  # The complete bridge/claim history is still in source_state.
            snapshot = _json({"pair": asdict(pair), "evidence": descriptors,
                              "reviewer_active": False, "release_gate": RELEASE_GATE})
            items.append({"pair": key, "snapshot": snapshot,
                          "observation_hash": sha256_json(snapshot), "evidence": descriptors})
        state["input_hash"] = sha256_json(state)
        return state, items

    def persist_generation(self, run_id: uuid.UUID) -> SourceClaimWriteResult:
        # begin_nested() unconditionally flushes earlier pending caller changes.
        # Fail outside our recovery scope if those changes are invalid.
        self.session.flush()
        with self.session.begin_nested():
            state, items = self._prepare()
            run = self.session.get(CandidateGenerationRun, run_id, with_for_update=True)
            if run is not None:
                self._verify_run(run, state, items)
                return self._result(run_id, items, True)
            now = datetime.now(UTC)
            run = CandidateGenerationRun(
                id=run_id, rule_set_id=RULE_SET_ID, rule_set_version=RULE_SET_VERSION,
                source_state=_json(state), status="RUNNING", started_at=now,
                version=1, created_at=now, updated_at=now,
            )
            self.session.add(run)
            self.session.flush()
            for item in items:
                lecturer_id, author_id = item["pair"]
                self.session.execute(self._insert(LecturerScopusCandidate).values(
                    id=uuid.uuid4(), lecturer_id=lecturer_id, scopus_author_id=author_id,
                    status="PENDING", version=1, first_seen_at=now, last_seen_at=now,
                    created_at=now, updated_at=now,
                ).on_conflict_do_nothing(index_elements=["lecturer_id", "scopus_author_id"]))
                root = self.session.scalar(select(LecturerScopusCandidate).where(
                    LecturerScopusCandidate.lecturer_id == lecturer_id,
                    LecturerScopusCandidate.scopus_author_id == author_id,
                ).with_for_update())
                if root is None:
                    raise GenerationRunConflict("Candidate insert not observable")
                observation = LecturerScopusCandidateObservation(
                    id=uuid.uuid4(), candidate_id=root.id, generation_run_id=run.id,
                    observed_at=now, candidate_snapshot=_json(item["snapshot"]),
                    observation_hash=item["observation_hash"], created_at=now,
                )
                self.session.add(observation)
                self.session.flush()
                for descriptor in item["evidence"]:
                    self.session.add(LecturerScopusCandidateEvidence(
                        id=uuid.uuid4(), observation_id=observation.id,
                        evidence_kind=descriptor["evidence_kind"], rule_id=descriptor["rule_id"],
                        rule_version=descriptor["rule_version"],
                        payload=_json(descriptor["payload"]),
                        source_refs=_json(descriptor["source_refs"]),
                        evidence_fingerprint=descriptor["fingerprint"], created_at=now,
                    ))
            run.status, run.completed_at = "STAGED", datetime.now(UTC)
            self.session.flush()
            return self._result(run.id, items, False)

    def _verify_run(self, run, state, items):
        if (run.rule_set_id != RULE_SET_ID or run.rule_set_version != RULE_SET_VERSION
                or run.status != "STAGED" or run.completed_at is None
                or run.source_state != state):
            raise GenerationRunConflict("Run metadata or trusted active inputs differ")
        actual = self.session.execute(
            select(LecturerScopusCandidateObservation, LecturerScopusCandidate)
            .join(LecturerScopusCandidate,
                  LecturerScopusCandidate.id == LecturerScopusCandidateObservation.candidate_id)
            .where(LecturerScopusCandidateObservation.generation_run_id == run.id)
        ).all()
        by_pair = {(r.lecturer_id, r.scopus_author_id): obs for obs, r in actual}
        if len(actual) != len(items) or set(by_pair) != {i["pair"] for i in items}:
            raise GenerationRunConflict("Run observation membership differs")
        for item in items:
            obs = by_pair[item["pair"]]
            if (obs.candidate_snapshot != item["snapshot"]
                    or obs.observation_hash != item["observation_hash"]
                    or _aware(obs.observed_at) != _aware(run.started_at)):
                raise GenerationRunConflict("Observation snapshot or identity differs")
            descriptors = self.session.scalars(select(LecturerScopusCandidateEvidence).where(
                LecturerScopusCandidateEvidence.observation_id == obs.id)).all()
            actual_descriptors = [{
                "evidence_kind": e.evidence_kind, "rule_id": e.rule_id,
                "rule_version": e.rule_version, "fingerprint": e.evidence_fingerprint,
                "payload": e.payload, "source_refs": e.source_refs,
            } for e in descriptors]
            if sorted(map(canonical_json, actual_descriptors)) != sorted(
                map(canonical_json, item["evidence"])
            ):
                raise GenerationRunConflict("Evidence payload, rules or provenance differs")

    @staticmethod
    def _result(run_id, items, replay):
        return SourceClaimWriteResult(run_id, "STAGED", len(items), len(items),
                                      sum(len(i["evidence"]) for i in items), replay)

    def current_evidence(self) -> tuple[dict, ...]:
        """Offline projection only; never a reviewer read path.

        Only a fully verified STAGED run matching today's active inputs is usable.
        New captures/rules/decisions invalidate an older run until regeneration.
        Multiple matching runs collapse by logical fingerprint, never by row count.
        """
        state, items = self._prepare()
        matching = [r for r in self.session.scalars(select(CandidateGenerationRun).where(
            CandidateGenerationRun.rule_set_id == RULE_SET_ID,
            CandidateGenerationRun.status == "STAGED",
        )) if r.source_state.get("input_hash") == state["input_hash"]]
        if not matching:
            return ()
        for run in matching:
            self._verify_run(run, state, items)
        evidence = {e["fingerprint"]: e for i in items for e in i["evidence"]}
        return tuple(_json(evidence[key]) for key in sorted(evidence))
