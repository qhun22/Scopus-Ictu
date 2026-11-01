"""Gate E.3 / P3-A — pure bridge from staged source claims to pair evidence (synthetic data).

Artifacts are built with the accepted P2-A adapters and parsed with the accepted P1 parser, then
projected into observation rows exactly as the staging view would deliver them.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.services.source_claim_matching.bridge import (
    BRIDGE_RULE_ID,
    SOURCE_TIER,
    BridgeError,
    CaptureRef,
    DecisionRef,
    LecturerRef,
    ObservedClaim,
    PairClass,
    Presence,
    Resolution,
    ScopusAuthorRef,
    bridge_source_claims,
    observations_from_snapshot,
)
from app.services.source_claims import adapters, parser
from app.services.source_claims.parser import parse_artifact_bytes
from tests.source_staging_fixtures import ORCID_A, lecturer, sid, tables_snapshot

BACKEND = Path(__file__).resolve().parents[2]
NS = uuid.UUID("6f1d3c2a-0000-4000-8000-000000000e3a")
REPO = "https://repository.example.invalid"
GUIDE = f"{REPO}/huong-dan-gop-tai-khoan-scopus/"


def u(*parts) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(map(str, parts)))


# ---------------------------------------------------------------------------
# Synthetic artifacts -> captures and observations (as the staging view projects them)
# ---------------------------------------------------------------------------

def multi_artifact(rows, *, ts="2026-10-29T00:32:28Z", completeness="COMPLETE"):
    return adapters.guide_multi_id_artifact(
        {"ts": ts, "url": GUIDE, "multi_id_rows": len(rows), "rows": [list(r) for r in rows]},
        snapshot_sha256="a" * 64, completeness=completeness)


def tables_artifact(ambiguous=(), unassigned=(), *, ts="2026-10-29T01:37:29Z"):
    snapshot = json.loads(tables_snapshot(ambiguous, unassigned, ts=ts)["snapshot_bytes"])
    return adapters.guide_tables_artifact(snapshot, snapshot_sha256="a" * 64,
                                          completeness="COMPLETE")


def profiles_artifact(items, *, completed="2026-10-03T21:31:10Z"):
    manifest = {"harvest_completed_at": completed, "source_base_url": REPO,
                "source_card_count": len(items), "lecturer_count": len(items),
                "status": "COMPLETE", "source_drift_detected": False,
                "semantic_file_hashes": {"lecturers.json": "b" * 64}}
    replay = {"a_equals_b_equals_c": True,
              "file_hashes": {r: {"lecturers.json": "b" * 64} for r in ("A", "B", "C")}}
    return adapters.profiles_artifact(items, manifest, {"source_entity_failures": []}, replay,
                                      lecturers_sha256="a" * 64)


def observe(artifact, *, version="1.0"):
    artifact = copy.deepcopy(artifact)
    artifact["contract_version"] = version
    snap = parse_artifact_bytes(adapters.artifact_bytes(artifact))
    capture_id = u("capture", snap.content_hash, snap.capture.capture_hash)
    analysis_id = u("analysis", snap.content_hash, version, snap.identity_rules_version,
                    snap.normalization_version)
    ids = {r.ref: u("record", analysis_id, r.ref) for r in snap.records}
    ids |= {f"{c.record_ref}/{c.claim_key}": u("claim", analysis_id, c.record_ref, c.claim_key)
            for c in snap.claims}
    capture = CaptureRef(capture_id, snap.source_system.value, snap.scope_key,
                         json.loads(snap.capture.capture_json)["adapter"]["projection"],
                         snap.capture.captured_at, snap.completeness.value)
    return capture, observations_from_snapshot(snap, capture_id=capture_id,
                                               analysis_id=analysis_id, ids=ids)


def run(*observed, lecturers=(), authors=None, decisions=()):
    captures = [c for c, _ in observed]
    rows = [o for _, obs in observed for o in obs]
    if authors is None:
        authors = [ScopusAuthorRef(u("author", n), sid(n)) for n in range(1, 40)]
    return bridge_source_claims(rows, captures, lecturers, authors, decisions)


def gv(n, *, email=None, url=None, orcid=None):
    return LecturerRef(u("lecturer", n), url, email or f"gv{n}@example.invalid", orcid)


def row(n, ids, primary=None, email=None):
    email = f"gv{n}@example.invalid" if email is None else email
    return [f"GV {n}", email, str(len(ids)), "1", primary or ids[0], "; ".join(ids)]


def author(n):
    return u("author", n)


def pair_of(result, lecturer_n, author_n):
    found = [p for p in result.pairs if p.lecturer_id == u("lecturer", lecturer_n)
             and p.scopus_author_id == author(author_n)]
    assert len(found) == 1
    return found[0]


def codes(result):
    return [f.code for f in result.findings]


# ---------------------------------------------------------------------------
# 1-6: claims, subjects, collisions, conflicts
# ---------------------------------------------------------------------------

def test_1_one_lecturer_claiming_several_scopus_ids_keeps_each_with_its_primary_flag():
    result = run(observe(multi_artifact([row(1, [sid(1), sid(2), sid(3)], primary=sid(2))])),
                 lecturers=[gv(1)])
    assert len(result.evidence) == 3
    assert {(e.scopus_id, e.is_primary_claimed) for e in result.evidence} == {
        (sid(1), False), (sid(2), True), (sid(3), False)}          # R-06: source flag only
    assert {e.subject_resolution for e in result.evidence} == {Resolution.RESOLVED_EMAIL}
    assert {e.rule_id for e in result.evidence} == {BRIDGE_RULE_ID}
    assert {e.source_tier for e in result.evidence} == {SOURCE_TIER}
    assert [p.classification for p in result.pairs] == [PairClass.PLAUSIBLE_CANDIDATE] * 3
    assert all(p.accept_reason_required and p.decision_preserved for p in result.pairs)


def test_2_one_scopus_id_in_several_source_rows_is_kept_per_row_and_flagged():
    result = run(observe(multi_artifact([row(1, [sid(5)]), row(2, [sid(5)])])),
                 lecturers=[gv(1), gv(2)])
    assert len(result.evidence) == 2
    for lecturer_n in (1, 2):
        pair = pair_of(result, lecturer_n, 5)
        assert pair.classification is PairClass.CONFLICTING_EVIDENCE
        assert "SCOPUS_ID_DECLARED_FOR_SEVERAL_LECTURERS" in pair.reasons


def test_3_duplicate_orcid_on_distinct_profiles_is_flagged_never_evidence():
    items = [lecturer(1, orcid=ORCID_A), lecturer(2, orcid=ORCID_A)]
    lecturers = [LecturerRef(u("lecturer", 1), f"{REPO}/giang-vien/synthetic-1/",
                             "lecturer1@example.invalid", ORCID_A),
                 LecturerRef(u("lecturer", 2), f"{REPO}/giang-vien/synthetic-2",
                             "lecturer2@example.invalid", None)]
    result = run(observe(profiles_artifact(items)), lecturers=lecturers)
    assert result.evidence == () and result.pairs == ()              # ORCID never pairs (R-13)
    assert codes(result).count("ORCID_DECLARED_BY_MULTIPLE_RECORDS") == 1        # R-14
    assert {(f.code, f.lecturer_id) for f in result.findings if f.code.startswith("ORCID_DECLARED_")
            and f.lecturer_id} == {("ORCID_DECLARED_MATCHES_LECTURER", u("lecturer", 1)),
                                   ("ORCID_DECLARED_LECTURER_HAS_NONE", u("lecturer", 2))}


def test_4_declared_email_resolves_the_subject_and_names_never_do():
    lecturers = [gv(1), LecturerRef(u("lecturer", 99), None, "someone@example.invalid", None)]
    # Row 99 carries the same *name* as no lecturer key; only its e-mail could resolve it.
    result = run(observe(multi_artifact([row(1, [sid(1)]),
                                         ["GV 1", "unknown@example.invalid", "1", "1", sid(2),
                                          sid(2)]])), lecturers=lecturers)
    assert [e.scopus_id for e in result.evidence] == [sid(1)]
    assert "SUBJECT_UNRESOLVED" in codes(result)


def test_4b_profile_resolved_by_url_with_a_different_stored_email_is_reported():
    lecturers = [LecturerRef(u("lecturer", 1), f"{REPO}/giang-vien/synthetic-1/",
                             "old.address@example.invalid", None)]
    result = run(observe(profiles_artifact([lecturer(1)])), lecturers=lecturers)
    assert "EMAIL_DECLARED_DIFFERS_FROM_LECTURER" in codes(result)


def test_5_weak_ambiguous_and_unresolved_subjects_never_get_a_lecturer():
    shared = [LecturerRef(u("lecturer", 10), None, "shared@example.invalid", None),
              LecturerRef(u("lecturer", 11), None, "shared@example.invalid", None)]
    result = run(observe(multi_artifact([row(20, [sid(20)], email=""),          # no e-mail: WEAK
                                         row(21, [sid(21)], email="shared@example.invalid"),
                                         row(22, [sid(22)])])),                  # no such lecturer
                 lecturers=shared)
    assert result.evidence == () and result.pairs == ()
    assert sorted(c for c in codes(result) if c.startswith("SUBJECT_")) == [
        "SUBJECT_AMBIGUOUS", "SUBJECT_UNRESOLVED", "SUBJECT_WEAK_SOURCE_KEY"]


def test_5b_url_and_email_pointing_at_different_lecturers_is_a_conflict():
    capture, observed = observe(multi_artifact([row(1, [sid(1)])]))
    conflicting = tuple(ObservedClaim(**{**{f: getattr(o, f) for f in o.__slots__},
                                         "record_source_id": f"{REPO}/giang-vien/other"})
                        for o in observed)
    lecturers = [gv(1), LecturerRef(u("lecturer", 2), f"{REPO}/giang-vien/other",
                                    "different@example.invalid", None)]
    result = bridge_source_claims(conflicting, [capture], lecturers,
                                  [ScopusAuthorRef(author(1), sid(1))])
    assert result.evidence == () and "SUBJECT_CONFLICT" in codes(result)


def test_6_conflicting_source_claims_and_approvals_elsewhere_are_conflicts():
    owned = observe(multi_artifact([row(1, [sid(7), sid(8)])]))
    unowned = observe(tables_artifact([], [["X", sid(7), "1"]]))
    approved_elsewhere = DecisionRef(u("lecturer", 2), author(8), "ACCEPTED", "APPROVED")
    result = run(owned, unowned, lecturers=[gv(1), gv(2)], decisions=[approved_elsewhere])
    assert pair_of(result, 1, 7).classification is PairClass.CONFLICTING_EVIDENCE
    assert "SCOPUS_ID_ALSO_LISTED_AS_UNASSIGNED" in pair_of(result, 1, 7).reasons
    assert "SCOPUS_ID_APPROVED_FOR_OTHER_LECTURER" in pair_of(result, 1, 8).reasons
    assert "UNOWNED_SCOPUS_ID_LISTED" in codes(result)
    assert all(p.scopus_id != sid(7) or p.lecturer_id == u("lecturer", 1) for p in result.pairs)


def test_unowned_ids_and_ids_missing_from_the_catalog_never_become_pairs():
    result = run(observe(tables_artifact([["X", sid(30), "1"]], [["Y", sid(31), "1"]])),
                 observe(multi_artifact([row(1, ["57000009999"])])),
                 lecturers=[gv(1)], authors=[ScopusAuthorRef(author(30), sid(30))])
    assert result.pairs == ()
    assert codes(result).count("UNOWNED_SCOPUS_ID_LISTED") == 2                 # R-15
    assert "SCOPUS_AUTHOR_NOT_IN_CATALOG" in codes(result)


# ---------------------------------------------------------------------------
# 7-10: projection policy — captures, artifact versions, rule versions, partial captures
# ---------------------------------------------------------------------------

def test_7_repeated_capture_of_identical_claims_does_not_inflate_evidence():
    rows = [row(1, [sid(1), sid(2)])]
    once = run(observe(multi_artifact(rows)), lecturers=[gv(1)])
    twice = run(observe(multi_artifact(rows)), observe(multi_artifact(
        rows, ts="2026-11-29T00:00:00Z")), lecturers=[gv(1)])
    assert [e.fingerprint for e in twice.evidence] == [e.fingerprint for e in once.evidence]
    assert [len(e.observed_in) for e in twice.evidence] == [2, 2]
    assert {e.presence for e in twice.evidence} == {Presence.CURRENT}


def test_8_several_artifact_versions_of_one_capture_are_refused_unless_projected():
    artifact = multi_artifact([row(1, [sid(1)])])
    v10, v11 = observe(artifact, version="1.0"), observe(artifact, version="1.1")
    assert v10[0] == v11[0]                                     # one capture
    with pytest.raises(BridgeError) as raised:
        run(v10, (v11[0], v11[1]), lecturers=[gv(1)])
    assert raised.value.code == "MULTIPLE_ANALYSES_PER_CAPTURE"
    projected = run(v11, lecturers=[gv(1)])                     # what the view selects
    assert [e.fingerprint for e in projected.evidence] == [
        e.fingerprint for e in run(v10, lecturers=[gv(1)]).evidence]


def test_9_new_rule_version_keeps_evidence_identity_and_mixing_is_refused(monkeypatch):
    artifact = multi_artifact([row(1, [sid(1), sid(2)])])
    v1 = observe(artifact)
    before = run(v1, lecturers=[gv(1)])
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    v2 = observe(artifact)
    after = run(v2, lecturers=[gv(1)])
    assert [e.evidence_key for e in after.evidence] == [e.evidence_key for e in before.evidence]
    assert {e.identity_rules_version for e in after.evidence} == {"2"}
    assert after.identity_rules_version == "2"
    with pytest.raises(BridgeError) as raised:
        bridge_source_claims([*v1[1], *v2[1]], [v1[0]], [gv(1)],
                             [ScopusAuthorRef(author(1), sid(1))])
    assert raised.value.code == "MIXED_RULE_VERSIONS"


def test_10_partial_capture_never_implies_withdrawal():
    first = observe(multi_artifact([row(1, [sid(1), sid(2)])]))
    partial = observe(multi_artifact([row(1, [sid(1)])], ts="2026-11-29T00:00:00Z",
                                     completeness="PARTIAL"))
    result = run(first, partial, lecturers=[gv(1)])
    gone = [e for e in result.evidence if e.scopus_id == sid(2)]
    assert [e.presence for e in gone] == [Presence.NOT_OBSERVED]
    assert pair_of(result, 1, 2).classification is PairClass.PLAUSIBLE_CANDIDATE


def test_10b_complete_recapture_withdraws_but_does_not_revoke_anything():
    first = observe(multi_artifact([row(1, [sid(1), sid(2)])]))
    later = observe(multi_artifact([row(1, [sid(1)])], ts="2026-11-29T00:00:00Z"))
    approved = DecisionRef(u("lecturer", 1), author(2), "ACCEPTED", "APPROVED")
    result = run(first, later, lecturers=[gv(1)], decisions=[approved])
    withdrawn = pair_of(result, 1, 2)
    assert [e.presence for e in result.evidence if e.scopus_id == sid(2)] == [Presence.WITHDRAWN]
    assert withdrawn.classification is PairClass.VERIFIED_ASSOCIATION       # decision stands
    assert withdrawn.existing_identity_status == "APPROVED"
    assert "SOURCE_NO_LONGER_LISTS_APPROVED_ID" in codes(result)
    unapproved = run(first, later, lecturers=[gv(1)])
    assert pair_of(unapproved, 1, 2).classification is PairClass.INSUFFICIENT_EVIDENCE


# ---------------------------------------------------------------------------
# 11-13: decisions, invalid claims, determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("candidate_status", "identity_status", "expected"), [
    ("ACCEPTED", "APPROVED", PairClass.VERIFIED_ASSOCIATION),
    ("REJECTED", None, PairClass.PLAUSIBLE_CANDIDATE),
    ("ACCEPTED", "REVOKED", PairClass.PLAUSIBLE_CANDIDATE),
    ("SUPERSEDED", None, PairClass.PLAUSIBLE_CANDIDATE),
    ("PENDING", None, PairClass.PLAUSIBLE_CANDIDATE),
])
def test_11_existing_decisions_are_echoed_never_changed(candidate_status, identity_status,
                                                        expected):
    decision = DecisionRef(u("lecturer", 1), author(1), candidate_status, identity_status)
    result = run(observe(multi_artifact([row(1, [sid(1)])])), lecturers=[gv(1)],
                 decisions=[decision])
    pair = pair_of(result, 1, 1)
    assert pair.classification is expected
    assert (pair.existing_candidate_status, pair.existing_identity_status) == (
        candidate_status, identity_status)
    assert pair.decision_preserved
    negative = candidate_status in ("REJECTED", "SUPERSEDED") or identity_status in (
        "REJECTED", "REVOKED")
    assert ("PRIOR_NEGATIVE_DECISION_REVIEWER_REOPEN_REQUIRED" in pair.reasons) is negative


def test_11b_lecturers_with_approved_ids_stay_eligible_for_new_ids():
    approved = DecisionRef(u("lecturer", 1), author(1), "ACCEPTED", "APPROVED")
    result = run(observe(multi_artifact([row(1, [sid(1), sid(2)])])), lecturers=[gv(1)],
                 decisions=[approved])
    assert pair_of(result, 1, 1).classification is PairClass.VERIFIED_ASSOCIATION
    assert pair_of(result, 1, 2).classification is PairClass.PLAUSIBLE_CANDIDATE   # R-16


def test_11c_bridge_output_has_no_decision_or_status_writing_field():
    fields = {name for cls in (__import__("app.services.source_claim_matching.bridge",
                                          fromlist=["x"]).PairAssessment,)
              for name in cls.__dataclass_fields__}
    assert not fields & {"new_status", "to_status", "action", "approve", "revoke", "status"}


def test_12_invalid_claim_never_becomes_evidence():
    result = run(observe(multi_artifact([["GV 1", "gv1@example.invalid", "1", "1", "57-BAD",
                                          "57-BAD"]])), lecturers=[gv(1)])
    assert result.evidence == () and result.pairs == ()
    assert "INVALID_CLAIM_VALUE" in codes(result)


def test_13_deterministic_regardless_of_input_order():
    observed = [observe(multi_artifact([row(1, [sid(1), sid(2)]), row(2, [sid(2)])])),
                observe(tables_artifact([["X", sid(3), "1"]], [["Y", sid(2), "1"]])),
                observe(multi_artifact([row(1, [sid(1)])], ts="2026-11-29T00:00:00Z"))]
    lecturers = [gv(1), gv(2)]
    baseline = run(*observed, lecturers=lecturers)
    rows = [o for _, obs in observed for o in obs]
    captures = [c for c, _ in observed]
    authors = [ScopusAuthorRef(author(n), sid(n)) for n in range(1, 40)]
    for seed in range(5):
        rng = random.Random(seed)
        shuffled_rows, shuffled_caps = rows[:], captures[:]
        rng.shuffle(shuffled_rows)
        rng.shuffle(shuffled_caps)
        again = bridge_source_claims(shuffled_rows, shuffled_caps, list(reversed(lecturers)),
                                     list(reversed(authors)))
        assert again == baseline


def test_evidence_traces_back_to_claim_record_capture_and_analysis():
    capture, observed = observe(multi_artifact([row(1, [sid(1)])]))
    result = bridge_source_claims(observed, [capture], [gv(1)],
                                  [ScopusAuthorRef(author(1), sid(1))])
    evidence, = result.evidence
    ref, = evidence.observed_in
    owned = [o for o in observed if o.claim_type == "SCOPUS_ID_OWNED"][0]
    assert (ref.capture_id, ref.analysis_id, ref.claim_id, ref.record_id, ref.contract_version) == (
        capture.capture_id, owned.analysis_id, owned.claim_id, owned.record_id, "1.0")
    assert evidence.claim_key == owned.claim_key and evidence.scope_key == capture.scope_key


def test_unknown_capture_and_duplicate_observations_are_refused():
    capture, observed = observe(multi_artifact([row(1, [sid(1)])]))
    with pytest.raises(BridgeError) as raised:
        bridge_source_claims(observed, [], [gv(1)], [])
    assert raised.value.code == "UNKNOWN_CAPTURE"
    with pytest.raises(BridgeError) as raised:
        bridge_source_claims([*observed, observed[0]], [capture], [gv(1)], [])
    assert raised.value.code == "DUPLICATE_OBSERVATION"


# ---------------------------------------------------------------------------
# P3A-R1 / P3A-R2: capture ordering is by instant; UUIDs break ties, never prove succession
# ---------------------------------------------------------------------------

def with_id(observed, capture_id):
    """Same capture and observations under a chosen capture UUID (to test UUID orderings)."""
    capture, rows = observed
    return (dataclasses.replace(capture, capture_id=capture_id),
            tuple(dataclasses.replace(o, capture_id=capture_id) for o in rows))


def claim_of(result, scopus_n):
    found = [e for e in result.evidence if e.scopus_id == sid(scopus_n)]
    assert len(found) == 1
    return found[0]


# 17:00 UTC written three ways; the +07:00 string sorts *after* the Z string ("23" > "17").
T_Z = "2026-10-29T17:00:00Z"
T_Z_PLUS_30 = "2026-10-29T17:30:00Z"
T_EQUAL_PLUS7 = "2026-10-30T00:00:00+07:00"        # == 17:00Z
T_EARLIER_PLUS7 = "2026-10-29T23:00:00+07:00"      # == 16:00Z, but string-greater than T_Z
T_LATER_PLUS7 = "2026-10-30T00:30:00+07:00"        # == 17:30Z


def test_r1_mixed_offsets_take_flags_from_the_later_instant_not_the_later_string():
    older = observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(1))],
                                   ts=T_EARLIER_PLUS7))
    newer = observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(2))], ts=T_Z))
    assert older[0].captured_at > newer[0].captured_at                # strings mislead
    result = run(older, newer, lecturers=[gv(1)])
    assert (claim_of(result, 1).is_primary_claimed, claim_of(result, 2).is_primary_claimed) == (
        False, True)                                                    # the 17:00Z capture wins
    for scopus_n in (1, 2):
        times = [ref.captured_at for ref in claim_of(result, scopus_n).observed_in]
        assert times == [T_EARLIER_PLUS7, T_Z]                          # chronological order
    assert {e.presence for e in result.evidence} == {Presence.CURRENT}


def test_r1_listed_flag_follows_the_later_instant():
    older = observe(multi_artifact([row(1, [sid(1)], primary=sid(2))], ts=T_EARLIER_PLUS7))
    newer = observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(2))], ts=T_Z))
    result = run(older, newer, lecturers=[gv(1)])
    assert claim_of(result, 2).listed is True                           # 17:00Z lists it
    swapped = run(observe(multi_artifact([row(1, [sid(1)], primary=sid(2))], ts=T_Z)),
                  observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(2))],
                                         ts=T_EARLIER_PLUS7)), lecturers=[gv(1)])
    assert claim_of(swapped, 2).listed is False       # the later 17:00Z capture does not list it
    assert claim_of(swapped, 1).presence is Presence.CURRENT


def test_r1_ordering_is_independent_of_input_order_and_captures_listing():
    older = observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(1))],
                                   ts=T_EARLIER_PLUS7))
    newer = observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(2))], ts=T_Z))
    baseline = run(older, newer, lecturers=[gv(1)])
    rows = [*older[1], *newer[1]]
    for seed in range(6):
        rng = random.Random(seed)
        rng.shuffle(rows)
        captures = [older[0], newer[0]]
        rng.shuffle(captures)
        assert bridge_source_claims(rows, captures, [gv(1)],
                                    [ScopusAuthorRef(author(n), sid(n)) for n in range(1, 40)]
                                    ) == baseline


def test_r1_naive_capture_time_is_refused():
    capture, observed = observe(multi_artifact([row(1, [sid(1)])]))
    naive = dataclasses.replace(capture, captured_at="2026-10-29T17:00:00")
    with pytest.raises(BridgeError) as raised:
        bridge_source_claims(observed, [naive], [gv(1)], [ScopusAuthorRef(author(1), sid(1))])
    assert raised.value.code == "CAPTURE_TIME_INVALID"


@pytest.mark.parametrize("later_time", [T_Z, T_EQUAL_PLUS7])
@pytest.mark.parametrize("uuid_order", [(1, 2), (2, 1)])
def test_r2_equal_instants_never_prove_withdrawal(uuid_order, later_time):
    """Same instant (also written with another offset): no UUID order can make B 'later'."""
    lists_both = with_id(observe(multi_artifact([row(1, [sid(1), sid(2)])], ts=T_Z)),
                         uuid.UUID(int=uuid_order[0]))
    omits_one = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=later_time)),
                        uuid.UUID(int=uuid_order[1]))
    result = run(lists_both, omits_one, lecturers=[gv(1)])
    gone = claim_of(result, 2)
    assert gone.presence is Presence.NOT_OBSERVED
    assert gone.presence is not Presence.WITHDRAWN
    assert pair_of(result, 1, 2).classification is PairClass.PLAUSIBLE_CANDIDATE
    ambiguous = [f for f in result.findings
                 if f.code == "CAPTURE_ORDER_AMBIGUOUS" and f.scopus_id == sid(2)]
    assert len(ambiguous) == 1 and dict(ambiguous[0].detail)["reason"] == "PRESENCE_DIFFERS"


@pytest.mark.parametrize("uuid_order", [(1, 2), (2, 1)])
def test_r2_strictly_later_complete_capture_still_withdraws_whatever_the_uuids(uuid_order):
    earlier = with_id(observe(multi_artifact([row(1, [sid(1), sid(2)])], ts=T_Z)),
                      uuid.UUID(int=uuid_order[0]))
    later = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=T_LATER_PLUS7)),
                    uuid.UUID(int=uuid_order[1]))
    result = run(earlier, later, lecturers=[gv(1)])
    assert claim_of(result, 2).presence is Presence.WITHDRAWN
    assert claim_of(result, 1).presence is Presence.CURRENT
    assert "CAPTURE_ORDER_AMBIGUOUS" not in codes(result)


def test_r2_two_later_captures_at_the_same_instant_that_both_omit_the_claim_withdraw_it():
    earlier = observe(multi_artifact([row(1, [sid(1), sid(2)])], ts=T_Z))
    twin_a = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=T_Z_PLUS_30)),
                     uuid.UUID(int=1))
    twin_b = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=T_LATER_PLUS7)),
                     uuid.UUID(int=2))
    assert twin_a[0].captured_at != twin_b[0].captured_at               # written differently ...
    result = run(earlier, twin_a, twin_b, lecturers=[gv(1)])
    assert claim_of(result, 2).presence is Presence.WITHDRAWN           # ... same later instant


@pytest.mark.parametrize("uuid_order", [(1, 2), (2, 1)])
def test_r2_a_partial_capture_at_the_latest_instant_blocks_withdrawal(uuid_order):
    earlier = observe(multi_artifact([row(1, [sid(1), sid(2)])], ts=T_Z))
    complete = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=T_Z_PLUS_30)),
                       uuid.UUID(int=uuid_order[0]))
    partial = with_id(observe(multi_artifact([row(1, [sid(1)], email="gv1@example.invalid")],
                                             ts="2026-10-30T00:30:00+07:00",
                                             completeness="PARTIAL")),
                      uuid.UUID(int=uuid_order[1]))
    result = run(earlier, complete, partial, lecturers=[gv(1)])
    assert claim_of(result, 2).presence is Presence.NOT_OBSERVED


def test_r2_tied_listing_captures_with_different_flags_are_flagged_not_silently_chosen():
    a = with_id(observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(1))], ts=T_Z)),
                uuid.UUID(int=1))
    b = with_id(observe(multi_artifact([row(1, [sid(1), sid(2)], primary=sid(2))],
                                       ts=T_EQUAL_PLUS7)), uuid.UUID(int=2))
    result = run(a, b, lecturers=[gv(1)])
    flagged = {f.scopus_id for f in result.findings if f.code == "CAPTURE_ORDER_AMBIGUOUS"
               and dict(f.detail)["reason"] == "FLAGS_DIFFER"}
    assert flagged == {sid(1), sid(2)}
    assert {e.presence for e in result.evidence} == {Presence.CURRENT}


@pytest.mark.parametrize("uuid_order", [(1, 2), (2, 1)])
def test_r2_ambiguity_never_revokes_an_approved_identity(uuid_order):
    lists_both = with_id(observe(multi_artifact([row(1, [sid(1), sid(2)])], ts=T_Z)),
                         uuid.UUID(int=uuid_order[0]))
    omits_one = with_id(observe(multi_artifact([row(1, [sid(1)])], ts=T_EQUAL_PLUS7)),
                        uuid.UUID(int=uuid_order[1]))
    approved = DecisionRef(u("lecturer", 1), author(2), "ACCEPTED", "APPROVED")
    result = run(lists_both, omits_one, lecturers=[gv(1)], decisions=[approved])
    pair = pair_of(result, 1, 2)
    assert pair.classification is PairClass.VERIFIED_ASSOCIATION
    assert (pair.existing_candidate_status, pair.existing_identity_status) == (
        "ACCEPTED", "APPROVED") and pair.decision_preserved
    assert "SOURCE_NO_LONGER_LISTS_APPROVED_ID" not in codes(result)


def test_source_claim_storage_is_explicit_but_reviewer_promotion_stays_blocked():
    """P3-B1 extends storage only; promotion and D-2 remain unchanged."""
    import inspect

    from app.models import Base
    from app.services import review_reason_policy
    from app.services.candidate_review_service import CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE

    table = Base.metadata.tables["lecturer_scopus_candidate_evidence"]
    kinds = [str(c.sqltext) for c in table.constraints
             if getattr(c, "name", None) and "evidence_kind" in str(c.name)]
    assert kinds == ["evidence_kind IN ('NAME', 'PUBLICATION', 'SOURCE_CLAIM')"]
    assert set(CANDIDATE_TO_IDENTITY_EVIDENCE_TYPE) == {"NAME", "PUBLICATION"}
    # D-2: only PUBLICATION evidence lifts NAME_EVIDENCE_ONLY; a source listing must not (R-05).
    assert '"PUBLICATION" not in set(evidence_kinds)' in inspect.getsource(
        review_reason_policy.accept_reason_policy)


def test_bridge_imports_no_database_matching_or_network_modules():
    bad = ("sqlalchemy", "psycopg2", "fastapi", "app.models", "app.core", "app.api",
           "app.services.matching", "app.services.candidate_review_service", "requests", "httpx",
           "socket", "http.client")
    code = (
        "import json, sys; sys.path.insert(0, '.');"
        f"bad = {bad!r};"
        "hit = lambda names: sorted(m for m in names"
        " if any(m == b or m.startswith(b + '.') for b in bad));"
        "before = set(sys.modules);"
        "import app.services.source_claim_matching.bridge;"
        "print(json.dumps({'new': hit(set(sys.modules) - before)}))"
    )
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=BACKEND,
                            capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(result.stdout)["new"] == [], result.stdout + result.stderr
