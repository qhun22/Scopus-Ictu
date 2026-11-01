"""Idempotent, append-only persistence of ICTU source artifacts into the staging tables.

Transaction ownership: the caller owns the session's transaction and decides commit/rollback.
Every public write runs inside its own SAVEPOINT, so a failure discards only that operation's
rows (earlier work in the caller's transaction survives) and the error propagates; this module
never commits, rolls back the outer transaction or keeps counters outside the database.
"""

from __future__ import annotations

import hashlib
import json
import uuid
import zlib
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from sqlalchemy import func, insert, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.governance import AuditEvent
from app.models.source_staging import (
    SOURCE_CAPTURE_ANALYSES_VIEW,
    SourceAnalysis,
    SourceArtifact,
    SourceCapture,
    SourceClaim,
    SourceContent,
    SourceRecord,
    SourceRuleSet,
)
from app.services.source_claims import adapters, analysis, parser
from app.services.source_claims.adapters import AdapterError
from app.services.source_claims.contract import ParsedSnapshot
from app.services.source_claims.parser import ArtifactError, parse_artifact_bytes
from app.services.source_claims.provenance import ProvenanceError, bind_and_build_profiles_artifact

_LOCK_KEY = zlib.crc32(b"scopus-ictu:source-staging") & 0x7FFFFFFF
GUIDE_LAYOUTS = ("TABLES", "MULTI_ID")
_ENTITY_ARTIFACT = "source_artifact"
_ENTITY_RULE_SET = "source_rule_set"


class StagingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class Actor:
    """Audit actor, mirroring the audit_events invariant (USER with id, or SYSTEM with name)."""

    user_id: uuid.UUID | None = None
    service: str | None = None

    def __post_init__(self) -> None:
        user = self.user_id is not None and self.service is None
        system = self.user_id is None and bool(self.service and self.service.strip())
        if not (user or system):
            raise StagingError("ACTOR_INVALID", "actor is a user id or a non-blank service name")


@dataclass(frozen=True, slots=True)
class IngestResult:
    outcome: str
    layers: tuple[tuple[str, bool], ...]
    content_id: uuid.UUID
    capture_id: uuid.UUID
    artifact_id: uuid.UUID
    analysis_id: uuid.UUID
    artifact_bytes_sha256: str
    contract_version: str
    identity_rules_version: str
    normalization_version: str
    completeness: str
    record_count: int
    claim_count: int


@dataclass(frozen=True, slots=True)
class ActivationResult:
    outcome: str                      # ACTIVATED | ALREADY_ACTIVE
    identity_rules_version: str
    normalization_version: str
    analyses_created: int
    artifacts_covered: int
    captures_covered: int


@dataclass(frozen=True, slots=True)
class CaptureComparison:
    previous_capture_id: uuid.UUID
    current_capture_id: uuid.UUID
    report: analysis.PresenceReport


def ingest_outcome(layers: dict[str, bool]) -> str:
    """The first layer that was new names the outcome; nothing new means ALREADY_INGESTED."""
    for layer, outcome in (("content", "CREATED"), ("capture", "REUSED"),
                           ("artifact", "ARTIFACT_ADDED"), ("analysis", "REANALYSED")):
        if layers[layer]:
            return outcome
    return "ALREADY_INGESTED"


