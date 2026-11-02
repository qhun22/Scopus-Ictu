"""B2-A: actual serializers/read queries on synthetic SQLite, no live review actions."""

from __future__ import annotations

import ast
import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app.core.exceptions import APIError
from app.models import candidate as candidate_models
from app.models import master_lecturer as lecturer_models
from app.models import publication as publication_models
from app.models.candidate import (
    CandidateGenerationRun,
    LecturerScopusCandidate,
    LecturerScopusCandidateEvidence,
    LecturerScopusCandidateObservation,
)
from app.models.identity import LecturerScopusIdentity
from app.models.source_staging import SourceRuleSet
from app.schemas import review_api
from app.services.candidate_fit import assess_fit, ictu_affiliation_paper_counts
from app.services.candidate_evidence_read import (
    _history,
    serialize_review_evidence,
    source_claim_read_preview,
)
from app.services.candidate_review_queries import (
    current_reviewable_candidates_subquery,
    current_reviewable_observation,
)
from app.services.candidate_review_service import ObservationNotFoundError
from app.services.matching.candidate_persistence import sha256_json
from app.services.review_reason_policy import accept_reason_policy
from app.services.source_claim_matching import bridge
from app.services.source_claims import adapters, parser
from tests.source_staging_fixtures import multi_row, multi_snapshot, sid
from tests.unit.test_source_claim_candidate_persistence import guide, uid, write
from tests.unit.test_source_claim_candidate_persistence import world as world


def preview(world):
    root = world[0].scalar(select(LecturerScopusCandidate).where(
        LecturerScopusCandidate.lecturer_id == uid(1),
        LecturerScopusCandidate.scopus_author_id == uid(101)))
    return source_claim_read_preview(world[0], root.id)


def rows(world):
    return world[0].scalars(select(LecturerScopusCandidateEvidence)).all()


def legacy_row(kind="NAME", *, payload=None, refs=None):
    return SimpleNamespace(id=uid(700), evidence_kind=kind, rule_id="SYNTHETIC_RULE",
                           rule_version="1", payload=payload or {}, source_refs=refs or [],
                           evidence_fingerprint="a" * 64)


def detail_function(source=None):
    """Execute the real read handler body with injected dependencies.

    No router/app/database module import, auth bypass endpoint or HTTP server.
    Route decorators are omitted; production authorization itself is unmodified
    and is not claimed tested by these function-level offline checks.
    """
    path = Path(__file__).parents[2] / "app/api/v1/endpoints/reviews.py"
    tree = ast.parse(source if source is not None else path.read_text(encoding="utf-8"))
    names = {"_serialize_uuid", "_source_ref_ids", "_detail_fit", "review_candidate_detail"}
    functions = [copy.deepcopy(n) for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in functions:
        node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0), *functions],
        type_ignores=[])
    namespace = {**vars(review_api), **vars(candidate_models), **vars(lecturer_models),
                 **vars(publication_models), "uuid": uuid, "select": select, "func": func,
                 "APIError": APIError, "ObservationNotFoundError": ObservationNotFoundError,
                 "current_reviewable_observation": current_reviewable_observation,
                 "accept_reason_policy": accept_reason_policy,
                 "serialize_review_evidence": serialize_review_evidence,
                 "assess_fit": assess_fit,
                 "ictu_affiliation_paper_counts": ictu_affiliation_paper_counts}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["review_candidate_detail"]


def completed_observation(world, evidence_kind="NAME"):
    db = world[0]
    root = db.scalar(select(LecturerScopusCandidate))
    now = datetime.now(UTC)
    run = CandidateGenerationRun(
        id=uid(800), rule_set_id="EXISTING_MATCHING", rule_set_version="1",
        status="COMPLETED", source_state={}, started_at=now, completed_at=now,
    )
    db.add(run)
    db.flush()
    observation = LecturerScopusCandidateObservation(
        id=uid(801), candidate_id=root.id, generation_run_id=run.id, observed_at=now,
        candidate_snapshot={}, observation_hash="b" * 64,
    )
    db.add(observation)
    db.flush()
    ev = LecturerScopusCandidateEvidence(
        id=uid(802), observation_id=observation.id, evidence_kind=evidence_kind,
        rule_id="SYNTHETIC_RULE", rule_version="1", payload={}, source_refs=[],
        evidence_fingerprint="a" * 64,
    )
    db.add(ev)
    db.commit()
    return root, observation, ev