def _decode_json_bytes(data: bytes, name: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        duplicated = sorted(k for k, n in Counter(k for k, _ in pairs).items() if n > 1)
        if duplicated:
            raise StagingError("DUPLICATE_JSON_KEY", f"{name}: duplicate keys {duplicated}")
        return dict(pairs)

    if not isinstance(data, bytes):
        raise StagingError("BYTES_REQUIRED", f"{name} must be passed as the exact file bytes")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagingError("NOT_JSON", f"{name}: {exc}") from exc


class SourceStagingService:
    def __init__(self, session: Session, actor: Actor) -> None:
        if not isinstance(actor, Actor):
            raise StagingError("ACTOR_INVALID", "an Actor is required")
        dialect = session.get_bind().dialect.name
        if dialect not in ("postgresql", "sqlite"):
            raise StagingError("UNSUPPORTED_DIALECT", dialect)
        self.session, self.actor, self._dialect = session, actor, dialect

    # ------------------------------------------------------------------ public: ingest

    def ingest_harvest(
        self, *, lecturers_bytes: bytes, lecturers_sha256: str, manifest_bytes: bytes,
        replay_bytes: bytes, crawl_report_bytes: bytes | None = None,
        upstream_name: str = "lecturers.json", upstream_storage_ref: str | None = None,
    ) -> IngestResult:
        """Craw profiles: only through the trusted bind-and-adapt entrypoint."""
        try:
            artifact = bind_and_build_profiles_artifact(
                lecturers_bytes=lecturers_bytes, lecturers_sha256=lecturers_sha256,
                manifest_bytes=manifest_bytes, replay_bytes=replay_bytes,
                crawl_report_bytes=crawl_report_bytes, upstream_name=upstream_name)
        except (ProvenanceError, AdapterError) as exc:
            raise StagingError(f"SOURCE_REJECTED_{exc.code}", str(exc)) from exc
        return self._ingest(adapters.artifact_bytes(artifact), upstream_storage_ref)

    def ingest_guide_snapshot(
        self, *, snapshot_bytes: bytes, snapshot_sha256: str, layout: str, completeness: str,
        declared_counts: dict[str, int] | None = None, upstream_name: str | None = None,
        upstream_storage_ref: str | None = None,
    ) -> IngestResult:
        """Scopus-guide snapshot: bound to its exact bytes only; no manifest or replay exists for
        it, so completeness stays the caller's explicit, recorded statement."""
        if layout not in GUIDE_LAYOUTS:
            raise StagingError("LAYOUT_INVALID", f"layout must be one of {GUIDE_LAYOUTS}")
        if not isinstance(snapshot_bytes, bytes) \
                or hashlib.sha256(snapshot_bytes).hexdigest() != snapshot_sha256:
            raise StagingError("BYTES_SHA256_MISMATCH",
                               "snapshot bytes do not hash to the declared SHA-256")
        snapshot = _decode_json_bytes(snapshot_bytes, upstream_name or "snapshot")
        build = (adapters.guide_tables_artifact if layout == "TABLES"
                 else adapters.guide_multi_id_artifact)
        try:
            artifact = build(snapshot, snapshot_sha256=snapshot_sha256, completeness=completeness,
                             declared_counts=declared_counts, upstream_name=upstream_name)
        except AdapterError as exc:
            raise StagingError(f"SOURCE_REJECTED_{exc.code}", str(exc)) from exc
        return self._ingest(adapters.artifact_bytes(artifact), upstream_storage_ref)

    # ------------------------------------------------------------------ public: rule sets

    def active_rule_set(self) -> tuple[str, str] | None:
        row = self.session.execute(
            select(SourceRuleSet.identity_rules_version, SourceRuleSet.normalization_version)
            .order_by(SourceRuleSet.sequence_no.desc()).limit(1)).first()
        return (row[0], row[1]) if row else None

    def activate_rule_set(self, *, reason: str | None = None) -> ActivationResult:
        """Activate the running code's rule versions: analyse every stored artifact under them,
        prove every capture then has exactly one active analysis, and only then insert the
        rule-set row, all in one SAVEPOINT. Readers see the old rules until the caller commits."""
        target = (parser.IDENTITY_RULES_VERSION, parser.NORMALIZATION_VERSION)
        self._lock(exclusive=True)
        if self.active_rule_set() == target:
            counts = self._coverage(target)
            return ActivationResult("ALREADY_ACTIVE", *target, 0, *counts)
        with self._savepoint():
            created = 0
            for artifact_row in self.session.execute(
                    select(SourceArtifact.id, SourceArtifact.content_id,
                           SourceArtifact.contract_version,
                           SourceArtifact.artifact_bytes_sha256)).all():
                snap = self._stored_snapshot(artifact_row)
                if (snap.identity_rules_version, snap.normalization_version) != target:
                    raise StagingError("RULE_VERSION_DRIFT", "parser versions changed mid-run")
                _, new = self._ensure_analysis(artifact_row.content_id, snap)
                created += new
            rule_set_id = uuid.uuid4()
            self.session.execute(insert(SourceRuleSet).values(
                id=rule_set_id, identity_rules_version=target[0],
                normalization_version=target[1], reason=reason,
                activated_by=self.actor.user_id))
            if self.active_rule_set() != target:
                raise StagingError("ACTIVATION_NOT_VISIBLE", "new rule set is not the newest row")
            artifacts, captures = self._coverage(target)
            self._audit(_ENTITY_RULE_SET, rule_set_id, "SOURCE_RULE_SET_ACTIVATED", {
                "identity_rules_version": target[0], "normalization_version": target[1],
                "analyses_created": created, "artifacts": artifacts, "captures": captures,
                "reason": reason})
        return ActivationResult("ACTIVATED", *target, created, artifacts, captures)

    # ------------------------------------------------------------------ public: comparison

    def compare_captures(self, previous_capture_id: uuid.UUID,
                         current_capture_id: uuid.UUID) -> CaptureComparison:
        """Read-only presence diff. Withdrawal only between comparable COMPLETE captures of the
        same scope, rules and projection, in order; it never touches reviews or identities."""
        captures = {row.id: row for row in self.session.execute(
            select(SourceCapture.id, SourceCapture.projection_version,
                   SourceCapture.adapter_version)
            .where(SourceCapture.id.in_([previous_capture_id, current_capture_id]))).all()}
        if set(captures) != {previous_capture_id, current_capture_id}:
            raise StagingError("CAPTURE_NOT_FOUND", "both captures must exist")
        previous = self._capture_snapshot(previous_capture_id)
        current = self._capture_snapshot(current_capture_id)
        report = analysis.presence_diff(previous, current)
        extra = []
        if captures[previous_capture_id].projection_version != \
                captures[current_capture_id].projection_version:
            extra.append("PROJECTION_DIFFERS")
        if extra:
            entries = tuple(
                replace(e, status=analysis.PresenceStatus.NOT_OBSERVED)
                if e.status in (analysis.PresenceStatus.WITHDRAWN,
                                analysis.PresenceStatus.KEY_UNSTABLE) else e
                for e in report.entries)
            report = analysis.PresenceReport(False, report.reasons + tuple(extra), entries)
        return CaptureComparison(previous_capture_id, current_capture_id, report)

    # ------------------------------------------------------------------ internals

    def _ingest(self, data: bytes, upstream_storage_ref: str | None) -> IngestResult:
        try:
            snap = parse_artifact_bytes(data)
            adapters.staging_keys(snap)
        except (ArtifactError, AdapterError) as exc:
            raise StagingError(f"ARTIFACT_INVALID_{exc.code}", str(exc)) from exc
        self._lock(exclusive=False)
        active = self.active_rule_set()
        versions = (snap.identity_rules_version, snap.normalization_version)
        if active is None:
            raise StagingError("NO_ACTIVE_RULE_SET", "activate the rule set before ingesting")
        if active != versions:
            raise StagingError("RULE_SET_MISMATCH",
                               f"active {active} differs from this code's rules {versions}")
        with self._savepoint():
            content_id, new_content = self._ensure_content(snap)
            capture_id, new_capture = self._ensure_capture(content_id, snap)
            artifact_id, new_artifact = self._ensure_artifact(
                content_id, capture_id, snap, upstream_storage_ref)
            analysis_id, new_analysis = self._ensure_analysis(content_id, snap)
            layers = {"content": new_content, "capture": new_capture, "artifact": new_artifact,
                      "analysis": new_analysis}
            result = IngestResult(
                ingest_outcome(layers), tuple(layers.items()), content_id, capture_id,
                artifact_id, analysis_id, snap.artifact_bytes_sha256, snap.contract_version,
                snap.identity_rules_version, snap.normalization_version, snap.completeness.value,
                len(snap.records), len(snap.claims))
            self._audit(_ENTITY_ARTIFACT, artifact_id, "SOURCE_ARTIFACT_INGESTED", {
                "outcome": result.outcome, "layers": layers,
                "source_system": snap.source_system.value, "content_hash": snap.content_hash,
                "capture_hash": snap.capture.capture_hash,
                "artifact_bytes_sha256": snap.artifact_bytes_sha256,
                "contract_version": snap.contract_version, "completeness": result.completeness,
                "identity_rules_version": versions[0], "normalization_version": versions[1],
                "records": result.record_count, "claims": result.claim_count})
        return result

    def _savepoint(self):
        """Flush first (G04): a pre-existing pending failure must not be absorbed here."""
        self.session.flush()
        return _Savepoint(self.session)

    def _lock(self, *, exclusive: bool) -> None:
        """PostgreSQL: transaction-scoped advisory lock (activation exclusive, ingest shared).
        SQLite serializes writers itself; nothing to do there."""
        if self._dialect == "postgresql":
            fn = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
            self.session.execute(text(f"SELECT {fn}(:key)"), {"key": _LOCK_KEY})

    def _insert_ignore(self, model, values: dict) -> bool:
        dialect_insert = postgresql.insert if self._dialect == "postgresql" else sqlite.insert
        stmt = dialect_insert(model.__table__).values(**values).on_conflict_do_nothing()
        return self.session.execute(stmt).rowcount == 1

    def _find_one(self, model, **key) -> Any:
        rows = self.session.execute(select(model).filter_by(**key)).scalars().all()
        if len(rows) != 1:
            raise StagingError("UNEXPECTED_CONFLICT",
                               f"{model.__tablename__}: expected one row for {sorted(key)}")
        return rows[0]

    def _ensure_content(self, snap: ParsedSnapshot) -> tuple[uuid.UUID, bool]:
        key = {"source_system": snap.source_system.value, "content_hash": snap.content_hash}
        new = self._insert_ignore(SourceContent, {
            "id": uuid.uuid4(), **key, "contract_major": parser.CONTRACT_MAJOR,
            "scope_key": snap.scope_key, "source_url": snap.source_url,
            "content_json": snap.content_json})
        row = self._find_one(SourceContent, **key)
        if row.scope_key != snap.scope_key:
            raise StagingError("STORED_CONTENT_MISMATCH", "stored content differs in scope")
        return row.id, new

    def _ensure_capture(self, content_id: uuid.UUID,
                        snap: ParsedSnapshot) -> tuple[uuid.UUID, bool]:
        capture = json.loads(snap.capture.capture_json)
        adapter_info, upstream = capture.get("adapter") or {}, capture.get("upstream") or {}
        if not adapter_info.get("version") or not adapter_info.get("projection") \
                or not upstream.get("bytes_sha256"):
            raise StagingError("CAPTURE_LINEAGE_MISSING", "capture lacks adapter or upstream data")
        key = {"content_id": content_id, "capture_hash": snap.capture.capture_hash}
        new = self._insert_ignore(SourceCapture, {
            "id": uuid.uuid4(), **key, "source_system": snap.source_system.value,
            "captured_at": datetime.fromisoformat(snap.capture.captured_at.replace("Z", "+00:00")),
            "completeness": snap.completeness.value, "capture_json": snap.capture.capture_json,
            "adapter_version": adapter_info["version"],
            "projection_version": adapter_info["projection"],
            "upstream_name": upstream.get("file"),
            "upstream_bytes_sha256": upstream["bytes_sha256"]})
        return self._find_one(SourceCapture, **key).id, new

    def _ensure_artifact(self, content_id, capture_id, snap, upstream_storage_ref):
        new = self._insert_ignore(SourceArtifact, {
            "id": uuid.uuid4(), "content_id": content_id, "capture_id": capture_id,
            "contract_version": snap.contract_version,
            "artifact_bytes_sha256": snap.artifact_bytes_sha256,
            "upstream_storage_ref": upstream_storage_ref, "ingested_by": self.actor.user_id})
        row = self._find_one(SourceArtifact, artifact_bytes_sha256=snap.artifact_bytes_sha256)
        if (row.content_id, row.capture_id, row.contract_version) != (
                content_id, capture_id, snap.contract_version):
            raise StagingError("STORED_ARTIFACT_MISMATCH", "artifact row disagrees with its bytes")
        return row.id, new

    def _ensure_analysis(self, content_id: uuid.UUID,
                         snap: ParsedSnapshot) -> tuple[uuid.UUID, bool]:
        key = {"content_id": content_id, "contract_version": snap.contract_version,
               "identity_rules_version": snap.identity_rules_version,
               "normalization_version": snap.normalization_version}
        analysis_id = uuid.uuid4()
        new = self._insert_ignore(SourceAnalysis, {
            "id": analysis_id, **key, "parser_build": "source_claims/e3-p1+p2a",
            "artifact_issues": [issue.to_dict() for issue in snap.issues],
            "declared_counts": dict(snap.declared_counts),
            "record_count": len(snap.records), "claim_count": len(snap.claims)})
        if new:
            self._insert_children(analysis_id, snap)
        else:
            analysis_id = self._find_one(SourceAnalysis, **key).id
        self._verify_analysis(analysis_id, len(snap.records), len(snap.claims))
        return analysis_id, new

    def _insert_children(self, analysis_id: uuid.UUID, snap: ParsedSnapshot) -> None:
        record_ids = {record.ref: uuid.uuid4() for record in snap.records}
        if snap.records:
            self.session.execute(insert(SourceRecord), [{
                "id": record_ids[r.ref], "analysis_id": analysis_id,
                "record_kind": r.record_kind.value, "source_position": r.source_position,
                "record_hash": r.record_hash, "record_key": r.record_key.value,
                "key_method": r.record_key.method.value,
                "key_strength": r.record_key.strength.value, "raw": json.loads(r.raw_json),
                "normalized": {name: dict(value) for name, value in r.normalized},
                "validation_status": r.validation_status.value,
                "issues": [i.to_dict() for i in r.issues]} for r in snap.records])
        if snap.claims:
            self.session.execute(insert(SourceClaim), [{
                "id": uuid.uuid4(), "analysis_id": analysis_id,
                "record_id": record_ids[c.record_ref], "claim_type": c.claim_type.value,
                "subject_key": c.subject_key, "value_raw": c.value.raw,
                "value_normalized": c.value.normalized, "value_method": c.value.method,
                "claim_key": c.claim_key, "flags": dict(c.flags)} for c in snap.claims])

    def _verify_analysis(self, analysis_id: uuid.UUID, records: int, claims: int) -> None:
        stored = self.session.execute(select(SourceAnalysis.record_count,
                                             SourceAnalysis.claim_count)
                                      .where(SourceAnalysis.id == analysis_id)).one()
        actual_records = self.session.execute(select(func.count()).select_from(SourceRecord)
                                              .where(SourceRecord.analysis_id == analysis_id)
                                              ).scalar_one()
        actual_claims = self.session.execute(select(func.count()).select_from(SourceClaim)
                                             .where(SourceClaim.analysis_id == analysis_id)
                                             ).scalar_one()
        if (stored.record_count, stored.claim_count) != (records, claims) \
                or (actual_records, actual_claims) != (records, claims):
            raise StagingError("ANALYSIS_INCOMPLETE",
                               f"analysis {analysis_id} counters or children are inconsistent")

    def _stored_bytes(self, artifact_row) -> tuple[bytes, Any]:
        content = self.session.execute(
            select(SourceContent.content_json, SourceContent.source_system)
            .where(SourceContent.id == artifact_row.content_id)).one()
        capture_json = self.session.execute(
            select(SourceCapture.capture_json).join(
                SourceArtifact, SourceArtifact.capture_id == SourceCapture.id)
            .where(SourceArtifact.id == artifact_row.id)).scalar_one()
        data = adapters.reconstruct_artifact_bytes(
            source_system=content.source_system, contract_version=artifact_row.contract_version,
            capture_json=capture_json, content_json=content.content_json)
        if hashlib.sha256(data).hexdigest() != artifact_row.artifact_bytes_sha256:
            raise StagingError("STORED_ARTIFACT_CORRUPT",
                               f"artifact {artifact_row.id} does not rebuild to its hash")
        return data, content

    def _stored_snapshot(self, artifact_row) -> ParsedSnapshot:
        data, _ = self._stored_bytes(artifact_row)
        try:
            return parse_artifact_bytes(data)
        except ArtifactError as exc:
            raise StagingError(f"STORED_ARTIFACT_UNPARSEABLE_{exc.code}", str(exc)) from exc

    def _capture_snapshot(self, capture_id: uuid.UUID) -> ParsedSnapshot:
        rows = self.session.execute(
            select(SourceArtifact.id, SourceArtifact.content_id, SourceArtifact.contract_version,
                   SourceArtifact.artifact_bytes_sha256)
            .where(SourceArtifact.capture_id == capture_id)).all()
        if not rows:
            raise StagingError("CAPTURE_HAS_NO_ARTIFACT", str(capture_id))
        newest = max(rows, key=lambda r: int(r.contract_version.split(".")[1]))
        return self._stored_snapshot(newest)

    def _coverage(self, target: tuple[str, str]) -> tuple[int, int]:
        """Every artifact has an analysis under ``target`` and every capture exactly one
        active rank-1 analysis in the observation view; otherwise fail closed."""
        artifacts = self.session.execute(
            select(func.count()).select_from(SourceArtifact)).scalar_one()
        covered = self.session.execute(
            select(func.count()).select_from(SourceArtifact).join(
                SourceAnalysis,
                (SourceAnalysis.content_id == SourceArtifact.content_id)
                & (SourceAnalysis.contract_version == SourceArtifact.contract_version)
                & (SourceAnalysis.identity_rules_version == target[0])
                & (SourceAnalysis.normalization_version == target[1]))).scalar_one()
        captures = self.session.execute(
            select(func.count()).select_from(SourceCapture)).scalar_one()
        selected = self.session.execute(text(
            f"SELECT COUNT(*), COUNT(DISTINCT capture_id) FROM {SOURCE_CAPTURE_ANALYSES_VIEW} "
            "WHERE selection_rank = 1 AND is_active_rule_set = 1")).one()
        if covered != artifacts or tuple(selected) != (captures, captures):
            raise StagingError("ACTIVATION_INCOMPLETE",
                               f"{covered}/{artifacts} artifacts analysed, "
                               f"{selected[1]}/{captures} captures selectable")
        return artifacts, captures

    def _audit(self, entity_type: str, entity_id: uuid.UUID, action: str, metadata: dict) -> None:
        user = self.actor.user_id is not None
        self.session.execute(insert(AuditEvent).values(
            id=uuid.uuid4(), entity_type=entity_type, entity_id=entity_id, action=action,
            actor_type="USER" if user else "SYSTEM", actor_user_id=self.actor.user_id,
            actor_service=None if user else self.actor.service, event_metadata=metadata))


class _Savepoint:
    """``session.begin_nested()`` that turns unexpected integrity errors into StagingError."""

    def __init__(self, session: Session) -> None:
        self.session, self.tx = session, None

    def __enter__(self):
        self.tx = self.session.begin_nested()
        return self.tx

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.tx.commit()
            return False
        self.tx.rollback()
        if isinstance(exc, IntegrityError):
            raise StagingError("INTEGRITY_VIOLATION", type(exc.orig).__name__) from exc
        return False