def test_source_serializer_uses_explicit_tier_and_allowlisted_provenance(world):
    guide(world)
    write(world)
    body = preview(world)
    item, = body.items
    assert not body.reviewer_active and not body.decision_enabled
    assert item.evidence_kind == "SOURCE_CLAIM" and item.source_tier == "INSTITUTION_DECLARED"
    assert item.selection_status == "ACTIVE_PROJECTION" and item.current_state == "CURRENT"
    assert item.current_weight == 1 and item.subject_resolution == "RESOLVED_EMAIL"
    trace, = item.source_refs
    assert trace.capture_id and trace.analysis_id and trace.claim_id and trace.artifact_id
    assert trace.contract_version == "1.0" and trace.identity_rules_version == "1"
    assert trace.selection_status == "ACTIVE_PROJECTION"
    assert trace.captured_at.utcoffset().total_seconds() == 0
    assert item.history[0].rule_id == bridge.BRIDGE_RULE_ID
    dumped = body.model_dump_json()
    for forbidden in ("record_raw", "record_issues", "value_raw", "record_email", "claim_key",
                      "subject_key", "gv1@example.invalid", "GV 1", "source_observations"):
        assert forbidden not in dumped
    assert "PUBLICATION" not in dumped and "ORCID_EXACT" not in dumped


def test_private_raw_flags_and_source_fields_never_leak(world):
    source_row = multi_row(1, [sid(1)])
    source_row[0] = "PRIVATE_PHONE_private@example.invalid"
    guide(world, [source_row])
    write(world)
    assert "PRIVATE_PHONE" in str(rows(world)[0].source_refs[0]["record_raw"])
    body = preview(world)
    assert body.items[0].current_state == "CURRENT"
    assert "PRIVATE_PHONE" not in body.model_dump_json()
    assert "private@example.invalid" not in body.model_dump_json()


def test_legacy_name_serialization_is_unchanged():
    payload = {"lecturer_source_value": "Synthetic lecturer",
               "lecturer_comparison_value": "synthetic lecturer",
               "scopus_surface_type": "PREFERRED_NAME", "scopus_surface_value": "Synthetic Author",
               "scopus_comparison_value": "synthetic author", "ignored": "not a response field"}
    refs = [{"kind": "scopus_author", "id": str(uid(101))}]
    names, papers = serialize_review_evidence([legacy_row(payload=payload, refs=refs)], {})
    assert papers == []
    assert names[0].model_dump(mode="json") == {
        "evidence_id": str(uid(700)), "evidence_kind": "NAME", "rule_id": "SYNTHETIC_RULE",
        "rule_version": "1", **{k: v for k, v in payload.items() if k != "ignored"},
        "source_refs": refs, "evidence_fingerprint": "a" * 64,
    }


@pytest.mark.parametrize("canonical", [True, False])
def test_publication_serialization_keeps_lookup_and_payload_fallback(canonical):
    payload = {"reconciliation": "DOI_EXACT", "canonical_publication_title": "Fallback title",
               "canonical_publication_doi": "10.0000/fallback", "canonical_publication_eid": "E0",
               "candidate_scopus_author_id": str(uid(101))}
    refs = [{"kind": "publication", "id": str(uid(900))},
            {"kind": "lecturer_known_publication", "id": str(uid(901))},
            {"kind": "publication", "id": "invalid-uuid"}, "ignored"]
    publications = {
        uid(900): SimpleNamespace(title="Canonical title", doi="10.0000/test", eid="E1")}
    names, papers = serialize_review_evidence(
        [legacy_row("PUBLICATION", payload=payload, refs=refs)], publications if canonical else {})
    assert names == [] and len(papers) == 1
    assert papers[0].evidence_kind == "PUBLICATION"
    assert papers[0].title == ("Canonical title" if canonical else "Fallback title")
    assert papers[0].doi == ("10.0000/test" if canonical else "10.0000/fallback")
    assert papers[0].canonical_publication_id == uid(900)
    assert papers[0].known_publication_id == uid(901)
    assert papers[0].candidate_scopus_author_id == uid(101)
    assert papers[0].source_refs == refs


@pytest.mark.parametrize("kind", ["UNKNOWN", "ORCID_EXACT", "APPROVED_ID", ""])
def test_unknown_kinds_never_fall_through_to_publication(kind):
    with pytest.raises(APIError) as exc:
        serialize_review_evidence([legacy_row(kind)], {})
    assert exc.value.code == "CANDIDATE_EVIDENCE_KIND_UNSUPPORTED"
    assert exc.value.status_code == 409


def test_live_serializer_rejects_source_evidence_without_any_false_publication(world):
    guide(world)
    write(world)
    with pytest.raises(APIError) as exc:
        serialize_review_evidence(rows(world), {})
    assert exc.value.code == "SOURCE_CLAIM_REVIEW_INACTIVE"


@pytest.mark.parametrize(("kind", "code"), [
    ("SOURCE_CLAIM", "SOURCE_CLAIM_REVIEW_INACTIVE"),
    ("UNRECOGNIZED", "CANDIDATE_EVIDENCE_KIND_UNSUPPORTED"),
])
def test_real_detail_handler_fails_closed_even_for_a_manually_completed_bad_kind(world, kind, code):
    guide(world)
    write(world)
    root, _, _ = completed_observation(world, kind)
    with pytest.raises(APIError) as exc:
        detail_function()(root.id, None, world[0])
    assert exc.value.code == code


def test_real_detail_handler_keeps_completed_name_and_d2_while_source_is_staged(world):
    guide(world)
    write(world)
    root, observation, _ = completed_observation(world)
    before = (root.status, root.version)
    write(world, 501)
    body = detail_function()(root.id, None, world[0])
    assert body.current_observation.observation_id == observation.id
    assert [e.evidence_kind for e in body.name_evidence] == ["NAME"]
    assert body.publication_evidence == []
    assert body.review_policy.accept_reason_required
    assert "NAME_EVIDENCE_ONLY" in body.review_policy.accept_reason_triggers
    assert (root.status, root.version) == before


@pytest.mark.parametrize("changes", [
    {"current_state": "WITHDRAWN", "current_weight": 1},
    {"selection_status": "HISTORICAL_ONLY"},
    {"temporal_ambiguity": True},
    {"source_tier": "ORCID_EXACT"},
    {"source_refs": []},
])
def test_read_schema_rejects_inconsistent_authority_or_missing_provenance(world, changes):
    guide(world)
    write(world)
    value = preview(world).items[0].model_dump()
    value.update(changes)
    with pytest.raises(ValidationError):
        review_api.ReviewSourceClaimEvidenceResponse.model_validate(value)


def test_staged_only_root_stays_out_of_queue_and_read_does_not_promote_it(world):
    guide(world)
    write(world)
    db = world[0]
    root = db.scalar(select(LecturerScopusCandidate))
    before = [(r.id, r.status, r.version) for r in db.scalars(select(CandidateGenerationRun))]
    assert preview(world).items
    assert db.execute(select(current_reviewable_candidates_subquery("PENDING"))).all() == []
    with pytest.raises(ObservationNotFoundError):
        current_reviewable_observation(db, root.id)
    after = [(r.id, r.status, r.version) for r in db.scalars(select(CandidateGenerationRun))]
    assert after == before


def test_replay_and_repeated_capture_show_one_logical_item_with_full_history(world):
    guide(world)
    write(world)
    write(world)
    guide(world, ts="2026-10-30T00:00:00Z")
    write(world, 501)
    write(world, 502)
    body = preview(world)
    item, = body.items
    assert item.current_weight == 1 and len(item.history) == 3
    assert len(item.source_refs) == 2
    assert len(rows(world)) == 3


def test_new_capture_invalidates_current_read_until_regeneration(world):
    guide(world)
    write(world)
    guide(world, ts="2026-10-30T00:00:00Z")
    item, = preview(world).items
    assert item.current_weight == 0 and item.current_state == "STALE"
    assert item.selection_status == "HISTORICAL_ONLY"
    assert item.is_primary_claimed is None and item.subject_resolution is None
    assert item.recorded_states == ["CURRENT"]
    assert all(r.selection_status == "HISTORICAL_ONLY" for r in item.source_refs)


def test_withdrawal_keeps_historical_current_records_but_zeroes_active_weight(world):
    guide(world)
    write(world)
    guide(world, rows=[], ts="2026-10-30T00:00:00Z")
    write(world, 501)
    item, = preview(world).items
    assert item.current_state == "WITHDRAWN" and item.current_weight == 0
    assert item.selection_status == "ACTIVE_PROJECTION"
    assert item.recorded_states == ["CURRENT", "WITHDRAWN"]
    assert "CLAIM_WITHDRAWN_FROM_SOURCE" in item.recorded_conflict_codes
    assert item.is_primary_claimed is None and len(item.history) == 2


@pytest.mark.parametrize(("ts", "complete", "expected"), [
    ("2026-10-30T00:00:00Z", "PARTIAL", "NOT_OBSERVED"),
    ("2026-10-29T07:00:00+07:00", "COMPLETE", "AMBIGUOUS"),
])
def test_partial_and_equal_time_contradictions_are_not_authoritative(world, ts, complete, expected):
    guide(world)
    write(world)
    guide(world, rows=[], ts=ts, completeness=complete)
    write(world, 501)
    item, = preview(world).items
    assert item.current_state == expected and item.current_weight == 0
    assert item.temporal_ambiguity == (expected == "AMBIGUOUS")
    assert item.listed is None


def test_equal_time_flag_disagreement_never_exposes_primary_as_current_fact(world):
    guide(world, [multi_row(1, [sid(1), sid(2)])], ts="2026-10-28T00:00:00Z")
    write(world)
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(1))])
    guide(world, [multi_row(1, [sid(1), sid(2)], primary=sid(2))])
    write(world, 501)
    assert len(preview(world).items) == 1  # preview selects this candidate, not every pair.
    assert all(i.current_weight == 0 and i.temporal_ambiguity
               and i.is_primary_claimed is None for i in preview(world).items)


def test_rule_reanalysis_marks_old_analysis_refs_as_history_without_inflation(world, monkeypatch):
    guide(world)
    write(world)
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    world[1].activate_rule_set()
    assert preview(world).items[0].current_state == "STALE"
    write(world, 501)
    item, = preview(world).items
    assert item.current_weight == 1
    assert {r.identity_rules_version for r in item.source_refs} == {"1", "2"}
    assert {r.identity_rules_version for r in item.source_refs
            if r.selection_status == "ACTIVE_PROJECTION"} == {"2"}


def test_contract_variation_keeps_one_item_and_distinguishes_trace_versions(world):
    guide(world)
    write(world)
    snapshot = multi_snapshot([multi_row(1, [sid(1)])], ts="2026-10-29T00:00:00Z")
    artifact = adapters.guide_multi_id_artifact(
        json.loads(snapshot["snapshot_bytes"]), snapshot_sha256=snapshot["snapshot_sha256"],
        completeness="COMPLETE")
    artifact["contract_version"] = "1.1"
    world[1]._ingest(adapters.artifact_bytes(artifact), None)
    write(world, 501)
    item, = preview(world).items
    assert item.current_weight == 1
    assert {r.contract_version for r in item.source_refs} == {"1.0", "1.1"}
    assert {r.contract_version for r in item.source_refs
            if r.selection_status == "ACTIVE_PROJECTION"} == {"1.1"}


def test_competing_ownership_conflict_is_explicit_but_not_an_identity_error(world):
    guide(world, [multi_row(1, [sid(1)]), multi_row(2, [sid(1)])])
    write(world)
    item, = preview(world).items
    assert "SCOPUS_ID_DECLARED_FOR_SEVERAL_LECTURERS" in item.recorded_conflict_codes
    assert item.current_weight == 1  # Usable declaration, never approved identity evidence.
    assert not preview(world).decision_enabled


@pytest.mark.parametrize("status", ["REJECTED", "SUPERSEDED", "ACCEPTED"])
def test_read_preserves_existing_candidate_decision_and_stales_old_current(world, status):
    guide(world)
    write(world)
    root = world[0].scalar(select(LecturerScopusCandidate))
    root.status = status  # Fixture setup; no reviewer handler is called.
    world[0].flush()
    before = root.status, root.version
    item, = preview(world).items
    assert item.current_weight == 0
    assert (root.status, root.version) == before


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED", "REVOKED"])
def test_canonical_identity_remains_unchanged_and_read_is_select_only(world, status):
    guide(world)
    write(world)
    db = world[0]
    identity = LecturerScopusIdentity(id=uid(999), lecturer_id=uid(1), scopus_author_id=uid(101),
                                     status=status, version=1)
    db.add(identity)
    db.flush()
    write(world, 501)
    before = identity.status, identity.version
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        assert preview(world).items
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
    assert statements and set(statements) <= {"SELECT", "WITH"}
    assert (identity.status, identity.version) == before


def test_read_does_not_autoflush_callers_pending_changes(world):
    guide(world)
    write(world)
    pending = publication_models.ScopusAuthor(id=uid(999), scopus_id=None, preferred_name="invalid")
    world[0].add(pending)
    assert preview(world).items
    assert pending in world[0].new and world[0].is_active


def test_missing_active_analysis_fails_closed_without_claiming_current(world):
    guide(world)
    write(world)
    world[0].add(SourceRuleSet(id=uid(999), identity_rules_version="unavailable",
                               normalization_version="unavailable"))
    world[0].flush()
    with pytest.raises(APIError) as exc:
        preview(world)
    assert exc.value.code == "SOURCE_CLAIM_PROJECTION_UNAVAILABLE"


def test_changed_evidence_snapshot_or_refs_fail_closed(world):
    guide(world)
    write(world)
    ev = rows(world)[0]
    ev.source_refs = [{"private": "must never be forwarded"}]
    world[0].flush()
    with pytest.raises(APIError):
        preview(world)


def stale_history(world):
    """One intact historical run with no matching CURRENT generation."""
    guide(world, ts="2026-10-01T10:00:00Z")
    write(world)
    guide(world, ts="2026-10-02T10:00:00Z")
    db = world[0]
    row = rows(world)[0]
    observation = db.get(LecturerScopusCandidateObservation, row.observation_id)
    run = db.get(CandidateGenerationRun, observation.generation_run_id)
    candidate = db.get(LecturerScopusCandidate, observation.candidate_id)
    return row, observation, run, candidate


def test_r1_valid_stale_history_passes_without_writes_or_hash_changes(world):
    args = stale_history(world)
    run = args[2]
    before = copy.deepcopy(run.source_state)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(world[0].get_bind(), "before_cursor_execute", capture)
    try:
        _, _, traces, _ = _history(*args)
        item, = preview(world).items
    finally:
        event.remove(world[0].get_bind(), "before_cursor_execute", capture)
    assert traces[0]["captured_at"] == datetime(2026, 10, 1, 10, tzinfo=UTC)
    assert traces[0]["completeness"] == "COMPLETE"
    assert item.current_state == "STALE" and item.current_weight == 0
    assert run.source_state == before
    assert not world[0].dirty and not world[0].new
    assert statements and set(statements) <= {"SELECT", "WITH"}


@pytest.mark.parametrize(("field", "value"), [
    ("captured_at", "2035-07-01T10:00:00Z"), ("completeness", "PARTIAL"),
])
def test_r1_stale_capture_tampering_with_original_hash_is_rejected(world, field, value):
    args = stale_history(world)
    run = args[2]
    state = copy.deepcopy(run.source_state)
    state["captures"][0][field] = value
    run.source_state = state
    world[0].flush()  # Synthetic tampering setup only; reader must not repair it.
    before = copy.deepcopy(run.source_state)
    for read in (lambda: _history(*args), lambda: preview(world)):
        with pytest.raises(APIError) as exc:
            read()
        assert exc.value.code == "SOURCE_CLAIM_EVIDENCE_INVALID"
    assert run.source_state == before and not world[0].dirty


@pytest.mark.parametrize("stored_hash", ["MISSING", None, 123, [], {}, "bad", "0" * 64])
def test_r1_missing_malformed_or_wrong_input_hash_fails_closed(world, stored_hash):
    args = stale_history(world)
    state = copy.deepcopy(args[2].source_state)
    if stored_hash == "MISSING":
        state.pop("input_hash")
    else:
        state["input_hash"] = stored_hash
    args[2].source_state = state
    world[0].flush()
    with pytest.raises(APIError) as exc:
        preview(world)
    assert exc.value.code == "SOURCE_CLAIM_EVIDENCE_INVALID"
    assert args[2].source_state == state


@pytest.mark.parametrize("malformed", [None, [], "not an object", 123])
def test_r1_malformed_history_state_has_controlled_error(world, malformed):
    row, observation, run, candidate = stale_history(world)
    bad_run = SimpleNamespace(id=run.id, source_state=malformed)
    with pytest.raises(APIError) as exc:
        _history(row, observation, bad_run, candidate)
    assert exc.value.code == "SOURCE_CLAIM_EVIDENCE_INVALID"


@pytest.mark.parametrize("change", [
    "missing_captures", "captures_dict", "capture_scalar", "missing_time", "time_list",
    "time_number", "invalid_time", "naive_time", "missing_completeness", "completeness_list",
    "invalid_completeness", "missing_capture_id", "invalid_capture_id", "duplicate_capture_id",
])
def test_r1_malformed_capture_envelope_even_with_consistent_hash_is_rejected(world, change):
    args = stale_history(world)
    state = copy.deepcopy(args[2].source_state)
    cap = state["captures"][0]
    if change == "missing_captures":
        state.pop("captures")
    elif change == "captures_dict":
        state["captures"] = {}
    elif change == "capture_scalar":
        state["captures"] = [123]
    elif change == "duplicate_capture_id":
        state["captures"].append(copy.deepcopy(cap))
    elif change.startswith("missing_"):
        cap.pop({"missing_time": "captured_at", "missing_completeness": "completeness",
                 "missing_capture_id": "capture_id"}[change])
    else:
        key, value = {
            "time_list": ("captured_at", []), "time_number": ("captured_at", 2035),
            "invalid_time": ("captured_at", "not-a-time"),
            "naive_time": ("captured_at", "2026-10-01T10:00:00"),
            "completeness_list": ("completeness", []),
            "invalid_completeness": ("completeness", "UNKNOWN"),
            "invalid_capture_id": ("capture_id", []),
        }[change]
        cap[key] = value
    state.pop("input_hash")
    state["input_hash"] = sha256_json(state)  # Structure validation must still apply.
    args[2].source_state = state
    world[0].flush()
    with pytest.raises(APIError) as exc:
        preview(world)
    assert exc.value.code == "SOURCE_CLAIM_EVIDENCE_INVALID"
